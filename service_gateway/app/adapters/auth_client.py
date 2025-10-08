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
                    if not result.get("valid"):
                        self.logger.warning(
                            "Token validation failed",
                            error=result.get("error")
                        )
                    return result
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
    
    @retry_on_exception((httpx.HTTPError, httpx.ConnectError), config=RetryConfig(max_attempts=3, base_delay=1.0))
    async def verify_websocket_token(self, token: str) -> Dict[str, Any]:
        """Verify a JWT token for WebSocket connections."""

        async def _verify_token():
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.auth_service_url}/auth/verify-ws",
                    json={"token": token}
                )

                if response.status_code == 200:
                    return response.json()
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

    @retry_on_exception((httpx.HTTPError, httpx.ConnectError), config=RetryConfig(max_attempts=3, base_delay=1.0))
    async def get_user_info(self, user_id: str) -> Dict[str, Any]:
        """Retrieve user information from Auth service."""

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{self.auth_service_url}/auth/users/{user_id}"
            )

            if response.status_code == 200:
                return response.json()
            if response.status_code == 404:
                return {"error": "User not found"}
            raise AuthenticationError(
                f"Auth service error: {response.status_code}",
                details={"status_code": response.status_code}
            )
