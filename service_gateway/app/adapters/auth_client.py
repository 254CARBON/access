"""
Auth service client for Gateway.
"""

import httpx
from typing import Dict, Any, Optional
import sys
import os

# Add shared directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..'))

import httpx
from shared.logging import get_logger
from shared.errors import AuthenticationError
from shared.circuit_breaker import get_circuit_breaker
from shared.retry import retry_on_exception, RetryConfig


class AuthClient:
    """Client for communicating with Auth service."""
    
    def __init__(self, auth_service_url: str):
        self.auth_service_url = auth_service_url
        self.logger = get_logger("gateway.auth_client")
        self.circuit_breaker = get_circuit_breaker(
            "auth_service",
            failure_threshold=3,
            recovery_timeout=30.0
        )

        # Configure retry for auth service calls
        self.retry_config = RetryConfig(
            max_attempts=3,
            base_delay=1.0,
            max_delay=10.0,
            exponential_base=2.0,
            jitter=True
        )
    
    @retry_on_exception((httpx.HTTPError, httpx.ConnectError), config=RetryConfig(max_attempts=3, base_delay=1.0))
    async def verify_token(self, token: str) -> Dict[str, Any]:
        """Verify JWT token with Auth service."""
        async def _verify_token():
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.auth_service_url}/auth/verify",
                    json={"token": token}
                )

                if response.status_code == 200:
                    result = response.json()
                    if result.get("valid"):
                        return result
                    else:
                        raise AuthenticationError(
                            f"Token validation failed: {result.get('error')}",
                            details={"auth_error": result.get("error")}
                        )
                else:
                    raise AuthenticationError(
                        f"Auth service error: {response.status_code}",
                        details={"status_code": response.status_code}
                    )

        try:
            return await self.circuit_breaker.call(_verify_token)

        except httpx.HTTPError as e:
            self.logger.error("Auth service HTTP error", error=str(e))
            raise AuthenticationError(
                "Auth service unavailable",
                details={"http_error": str(e)}
            )
        except Exception as e:
            self.logger.error("Auth service error", error=str(e))
            raise AuthenticationError(
                f"Auth service error: {str(e)}",
                details={"error": str(e)}
            )
    
    async def get_user_info(self, token: str) -> Dict[str, Any]:
        """Get user information from token."""
        result = await self.verify_token(token)
        return result.get("user_info", {})
