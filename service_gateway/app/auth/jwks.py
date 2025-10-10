"""
JSON Web Key Set (JWKS) authentication utilities for the Access Gateway.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional, Set

import httpx
from fastapi import Request
from jose import JWTError, jwt

from shared.errors import AuthenticationError
from shared.logging import get_logger


@dataclass(frozen=True)
class AuthContext:
    """Authenticated request context derived from a verified JWT."""

    subject: str
    tenant_id: str
    roles: Set[str]
    claims: Dict[str, Any]
    token: str


class JWKSAuthenticator:
    """Authenticator that validates JWTs against a remote JWKS endpoint."""

    def __init__(
        self,
        jwks_url: str,
        audience: Optional[str] = None,
        issuer: Optional[str] = None,
        *,
        required_role: Optional[str] = "marketdata:read",
        refresh_interval: int = 300,
        http_timeout: float = 5.0,
    ) -> None:
        self.jwks_url = jwks_url
        self.audience = audience
        self.issuer = issuer
        self.required_role = required_role
        self.refresh_interval = refresh_interval
        self.logger = get_logger("gateway.auth.jwks")

        self._keys: Optional[Iterable[Dict[str, Any]]] = None
        self._last_refresh: float = 0.0
        self._lock = asyncio.Lock()
        self._client = httpx.AsyncClient(timeout=http_timeout)

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    async def warmup(self) -> None:
        """Eagerly load JWKS metadata so the first request does not pay the cost."""
        try:
            await self._refresh_keys(force=True)
        except Exception as exc:  # pragma: no cover - best-effort warmup
            self.logger.warning("JWKS warmup failed", error=str(exc))

    async def authenticate(self, request: Request) -> AuthContext:
        """Authenticate the incoming request using the Authorization bearer token."""
        authorization = request.headers.get("Authorization")
        if not authorization or not authorization.startswith("Bearer "):
            raise AuthenticationError("Missing or invalid Authorization header")

        token = authorization[7:].strip()
        if not token:
            raise AuthenticationError("Authorization header contained empty bearer token")

        claims = await self._validate_token(token)
        subject = claims.get("sub")
        if not isinstance(subject, str) or not subject:
            raise AuthenticationError("JWT missing subject claim")

        roles = self._extract_roles(claims)
        if self.required_role and self.required_role not in roles:
            raise AuthenticationError(
                f"Missing required role '{self.required_role}'",
                details={"roles": sorted(roles)},
            )

        tenant_id = self._resolve_tenant_id(request, claims)
        context = AuthContext(
            subject=subject,
            tenant_id=tenant_id,
            roles=roles,
            claims=claims,
            token=token,
        )

        # Cache context on the request for downstream handlers/middleware.
        request.state.user_info = {
            "user_id": subject,
            "tenant_id": tenant_id,
            "roles": sorted(roles),
        }
        request.state.auth_context = context
        return context

    async def check_health(self) -> str:
        """Return 'ok' if the JWKS endpoint responds correctly, otherwise 'error'."""
        try:
            await self._refresh_keys(force=False)
            return "ok"
        except Exception as exc:
            self.logger.error("JWKS health check failed", error=str(exc))
            return "error"

    async def _validate_token(self, token: str) -> Dict[str, Any]:
        """Validate the JWT and return its claims."""
        header = jwt.get_unverified_header(token)
        kid = header.get("kid")
        if not isinstance(kid, str):
            raise AuthenticationError("JWT header missing key id (kid)")

        key_data = await self._get_key(kid)
        if not key_data:
            raise AuthenticationError("Signing key not found for token", details={"kid": kid})

        algorithms = [key_data.get("alg", "RS256")]
        options: Dict[str, Any] = {"verify_aud": self.audience is not None}

        try:
            claims = jwt.decode(
                token,
                key_data,
                algorithms=algorithms,
                audience=self.audience,
                issuer=self.issuer,
                options=options,
            )
        except JWTError as exc:
            raise AuthenticationError("JWT validation failed", details={"error": str(exc)}) from exc

        return claims

    async def _get_key(self, kid: str) -> Optional[Dict[str, Any]]:
        """Fetch the JWKS and return the key matching the provided kid."""
        await self._refresh_keys(force=False)
        for key in self._keys or []:
            if key.get("kid") == kid:
                return key

        # Key might be rotated; refresh once more eagerly.
        await self._refresh_keys(force=True)
        for key in self._keys or []:
            if key.get("kid") == kid:
                return key
        return None

    async def _refresh_keys(self, *, force: bool) -> None:
        """Refresh the JWKS if the cache is stale."""
        now = time.time()
        if not force and self._keys is not None and (now - self._last_refresh) < self.refresh_interval:
            return

        async with self._lock:
            if not force and self._keys is not None and (time.time() - self._last_refresh) < self.refresh_interval:
                return

            response = await self._client.get(self.jwks_url)
            response.raise_for_status()
            payload = response.json()
            keys = payload.get("keys")
            if not isinstance(keys, list):
                raise AuthenticationError("JWKS response missing 'keys' array")

            self._keys = keys
            self._last_refresh = time.time()

    def _extract_roles(self, claims: Dict[str, Any]) -> Set[str]:
        """Extract roles from common Keycloak token structures."""
        roles: Set[str] = set()

        direct_roles = claims.get("roles")
        if isinstance(direct_roles, list):
            roles.update(role for role in direct_roles if isinstance(role, str))

        scope = claims.get("scope")
        if isinstance(scope, str):
            roles.update(scope.split())

        realm_access = claims.get("realm_access", {})
        if isinstance(realm_access, dict):
            realm_roles = realm_access.get("roles")
            if isinstance(realm_roles, list):
                roles.update(role for role in realm_roles if isinstance(role, str))

        resource_access = claims.get("resource_access", {})
        if isinstance(resource_access, dict):
            for resource in resource_access.values():
                if isinstance(resource, dict):
                    resource_roles = resource.get("roles")
                    if isinstance(resource_roles, list):
                        roles.update(role for role in resource_roles if isinstance(role, str))

        return roles

    def _resolve_tenant_id(self, request: Request, claims: Dict[str, Any]) -> str:
        """Resolve the tenant identifier with header override support."""
        header_tenant = request.headers.get("X-Tenant-ID") or request.headers.get("X-Tenant")
        if isinstance(header_tenant, str) and header_tenant.strip():
            return header_tenant.strip()

        for claim_key in ("tenant_id", "tenant", "custom:tenantId", "custom:tenant_id"):
            claim_value = claims.get(claim_key)
            if isinstance(claim_value, str) and claim_value.strip():
                return claim_value.strip()

        return "default"
