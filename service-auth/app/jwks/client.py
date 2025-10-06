"""
JWKS client for Keycloak integration.
"""

import time
import httpx
from typing import Dict, Any, Optional
from jose import jwt, jwk
from jose.exceptions import JWTError
import json
import sys
import os

# Add shared directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from shared.logging import get_logger
from shared.circuit_breaker import circuit_breaker_manager


class JWKSClient:
    """Client for fetching and caching JWKS from Keycloak."""
    
    def __init__(self, jwks_url: str, cache_ttl: int = 3600):
        self.jwks_url = jwks_url
        self.cache_ttl = cache_ttl
        self.logger = get_logger("auth.jwks")
        
        # Cache for JWKS
        self._jwks_cache: Optional[Dict[str, Any]] = None
        self._cache_timestamp: float = 0
        
        # Cache for individual keys
        self._key_cache: Dict[str, Any] = {}
        
        # Circuit breaker for Keycloak calls
        self.circuit_breaker = circuit_breaker_manager.get_breaker(
            "keycloak-jwks",
            failure_threshold=5,
            recovery_timeout=30,
            expected_exception=httpx.HTTPError
        )
    
    async def get_jwks(self) -> Dict[str, Any]:
        """Get JWKS from cache or fetch from Keycloak."""
        current_time = time.time()
        
        # Check if cache is valid
        if (self._jwks_cache is not None and 
            current_time - self._cache_timestamp < self.cache_ttl):
            return self._jwks_cache
        
        # Fetch fresh JWKS with circuit breaker
        try:
            async def _fetch_jwks():
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(self.jwks_url)
                    response.raise_for_status()
                    return response.json()
            
            jwks_data = await self.circuit_breaker.call(_fetch_jwks)
            
            self._jwks_cache = jwks_data
            self._cache_timestamp = current_time
            
            self.logger.info(
                "JWKS refreshed successfully",
                keys_count=len(self._jwks_cache.get("keys", []))
            )
            
            return self._jwks_cache
                
        except Exception as e:
            self.logger.error("Failed to fetch JWKS", error=str(e))
            # Return cached data if available, even if stale
            if self._jwks_cache is not None:
                self.logger.warning("Using stale JWKS cache due to fetch failure")
                return self._jwks_cache
            raise
    
    async def get_key(self, kid: str) -> Optional[Dict[str, Any]]:
        """Get a specific key by key ID."""
        # Check key cache first
        if kid in self._key_cache:
            return self._key_cache[kid]
        
        # Get JWKS
        jwks = await self.get_jwks()
        
        # Find the key
        for key in jwks.get("keys", []):
            if key.get("kid") == kid:
                self._key_cache[kid] = key
                return key
        
        self.logger.warning("Key not found", kid=kid)
        return None
    
    async def verify_token(self, token: str) -> Dict[str, Any]:
        """Verify JWT token and return claims."""
        try:
            # Decode header to get key ID
            unverified_header = jwt.get_unverified_header(token)
            kid = unverified_header.get("kid")
            
            if not kid:
                raise JWTError("Token missing key ID")
            
            # Get the key
            key_data = await self.get_key(kid)
            if not key_data:
                raise JWTError(f"Key not found: {kid}")
            
            # Convert JWK to RSA key
            rsa_key = jwk.construct(key_data)
            
            # Verify and decode token
            payload = jwt.decode(
                token,
                rsa_key,
                algorithms=["RS256"],
                options={"verify_exp": True, "verify_aud": False}
            )
            
            self.logger.info(
                "Token verified successfully",
                sub=payload.get("sub"),
                tenant_id=payload.get("tenant_id")
            )
            
            return payload
            
        except JWTError as e:
            self.logger.warning("Token verification failed", error=str(e))
            raise
        except Exception as e:
            self.logger.error("Unexpected error during token verification", error=str(e))
            raise JWTError(f"Token verification failed: {str(e)}")
    
    def clear_cache(self):
        """Clear all caches."""
        self._jwks_cache = None
        self._cache_timestamp = 0
        self._key_cache.clear()
        self.logger.info("JWKS cache cleared")
