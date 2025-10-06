"""
Entitlements service client for Gateway.
"""

import httpx
from typing import Dict, Any, Optional
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
        self.entitlements_service_url = entitlements_service_url
        self.logger = get_logger("gateway.entitlements_client")
        self.circuit_breaker = get_circuit_breaker(
            "entitlements_service",
            failure_threshold=3,
            recovery_timeout=30.0
        )

        # Configure retry for entitlements service calls
        self.retry_config = RetryConfig(
            max_attempts=3,
            base_delay=1.0,
            max_delay=10.0,
            exponential_base=2.0,
            jitter=True
        )
    
    @retry_on_exception((httpx.HTTPError, httpx.ConnectError), config=RetryConfig(max_attempts=3, base_delay=1.0))
    async def check_entitlement(self, user_id: str, tenant_id: str, action: str,
                               resource_type: str, resource_id: Optional[str] = None,
                               context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Check entitlement with Entitlements service."""
        async def _check_entitlement():
            payload = {
                "user_id": user_id,
                "tenant_id": tenant_id,
                "action": action,
                "resource_type": resource_type,
                "context": context or {}
            }

            if resource_id:
                payload["resource_id"] = resource_id

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.entitlements_service_url}/entitlements/check",
                    json=payload
                )

                if response.status_code == 200:
                    result = response.json()
                    if result.get("allowed"):
                        return result
                    else:
                        raise AuthorizationError(
                            f"Access denied: {result.get('reason')}",
                            details={"entitlement_error": result.get("reason")}
                        )
                else:
                    raise AuthorizationError(
                        f"Entitlements service error: {response.status_code}",
                        details={"status_code": response.status_code}
                    )

        try:
            return await self.circuit_breaker.call(_check_entitlement)

        except httpx.HTTPError as e:
            self.logger.error("Entitlements service HTTP error", error=str(e))
            raise AuthorizationError(
                "Entitlements service unavailable",
                details={"http_error": str(e)}
            )
        except Exception as e:
            self.logger.error("Entitlements service error", error=str(e))
            raise AuthorizationError(
                f"Entitlements service error: {str(e)}",
                details={"error": str(e)}
            )
