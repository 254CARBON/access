"""
Mock Keycloak server providing JWKS and token validation endpoints.
"""

import json
import time
import jwt
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import sys
import os

# Add shared directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from shared.logging import get_logger


class MockKeycloakServer:
    """Mock Keycloak server implementation."""
    
    def __init__(self, port: int = 8080):
        self.port = port
        self.logger = get_logger("mock.keycloak")
        self.app = FastAPI(title="Mock Keycloak", version="1.0.0")
        
        # Mock configuration
        self.realm = "254carbon"
        self.client_id = "access-layer"
        self.issuer = f"http://localhost:{port}/realms/{self.realm}"
        
        # Mock users
        self.users = {
            "user1": {
                "sub": "user1",
                "preferred_username": "john.doe",
                "email": "john.doe@254carbon.com",
                "tenant_id": "tenant-1",
                "roles": ["user", "analyst"]
            },
            "user2": {
                "sub": "user2", 
                "preferred_username": "jane.smith",
                "email": "jane.smith@254carbon.com",
                "tenant_id": "tenant-2",
                "roles": ["user", "admin"]
            },
            "admin": {
                "sub": "admin",
                "preferred_username": "admin",
                "email": "admin@254carbon.com",
                "tenant_id": "tenant-1",
                "roles": ["admin", "superuser"]
            }
        }
        
        # Mock JWKS
        self.jwks = {
            "keys": [
                {
                    "kty": "RSA",
                    "kid": "mock-key-1",
                    "use": "sig",
                    "n": "mock-public-key-n",
                    "e": "AQAB",
                    "alg": "RS256"
                }
            ]
        }
        
        # Mock private key for signing (in real implementation, this would be secure)
        self.private_key = "mock-private-key"
        
        self._setup_routes()
    
    def _setup_routes(self):
        """Set up mock Keycloak routes."""
        
        @self.app.get("/")
        async def root():
            """Root endpoint."""
            return {
                "service": "mock-keycloak",
                "message": "Mock Keycloak server for 254Carbon Access Layer",
                "version": "1.0.0",
                "realm": self.realm,
                "issuer": self.issuer
            }
        
        @self.app.get("/realms/{realm}/.well-known/openid_configuration")
        async def openid_configuration(realm: str):
            """OpenID Connect configuration."""
            if realm != self.realm:
                raise HTTPException(status_code=404, detail="Realm not found")
            
            return {
                "issuer": self.issuer,
                "authorization_endpoint": f"{self.issuer}/protocol/openid-connect/auth",
                "token_endpoint": f"{self.issuer}/protocol/openid-connect/token",
                "userinfo_endpoint": f"{self.issuer}/protocol/openid-connect/userinfo",
                "jwks_uri": f"{self.issuer}/protocol/openid-connect/certs",
                "end_session_endpoint": f"{self.issuer}/protocol/openid-connect/logout",
                "grant_types_supported": ["authorization_code", "client_credentials", "refresh_token"],
                "response_types_supported": ["code"],
                "subject_types_supported": ["public"],
                "id_token_signing_alg_values_supported": ["RS256"],
                "scopes_supported": ["openid", "profile", "email"]
            }
        
        @self.app.get("/realms/{realm}/protocol/openid-connect/certs")
        async def jwks_endpoint(realm: str):
            """JWKS endpoint."""
            if realm != self.realm:
                raise HTTPException(status_code=404, detail="Realm not found")
            
            return self.jwks
        
        @self.app.post("/realms/{realm}/protocol/openid-connect/token")
        async def token_endpoint(
            realm: str,
            grant_type: str = Query(...),
            client_id: str = Query(...),
            username: Optional[str] = Query(None),
            password: Optional[str] = Query(None),
            refresh_token: Optional[str] = Query(None)
        ):
            """Token endpoint for authentication."""
            if realm != self.realm:
                raise HTTPException(status_code=404, detail="Realm not found")
            
            if client_id != self.client_id:
                raise HTTPException(status_code=400, detail="Invalid client")
            
            if grant_type == "password":
                return await self._handle_password_grant(username, password)
            elif grant_type == "refresh_token":
                return await self._handle_refresh_token(refresh_token)
            elif grant_type == "client_credentials":
                return await self._handle_client_credentials()
            else:
                raise HTTPException(status_code=400, detail="Unsupported grant type")
        
        @self.app.get("/realms/{realm}/protocol/openid-connect/userinfo")
        async def userinfo_endpoint(
            realm: str,
            credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer())
        ):
            """User info endpoint."""
            if realm != self.realm:
                raise HTTPException(status_code=404, detail="Realm not found")
            
            try:
                # Decode token to get user info
                token = credentials.credentials
                payload = jwt.decode(token, options={"verify_signature": False})
                
                user_id = payload.get("sub")
                if user_id not in self.users:
                    raise HTTPException(status_code=401, detail="Invalid user")
                
                user_info = self.users[user_id].copy()
                # Remove sensitive fields
                user_info.pop("sub", None)
                
                return user_info
                
            except jwt.InvalidTokenError:
                raise HTTPException(status_code=401, detail="Invalid token")
        
        @self.app.post("/realms/{realm}/protocol/openid-connect/logout")
        async def logout_endpoint(realm: str):
            """Logout endpoint."""
            if realm != self.realm:
                raise HTTPException(status_code=404, detail="Realm not found")
            
            return {"message": "Logged out successfully"}
        
        @self.app.get("/realms/{realm}/users")
        async def list_users(realm: str):
            """List users endpoint."""
            if realm != self.realm:
                raise HTTPException(status_code=404, detail="Realm not found")
            
            return {
                "users": [
                    {
                        "id": user_id,
                        "username": user_data["preferred_username"],
                        "email": user_data["email"],
                        "tenant_id": user_data["tenant_id"],
                        "roles": user_data["roles"]
                    }
                    for user_id, user_data in self.users.items()
                ]
            }
        
        @self.app.get("/realms/{realm}/users/{user_id}")
        async def get_user(realm: str, user_id: str):
            """Get user by ID."""
            if realm != self.realm:
                raise HTTPException(status_code=404, detail="Realm not found")
            
            if user_id not in self.users:
                raise HTTPException(status_code=404, detail="User not found")
            
            user_data = self.users[user_id].copy()
            user_data["id"] = user_id
            return user_data
    
    async def _handle_password_grant(self, username: Optional[str], password: Optional[str]) -> Dict[str, Any]:
        """Handle password grant type."""
        if not username or not password:
            raise HTTPException(status_code=400, detail="Username and password required")
        
        # Simple mock authentication
        if username == "john.doe" and password == "password123":
            user_id = "user1"
        elif username == "jane.smith" and password == "password123":
            user_id = "user2"
        elif username == "admin" and password == "admin123":
            user_id = "admin"
        else:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        return await self._generate_token_pair(user_id)
    
    async def _handle_refresh_token(self, refresh_token: Optional[str]) -> Dict[str, Any]:
        """Handle refresh token grant type."""
        if not refresh_token:
            raise HTTPException(status_code=400, detail="Refresh token required")
        
        try:
            # Decode refresh token to get user info
            payload = jwt.decode(refresh_token, options={"verify_signature": False})
            user_id = payload.get("sub")
            
            if user_id not in self.users:
                raise HTTPException(status_code=401, detail="Invalid refresh token")
            
            return await self._generate_token_pair(user_id)
            
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail="Invalid refresh token")
    
    async def _handle_client_credentials(self) -> Dict[str, Any]:
        """Handle client credentials grant type."""
        # Generate service account token
        now = datetime.utcnow()
        access_token_payload = {
            "iss": self.issuer,
            "sub": "service-account",
            "aud": self.client_id,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(hours=1)).timestamp()),
            "azp": self.client_id,
            "scope": "openid profile email",
            "realm_access": {
                "roles": ["service-account"]
            },
            "resource_access": {
                self.client_id: {
                    "roles": ["service-account"]
                }
            }
        }
        
        access_token = jwt.encode(access_token_payload, self.private_key, algorithm="HS256")
        
        return {
            "access_token": access_token,
            "expires_in": 3600,
            "refresh_expires_in": 0,
            "token_type": "Bearer",
            "not-before-policy": 0,
            "scope": "openid profile email"
        }
    
    async def _generate_token_pair(self, user_id: str) -> Dict[str, Any]:
        """Generate access and refresh token pair."""
        user_data = self.users[user_id]
        now = datetime.utcnow()
        
        # Access token payload
        access_token_payload = {
            "iss": self.issuer,
            "sub": user_id,
            "aud": self.client_id,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(hours=1)).timestamp()),
            "azp": self.client_id,
            "scope": "openid profile email",
            "preferred_username": user_data["preferred_username"],
            "email": user_data["email"],
            "tenant_id": user_data["tenant_id"],
            "realm_access": {
                "roles": user_data["roles"]
            },
            "resource_access": {
                self.client_id: {
                    "roles": user_data["roles"]
                }
            }
        }
        
        # Refresh token payload
        refresh_token_payload = {
            "iss": self.issuer,
            "sub": user_id,
            "aud": self.client_id,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(days=30)).timestamp()),
            "azp": self.client_id,
            "typ": "Refresh"
        }
        
        access_token = jwt.encode(access_token_payload, self.private_key, algorithm="HS256")
        refresh_token = jwt.encode(refresh_token_payload, self.private_key, algorithm="HS256")
        
        return {
            "access_token": access_token,
            "expires_in": 3600,
            "refresh_expires_in": 2592000,  # 30 days
            "refresh_token": refresh_token,
            "token_type": "Bearer",
            "not-before-policy": 0,
            "scope": "openid profile email"
        }


def create_app():
    """Create mock Keycloak application."""
    server = MockKeycloakServer()
    return server.app


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(create_app(), host="0.0.0.0", port=8080)
