"""
Authentication middleware for Gateway.
"""

from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Dict, Any, Optional
import sys
import os

# Add shared directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from shared.logging import get_logger
from shared.errors import AuthenticationError, AuthorizationError
from adapters.auth_client import AuthClient
from adapters.entitlements_client import EntitlementsClient


class AuthMiddleware:
    """Authentication middleware for Gateway."""
    
    def __init__(self, auth_client: AuthClient, entitlements_client: EntitlementsClient):
        self.auth_client = auth_client
        self.entitlements_client = entitlements_client
        self.logger = get_logger("gateway.auth_middleware")
        self.security = HTTPBearer(auto_error=False)
    
    async def authenticate_request(self, request: Request) -> Dict[str, Any]:
        """Authenticate incoming request with JWT token or API key fallback."""
        # Check for API key first
        api_key = request.headers.get("X-API-Key")
        if api_key:
            user_info = await self._authenticate_with_api_key(api_key)
            
            try:
                request.state.user_info = user_info
            except AttributeError:
                pass
            
            return user_info
        
        # Fall back to JWT token authentication
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            raise HTTPException(
                status_code=401,
                detail="Authorization header or X-API-Key header required"
            )
        
        if not auth_header.startswith("Bearer "):
            raise HTTPException(
                status_code=401,
                detail="Invalid authorization header format"
            )
        
        token = auth_header[7:]  # Remove "Bearer " prefix
        
        # Verify token with Auth service
        try:
            auth_result = await self.auth_client.verify_token(token)
            user_info = auth_result.get("user_info", {})
            
            self.logger.info(
                "Request authenticated with JWT",
                user_id=user_info.get("user_id"),
                tenant_id=user_info.get("tenant_id")
            )
            
            try:
                request.state.user_info = user_info
            except AttributeError:
                # FastAPI ensures state exists, but guard defensively
                pass
            
            return user_info
            
        except AuthenticationError as e:
            self.logger.warning("JWT authentication failed", error=str(e))
            raise HTTPException(
                status_code=401,
                detail=str(e)
            )
    
    async def _authenticate_with_api_key(self, api_key: str) -> Dict[str, Any]:
        """Authenticate with API key."""
        # Mock API key validation (in real implementation, this would check a database)
        api_keys = {
            "dev-key-123": {"tenant_id": "tenant-1", "roles": ["user"]},
            "admin-key-456": {"tenant_id": "tenant-1", "roles": ["admin"]},
            "service-key-789": {"tenant_id": "*", "roles": ["service"]}
        }
        
        if api_key not in api_keys:
            raise HTTPException(
                status_code=401,
                detail="Invalid API key"
            )
        
        api_key_info = api_keys[api_key]
        
        user_info = {
            "user_id": f"api-key-{api_key}",
            "tenant_id": api_key_info["tenant_id"],
            "roles": api_key_info["roles"],
            "auth_method": "api_key"
        }
        
        self.logger.info(
            "Request authenticated with API key",
            api_key=api_key[:8] + "...",
            tenant_id=api_key_info["tenant_id"]
        )

        return user_info
    
    async def authorize_request(self, user_info: Dict[str, Any], action: str,
                               resource_type: str, resource_id: Optional[str] = None) -> bool:
        """Authorize request based on user entitlements."""
        try:
            await self.entitlements_client.check_entitlement(
                user_id=user_info["user_id"],
                tenant_id=user_info["tenant_id"],
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                context={"roles": user_info.get("roles", [])}
            )
            
            self.logger.info(
                "Request authorized",
                user_id=user_info["user_id"],
                action=action,
                resource_type=resource_type
            )
            
            return True
            
        except AuthorizationError as e:
            self.logger.warning("Authorization failed", error=str(e))
            raise HTTPException(
                status_code=403,
                detail=str(e)
            )
    
    async def process_request(self, request: Request, action: str, resource_type: str,
                             resource_id: Optional[str] = None) -> Dict[str, Any]:
        """Process request with authentication and authorization."""
        # Authenticate
        user_info = await self.authenticate_request(request)
        
        # Authorize
        await self.authorize_request(user_info, action, resource_type, resource_id)
        
        return user_info


# Dependency function for FastAPI
async def get_current_user(
    request: Request,
    auth_client: AuthClient,
    entitlements_client: EntitlementsClient
) -> Dict[str, Any]:
    """FastAPI dependency for getting current user."""
    middleware = AuthMiddleware(auth_client, entitlements_client)
    return await middleware.authenticate_request(request)
