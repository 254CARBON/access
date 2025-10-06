"""
Token validation service for Auth service.
"""

from typing import Dict, Any, Optional
from pydantic import BaseModel
import sys
import os

# Add shared directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from shared.logging import get_logger
from shared.errors import AuthenticationError
from ..jwks.client import JWKSClient


class TokenVerificationRequest(BaseModel):
    """Request model for token verification."""
    token: str


class TokenVerificationResponse(BaseModel):
    """Response model for token verification."""
    valid: bool
    claims: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class TokenRefreshResponse(BaseModel):
    """Response model for token refresh."""
    valid: bool
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    expires_in: Optional[int] = None
    token_type: str = "Bearer"
    error: Optional[str] = None


class TokenValidator:
    """Token validation service."""
    
    def __init__(self, jwks_url: str):
        self.jwks_client = JWKSClient(jwks_url)
        self.logger = get_logger("auth.validator")
    
    async def verify_token(self, token: str) -> TokenVerificationResponse:
        """Verify a JWT token."""
        try:
            # Remove Bearer prefix if present
            if token.startswith("Bearer "):
                token = token[7:]
            
            # Verify token
            claims = await self.jwks_client.verify_token(token)
            
            return TokenVerificationResponse(
                valid=True,
                claims=claims
            )
            
        except Exception as e:
            self.logger.warning("Token verification failed", error=str(e))
            return TokenVerificationResponse(
                valid=False,
                error=str(e)
            )
    
    async def extract_claims(self, token: str) -> Dict[str, Any]:
        """Extract claims from a valid token."""
        response = await self.verify_token(token)
        
        if not response.valid:
            raise AuthenticationError(
                f"Invalid token: {response.error}",
                details={"token_error": response.error}
            )
        
        return response.claims
    
    async def get_user_info(self, token: str) -> Dict[str, Any]:
        """Get user information from token claims."""
        claims = await self.extract_claims(token)
        
        return {
            "user_id": claims.get("sub"),
            "tenant_id": claims.get("tenant_id"),
            "email": claims.get("email"),
            "username": claims.get("preferred_username"),
            "roles": claims.get("realm_access", {}).get("roles", []),
            "client_roles": claims.get("resource_access", {}),
            "exp": claims.get("exp"),
            "iat": claims.get("iat")
        }
    
    async def refresh_token(self, refresh_token: str) -> TokenRefreshResponse:
        """Refresh an access token using refresh token."""
        try:
            # Remove Bearer prefix if present
            if refresh_token.startswith("Bearer "):
                refresh_token = refresh_token[7:]
            
            # Verify refresh token
            claims = await self.jwks_client.verify_token(refresh_token)
            
            # Check if it's a refresh token
            if claims.get("typ") != "Refresh":
                raise AuthenticationError("Invalid refresh token type")
            
            # Extract user ID from refresh token
            user_id = claims.get("sub")
            if not user_id:
                raise AuthenticationError("Refresh token missing user ID")
            
            # Get user info from Keycloak
            user_info = await self.get_user_by_id(user_id)
            if not user_info:
                raise AuthenticationError("User not found")
            
            # Generate new token pair (in real implementation, this would call Keycloak)
            new_tokens = await self._generate_new_tokens(user_info)
            
            return TokenRefreshResponse(
                valid=True,
                access_token=new_tokens["access_token"],
                refresh_token=new_tokens["refresh_token"],
                expires_in=new_tokens["expires_in"],
                token_type="Bearer"
            )
            
        except Exception as e:
            self.logger.warning("Token refresh failed", error=str(e))
            return TokenRefreshResponse(
                valid=False,
                error=str(e)
            )
    
    async def revoke_token(self, token: str) -> bool:
        """Revoke a token (logout)."""
        try:
            # Extract user info from token
            user_info = await self.get_user_info(token)
            user_id = user_info.get("user_id")
            
            if not user_id:
                return False
            
            # In real implementation, this would call Keycloak logout endpoint
            # For now, we just log the revocation
            self.logger.info(
                "Token revoked",
                user_id=user_id,
                tenant_id=user_info.get("tenant_id")
            )
            
            return True
            
        except Exception as e:
            self.logger.error("Token revocation failed", error=str(e))
            return False
    
    async def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user information by user ID from Keycloak."""
        try:
            # In real implementation, this would call Keycloak user info endpoint
            # For now, return mock user data
            mock_users = {
                "user1": {
                    "id": "user1",
                    "username": "john.doe",
                    "email": "john.doe@254carbon.com",
                    "tenant_id": "tenant-1",
                    "roles": ["user", "analyst"],
                    "created_at": "2024-01-01T00:00:00Z",
                    "updated_at": "2024-01-01T00:00:00Z"
                },
                "user2": {
                    "id": "user2",
                    "username": "jane.smith",
                    "email": "jane.smith@254carbon.com",
                    "tenant_id": "tenant-2",
                    "roles": ["user", "admin"],
                    "created_at": "2024-01-01T00:00:00Z",
                    "updated_at": "2024-01-01T00:00:00Z"
                },
                "admin": {
                    "id": "admin",
                    "username": "admin",
                    "email": "admin@254carbon.com",
                    "tenant_id": "tenant-1",
                    "roles": ["admin", "superuser"],
                    "created_at": "2024-01-01T00:00:00Z",
                    "updated_at": "2024-01-01T00:00:00Z"
                }
            }
            
            return mock_users.get(user_id)
            
        except Exception as e:
            self.logger.error("Failed to get user by ID", user_id=user_id, error=str(e))
            return None
    
    async def _generate_new_tokens(self, user_info: Dict[str, Any]) -> Dict[str, Any]:
        """Generate new access and refresh tokens."""
        # In real implementation, this would call Keycloak token endpoint
        # For now, return mock tokens
        import time
        from datetime import datetime, timedelta
        
        now = datetime.utcnow()
        expires_in = 3600  # 1 hour
        
        # Mock token generation
        access_token = f"mock_access_token_{user_info['id']}_{int(now.timestamp())}"
        refresh_token = f"mock_refresh_token_{user_info['id']}_{int(now.timestamp())}"
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_in": expires_in
        }
