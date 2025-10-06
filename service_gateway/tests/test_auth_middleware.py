"""
Unit tests for AuthMiddleware.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi import Request

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from service_gateway.app.domain.auth_middleware import AuthMiddleware
from shared.errors import AuthenticationError


class TestAuthMiddleware:
    """Test cases for AuthMiddleware."""
    
    @pytest.fixture
    def auth_middleware(self):
        """Create AuthMiddleware instance."""
        mock_auth_client = AsyncMock()
        mock_entitlements_client = AsyncMock()
        return AuthMiddleware(mock_auth_client, mock_entitlements_client)
    
    @pytest.fixture
    def mock_request(self):
        """Create mock request."""
        request = MagicMock(spec=Request)
        request.headers = {}
        return request
    
    @pytest.fixture
    def mock_user_info(self):
        """Mock user info."""
        return {
            "user_id": "user1",
            "tenant_id": "tenant-1",
            "roles": ["user", "analyst"],
            "email": "john.doe@254carbon.com",
            "username": "john.doe"
        }
    
    @pytest.mark.asyncio
    async def test_authenticate_request_jwt_success(self, auth_middleware, mock_request, mock_user_info):
        """Test successful JWT authentication."""
        # Set up request headers
        mock_request.headers = {"Authorization": "Bearer valid_token"}
        
        # Mock auth client
        auth_middleware.auth_client.verify_token = AsyncMock(return_value={
            "valid": True,
            "user_info": mock_user_info
        })
        
        # Test
        result = await auth_middleware.authenticate_request(mock_request)
        
        # Assertions
        assert result == mock_user_info
        auth_middleware.auth_client.verify_token.assert_called_once_with("valid_token")
    
    @pytest.mark.asyncio
    async def test_authenticate_request_api_key_success(self, auth_middleware, mock_request):
        """Test successful API key authentication."""
        # Set up request headers
        mock_request.headers = {"X-API-Key": "dev-key-123"}
        
        # Test
        result = await auth_middleware.authenticate_request(mock_request)
        
        # Assertions
        assert result["user_id"] == "api-key-dev-key-123"
        assert result["tenant_id"] == "tenant-1"
        assert result["roles"] == ["user"]
        assert result["auth_method"] == "api_key"
    
    @pytest.mark.asyncio
    async def test_authenticate_request_api_key_invalid(self, auth_middleware, mock_request):
        """Test invalid API key authentication."""
        # Set up request headers
        mock_request.headers = {"X-API-Key": "invalid-key"}
        
        # Test and assert exception
        with pytest.raises(Exception):  # HTTPException
            await auth_middleware.authenticate_request(mock_request)
    
    @pytest.mark.asyncio
    async def test_authenticate_request_no_auth(self, auth_middleware, mock_request):
        """Test authentication with no auth headers."""
        # Set up request headers (empty)
        mock_request.headers = {}
        
        # Test and assert exception
        with pytest.raises(Exception):  # HTTPException
            await auth_middleware.authenticate_request(mock_request)
    
    @pytest.mark.asyncio
    async def test_authenticate_request_invalid_bearer_format(self, auth_middleware, mock_request):
        """Test authentication with invalid Bearer format."""
        # Set up request headers
        mock_request.headers = {"Authorization": "InvalidFormat valid_token"}
        
        # Test and assert exception
        with pytest.raises(Exception):  # HTTPException
            await auth_middleware.authenticate_request(mock_request)
    
    @pytest.mark.asyncio
    async def test_authenticate_request_jwt_failure(self, auth_middleware, mock_request):
        """Test JWT authentication failure."""
        # Set up request headers
        mock_request.headers = {"Authorization": "Bearer invalid_token"}
        
        # Mock auth client to raise exception
        auth_middleware.auth_client.verify_token = AsyncMock(side_effect=AuthenticationError("Invalid token"))
        
        # Test and assert exception
        with pytest.raises(Exception):  # HTTPException
            await auth_middleware.authenticate_request(mock_request)
    
    @pytest.mark.asyncio
    async def test_authorize_request_success(self, auth_middleware, mock_user_info):
        """Test successful request authorization."""
        # Mock entitlements client
        auth_middleware.entitlements_client.check_entitlement = AsyncMock(return_value=True)
        
        # Test
        result = await auth_middleware.authorize_request(
            mock_user_info, "read", "instrument", "INST001"
        )
        
        # Assertions
        assert result is True
        auth_middleware.entitlements_client.check_entitlement.assert_called_once_with(
            user_id="user1",
            tenant_id="tenant-1",
            action="read",
            resource_type="instrument",
            resource_id="INST001",
            context={"roles": ["user", "analyst"]}
        )
    
    @pytest.mark.asyncio
    async def test_authorize_request_failure(self, auth_middleware, mock_user_info):
        """Test request authorization failure."""
        # Mock entitlements client to raise exception
        from shared.errors import AuthorizationError
        auth_middleware.entitlements_client.check_entitlement = AsyncMock(
            side_effect=AuthorizationError("Access denied")
        )
        
        # Test and assert exception
        with pytest.raises(Exception):  # HTTPException
            await auth_middleware.authorize_request(
                mock_user_info, "write", "instrument", "INST001"
            )
    
    @pytest.mark.asyncio
    async def test_process_request_success(self, auth_middleware, mock_request, mock_user_info):
        """Test successful request processing."""
        # Set up request headers
        mock_request.headers = {"Authorization": "Bearer valid_token"}
        
        # Mock auth client
        auth_middleware.auth_client.verify_token = AsyncMock(return_value={
            "valid": True,
            "user_info": mock_user_info
        })
        
        # Mock entitlements client
        auth_middleware.entitlements_client.check_entitlement = AsyncMock(return_value=True)
        
        # Test
        result = await auth_middleware.process_request(
            mock_request, "read", "instrument", "INST001"
        )
        
        # Assertions
        assert result == mock_user_info
        auth_middleware.auth_client.verify_token.assert_called_once_with("valid_token")
        auth_middleware.entitlements_client.check_entitlement.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_process_request_auth_failure(self, auth_middleware, mock_request):
        """Test request processing with authentication failure."""
        # Set up request headers
        mock_request.headers = {"Authorization": "Bearer invalid_token"}
        
        # Mock auth client to raise exception
        auth_middleware.auth_client.verify_token = AsyncMock(side_effect=AuthenticationError("Invalid token"))
        
        # Test and assert exception
        with pytest.raises(Exception):  # HTTPException
            await auth_middleware.process_request(
                mock_request, "read", "instrument", "INST001"
            )
    
    @pytest.mark.asyncio
    async def test_process_request_authorization_failure(self, auth_middleware, mock_request, mock_user_info):
        """Test request processing with authorization failure."""
        # Set up request headers
        mock_request.headers = {"Authorization": "Bearer valid_token"}
        
        # Mock auth client
        auth_middleware.auth_client.verify_token = AsyncMock(return_value={
            "valid": True,
            "user_info": mock_user_info
        })
        
        # Mock entitlements client to raise exception
        from shared.errors import AuthorizationError
        auth_middleware.entitlements_client.check_entitlement = AsyncMock(
            side_effect=AuthorizationError("Access denied")
        )
        
        # Test and assert exception
        with pytest.raises(Exception):  # HTTPException
            await auth_middleware.process_request(
                mock_request, "write", "instrument", "INST001"
            )
