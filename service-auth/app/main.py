"""
Auth service for 254Carbon Access Layer.
"""

import sys
import os

# Add shared directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from shared.base_service import BaseService
from .validation.token_validator import TokenValidator, TokenVerificationRequest


class AuthService(BaseService):
    """Auth service implementation."""
    
    def __init__(self):
        super().__init__("auth", 8010)
        self.token_validator = TokenValidator(self.config.jwks_url)
        self._setup_auth_routes()
    
    def _setup_auth_routes(self):
        """Set up auth-specific routes."""
        
        @self.app.get("/")
        async def root():
            """Root endpoint."""
            return {
                "service": "auth",
                "message": "254Carbon Access Layer - Auth Service",
                "version": "1.0.0"
            }
        
        @self.app.post("/auth/verify")
        async def verify_token(request: TokenVerificationRequest):
            """Token verification endpoint."""
            try:
                response = await self.token_validator.verify_token(request.token)
                
                if response.valid:
                    return {
                        "valid": True,
                        "claims": response.claims,
                        "user_info": await self.token_validator.get_user_info(request.token)
                    }
                else:
                    return {
                        "valid": False,
                        "error": response.error
                    }
            except Exception as e:
                self.logger.error("Token verification error", error=str(e))
                return {
                    "valid": False,
                    "error": str(e)
                }
        
        @self.app.post("/auth/verify-ws")
        async def verify_websocket_token(request: TokenVerificationRequest):
            """WebSocket token verification endpoint."""
            try:
                response = await self.token_validator.verify_token(request.token)
                
                if response.valid:
                    return {
                        "valid": True,
                        "claims": response.claims,
                        "user_info": await self.token_validator.get_user_info(request.token)
                    }
                else:
                    return {
                        "valid": False,
                        "error": response.error
                    }
            except Exception as e:
                self.logger.error("WebSocket token verification error", error=str(e))
                return {
                    "valid": False,
                    "error": str(e)
                }
        
        @self.app.post("/auth/refresh")
        async def refresh_token(request: TokenVerificationRequest):
            """Token refresh endpoint."""
            try:
                response = await self.token_validator.refresh_token(request.token)
                
                if response.valid:
                    return {
                        "valid": True,
                        "access_token": response.access_token,
                        "refresh_token": response.refresh_token,
                        "expires_in": response.expires_in,
                        "token_type": response.token_type,
                        "user_info": await self.token_validator.get_user_info(response.access_token)
                    }
                else:
                    return {
                        "valid": False,
                        "error": response.error
                    }
            except Exception as e:
                self.logger.error("Token refresh error", error=str(e))
                return {
                    "valid": False,
                    "error": str(e)
                }
        
        @self.app.post("/auth/logout")
        async def logout(request: TokenVerificationRequest):
            """Token logout/revocation endpoint."""
            try:
                # Extract user info from token before revoking
                user_info = await self.token_validator.get_user_info(request.token)
                
                # Revoke token (in real implementation, this would call Keycloak)
                await self.token_validator.revoke_token(request.token)
                
                self.logger.info(
                    "User logged out successfully",
                    user_id=user_info.get("user_id"),
                    tenant_id=user_info.get("tenant_id")
                )
                
                return {
                    "success": True,
                    "message": "Logged out successfully"
                }
            except Exception as e:
                self.logger.error("Logout error", error=str(e))
                return {
                    "success": False,
                    "error": str(e)
                }
        
        @self.app.get("/auth/users/{user_id}")
        async def get_user_info(user_id: str):
            """Get user information by user ID."""
            try:
                user_info = await self.token_validator.get_user_by_id(user_id)
                
                if user_info:
                    return {
                        "user_id": user_info.get("id"),
                        "username": user_info.get("username"),
                        "email": user_info.get("email"),
                        "tenant_id": user_info.get("tenant_id"),
                        "roles": user_info.get("roles", []),
                        "created_at": user_info.get("created_at"),
                        "updated_at": user_info.get("updated_at")
                    }
                else:
                    return {
                        "error": "User not found"
                    }
            except Exception as e:
                self.logger.error("Get user info error", error=str(e))
                return {
                    "error": str(e)
                }
    
    async def _check_dependencies(self):
        """Check auth dependencies."""
        dependencies = {}
        
        # Check Keycloak JWKS endpoint
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                response = await client.get(self.config.jwks_url, timeout=5.0)
                if response.status_code == 200:
                    dependencies["keycloak"] = "ok"
                else:
                    dependencies["keycloak"] = "error"
        except Exception:
            dependencies["keycloak"] = "error"
        
        return dependencies


def create_app():
    """Create FastAPI application."""
    service = AuthService()
    return service.app


if __name__ == "__main__":
    service = AuthService()
    service.run()
