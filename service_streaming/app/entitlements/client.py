"""
Entitlements client for Streaming Service.
"""

from typing import Any, Dict, Optional
import httpx
import sys
import os

# Add shared directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from shared.logging import get_logger
from shared.errors import AuthorizationError
from shared.circuit_breaker import get_circuit_breaker
from shared.retry import retry_on_exception, RetryConfig


class EntitlementsClient:
    """Client for communicating with Entitlements service."""

    def __init__(self, entitlements_service_url: str):
        self.base_url = entitlements_service_url.rstrip('/')
        self.logger = get_logger("streaming.entitlements.client")

        self.circuit_breaker = get_circuit_breaker(
            "entitlements_service",
            failure_threshold=3,
            recovery_timeout=30.0
        )

        self.retry_config = RetryConfig(
            max_attempts=3,
            base_delay=0.5,
            max_delay=5.0,
            exponential_base=2.0,
            jitter=True
        )

    @retry_on_exception((httpx.HTTPError, httpx.ConnectError), config=RetryConfig(max_attempts=3, base_delay=0.5))
    async def check_access(
        self,
        user_id: str,
        tenant_id: str,
        resource: str,
        action: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Check streaming entitlement."""

        payload = {
            "user_id": user_id,
            "tenant_id": tenant_id,
            "resource": resource,
            "action": action,
            "context": context or {}
        }

        async def _request():
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(f"{self.base_url}/entitlements/check", json=payload)

            if response.status_code == 200:
                data = response.json()
                if data.get("allowed"):
                    return data

                raise AuthorizationError(
                    message=data.get("reason", "Access denied"),
                    details={"resource": resource, "action": action}
                )

            self.logger.error(
                "Entitlements service error",
                status_code=response.status_code,
                body=response.text
            )
            raise AuthorizationError(
                message="Entitlements service error",
                details={"status_code": response.status_code}
            )

        try:
            return await self.circuit_breaker.call(_request)
        except AuthorizationError:
            raise
        except Exception as exc:
            self.logger.error("Entitlements request failed", error=str(exc))
            raise AuthorizationError(
                message="Entitlements service unavailable",
                details={"error": str(exc)}
            )
