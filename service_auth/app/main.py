"""
Auth service for 254Carbon Access Layer.
"""

import sys
import os
import time
import asyncio

# Add shared directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from shared.base_service import BaseService
from shared.observability import get_observability_manager, observe_function, observe_operation
from .validation.token_validator import TokenValidator, TokenVerificationRequest


class AuthService(BaseService):
    """Auth service implementation."""
    
    def __init__(self):
        super().__init__("auth", 8010)
        self.token_validator = TokenValidator(self.config.jwks_url)
        
        # Initialize observability
        self.observability = get_observability_manager(
            "auth",
            log_level=self.config.log_level,
            otel_exporter=self.config.otel_exporter,
            enable_console=self.config.enable_console_tracing
        )
        
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
        @observe_function("auth_verify_token")
        async def verify_token(request: TokenVerificationRequest):
            """Token verification endpoint."""
            start_time = time.time()
            
            try:
                response = await self.token_validator.verify_token(request.token)
                
                if response.valid:
                    user_info = await self.token_validator.get_user_info(request.token)
                    
                    # Set user context for logging
                    self.observability.trace_request(
                        user_id=user_info.get("user_id"),
                        tenant_id=user_info.get("tenant_id")
                    )
                    
                    # Log successful verification
                    self.observability.log_business_event(
                        "token_verified",
                        user_id=user_info.get("user_id"),
                        tenant_id=user_info.get("tenant_id")
                    )
                    
                    return {
                        "valid": True,
                        "claims": response.claims,
                        "user_info": user_info
                    }
                else:
                    # Log failed verification
                    self.observability.log_error(
                        "token_verification_failed",
                        response.error
                    )
                    
                    return {
                        "valid": False,
                        "error": response.error
                    }
            except Exception as e:
                duration = time.time() - start_time
                self.observability.log_error(
                    "token_verification_error",
                    str(e),
                    duration=duration
                )
                return {
                    "valid": False,
                    "error": str(e)
                }
        
        @self.app.post("/auth/verify-ws")
        @observe_function("auth_verify_websocket_token")
        async def verify_websocket_token(request: TokenVerificationRequest):
            """WebSocket token verification endpoint."""
            start_time = time.time()
            
            try:
                response = await self.token_validator.verify_token(request.token)
                
                if response.valid:
                    user_info = await self.token_validator.get_user_info(request.token)
                    
                    # Set user context for logging
                    self.observability.trace_request(
                        user_id=user_info.get("user_id"),
                        tenant_id=user_info.get("tenant_id")
                    )
                    
                    # Log successful WebSocket verification
                    self.observability.log_business_event(
                        "websocket_token_verified",
                        user_id=user_info.get("user_id"),
                        tenant_id=user_info.get("tenant_id")
                    )
                    
                    return {
                        "valid": True,
                        "claims": response.claims,
                        "user_info": user_info
                    }
                else:
                    # Log failed verification
                    self.observability.log_error(
                        "websocket_token_verification_failed",
                        response.error
                    )
                    
                    return {
                        "valid": False,
                        "error": response.error
                    }
            except Exception as e:
                duration = time.time() - start_time
                self.observability.log_error(
                    "websocket_token_verification_error",
                    str(e),
                    duration=duration
                )
                return {
                    "valid": False,
                    "error": str(e)
                }
        
        @self.app.post("/auth/refresh")
        @observe_function("auth_refresh_token")
        async def refresh_token(request: TokenVerificationRequest):
            """Token refresh endpoint."""
            start_time = time.time()
            
            try:
                response = await self.token_validator.refresh_token(request.token)
                
                if response.valid:
                    user_info = await self.token_validator.get_user_info(response.access_token)
                    
                    # Set user context for logging
                    self.observability.trace_request(
                        user_id=user_info.get("user_id"),
                        tenant_id=user_info.get("tenant_id")
                    )
                    
                    # Log successful refresh
                    self.observability.log_business_event(
                        "token_refreshed",
                        user_id=user_info.get("user_id"),
                        tenant_id=user_info.get("tenant_id")
                    )
                    
                    return {
                        "valid": True,
                        "access_token": response.access_token,
                        "refresh_token": response.refresh_token,
                        "expires_in": response.expires_in,
                        "token_type": response.token_type,
                        "user_info": user_info
                    }
                else:
                    # Log failed refresh
                    self.observability.log_error(
                        "token_refresh_failed",
                        response.error
                    )
                    
                    return {
                        "valid": False,
                        "error": response.error
                    }
            except Exception as e:
                duration = time.time() - start_time
                self.observability.log_error(
                    "token_refresh_error",
                    str(e),
                    duration=duration
                )
                return {
                    "valid": False,
                    "error": str(e)
                }
        
        @self.app.post("/auth/logout")
        @observe_function("auth_logout")
        async def logout(request: TokenVerificationRequest):
            """Token logout/revocation endpoint."""
            start_time = time.time()
            
            try:
                # Extract user info from token before revoking
                user_info = await self.token_validator.get_user_info(request.token)
                
                # Set user context for logging
                self.observability.trace_request(
                    user_id=user_info.get("user_id"),
                    tenant_id=user_info.get("tenant_id")
                )
                
                # Revoke token (in real implementation, this would call Keycloak)
                await self.token_validator.revoke_token(request.token)
                
                # Log successful logout
                self.observability.log_business_event(
                    "user_logged_out",
                    user_id=user_info.get("user_id"),
                    tenant_id=user_info.get("tenant_id")
                )
                
                return {
                    "success": True,
                    "message": "Logged out successfully"
                }
            except Exception as e:
                duration = time.time() - start_time
                self.observability.log_error(
                    "logout_error",
                    str(e),
                    duration=duration
                )
                return {
                    "success": False,
                    "error": str(e)
                }
        
        @self.app.get("/auth/users/{user_id}")
        @observe_function("auth_get_user_info")
        async def get_user_info(user_id: str):
            """Get user information by user ID."""
            start_time = time.time()
            
            try:
                user_info = await self.token_validator.get_user_by_id(user_id)
                
                if user_info:
                    # Set user context for logging
                    self.observability.trace_request(
                        user_id=user_id,
                        tenant_id=user_info.get("tenant_id")
                    )
                    
                    # Log successful user info retrieval
                    self.observability.log_business_event(
                        "user_info_retrieved",
                        user_id=user_id,
                        tenant_id=user_info.get("tenant_id")
                    )
                    
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
                    # Log user not found
                    self.observability.log_error(
                        "user_not_found",
                        f"User {user_id} not found"
                    )
                    
                    return {
                        "error": "User not found"
                    }
            except Exception as e:
                duration = time.time() - start_time
                self.observability.log_error(
                    "get_user_info_error",
                    str(e),
                    duration=duration,
                    user_id=user_id
                )
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
