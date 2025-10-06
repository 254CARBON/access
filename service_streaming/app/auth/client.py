"""
Auth client for Streaming Service.
"""

import httpx
from typing import Dict, Any, Optional
import sys
import os

# Add shared directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from shared.logging import get_logger
from shared.errors import AccessLayerException


class AuthClient:
    """Client for communicating with Auth Service."""
    
    def __init__(self, auth_service_url: str):
        self.auth_service_url = auth_service_url.rstrip('/')
        self.logger = get_logger("streaming.auth.client")
        self.timeout = 5.0
    
    async def verify_token(self, token: str) -> Dict[str, Any]:
        """Verify a JWT token."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.auth_service_url}/auth/verify",
                    json={"token": token}
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    self.logger.warning(
                        "Token verification failed",
                        status_code=response.status_code,
                        response=response.text
                    )
                    return {"valid": False, "error": "Token verification failed"}
                    
        except httpx.TimeoutException:
            self.logger.error("Auth service timeout")
            raise AccessLayerException("AUTH_SERVICE_TIMEOUT", "Auth service timeout")
        except httpx.RequestError as e:
            self.logger.error("Auth service request error", error=str(e))
            raise AccessLayerException("AUTH_SERVICE_ERROR", "Auth service unavailable")
        except Exception as e:
            self.logger.error("Unexpected auth error", error=str(e))
            raise AccessLayerException("AUTH_ERROR", "Authentication error")
    
    async def verify_websocket_token(self, token: str) -> Dict[str, Any]:
        """Verify a JWT token for WebSocket connection."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.auth_service_url}/auth/verify-ws",
                    json={"token": token}
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    self.logger.warning(
                        "WebSocket token verification failed",
                        status_code=response.status_code,
                        response=response.text
                    )
                    return {"valid": False, "error": "WebSocket token verification failed"}
                    
        except httpx.TimeoutException:
            self.logger.error("Auth service timeout")
            raise AccessLayerException("AUTH_SERVICE_TIMEOUT", "Auth service timeout")
        except httpx.RequestError as e:
            self.logger.error("Auth service request error", error=str(e))
            raise AccessLayerException("AUTH_SERVICE_ERROR", "Auth service unavailable")
        except Exception as e:
            self.logger.error("Unexpected auth error", error=str(e))
            raise AccessLayerException("AUTH_ERROR", "Authentication error")
    
    async def health_check(self) -> bool:
        """Check if auth service is healthy."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"{self.auth_service_url}/health")
                return response.status_code == 200
        except Exception:
            return False
