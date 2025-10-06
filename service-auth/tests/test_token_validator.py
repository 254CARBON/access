"""
Unit tests for TokenValidator.
"""

import pytest
import jwt
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch, MagicMock

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from service_auth.app.validation.token_validator import TokenValidator, TokenVerificationRequest, TokenVerificationResponse, TokenRefreshResponse
from shared.errors import AuthenticationError


class TestTokenValidator:
    """Test cases for TokenValidator."""
    
    @pytest.fixture
    def token_validator(self):
        """Create TokenValidator instance."""
        with patch('service_auth.app.validation.token_validator.JWKSClient') as mock_jwks:
            mock_jwks_client = AsyncMock()
            mock_jwks.return_value = mock_jwks_client
            return TokenValidator("http://mock-keycloak/jwks")
    
    @pytest.fixture
    def mock_claims(self):
        """Mock JWT claims."""
        return {
            "sub": "user1",
            "tenant_id": "tenant-1",
            "email": "john.doe@254carbon.com",
            "preferred_username": "john.doe",
            "realm_access": {"roles": ["user", "analyst"]},
            "resource_access": {"access-layer": {"roles": ["user"]}},
            "exp": int((datetime.utcnow() + timedelta(hours=1)).timestamp()),
            "iat": int(datetime.utcnow().timestamp())
        }
    
    @pytest.fixture
    def mock_refresh_claims(self):
        """Mock refresh token claims."""
        return {
            "sub": "user1",
            "typ": "Refresh",
            "exp": int((datetime.utcnow() + timedelta(days=30)).timestamp()),
            "iat": int(datetime.utcnow().timestamp())
        }
    
    @pytest.mark.asyncio
    async def test_verify_token_success(self, token_validator, mock_claims):
        """Test successful token verification."""
        # Mock JWKS client
        token_validator.jwks_client.verify_token = AsyncMock(return_value=mock_claims)
        
        # Test
        result = await token_validator.verify_token("valid_token")
        
        # Assertions
        assert result.valid is True
        assert result.claims == mock_claims
        assert result.error is None
        token_validator.jwks_client.verify_token.assert_called_once_with("valid_token")
    
    @pytest.mark.asyncio
    async def test_verify_token_with_bearer_prefix(self, token_validator, mock_claims):
        """Test token verification with Bearer prefix."""
        # Mock JWKS client
        token_validator.jwks_client.verify_token = AsyncMock(return_value=mock_claims)
        
        # Test
        result = await token_validator.verify_token("Bearer valid_token")
        
        # Assertions
        assert result.valid is True
        assert result.claims == mock_claims
        token_validator.jwks_client.verify_token.assert_called_once_with("valid_token")
    
    @pytest.mark.asyncio
    async def test_verify_token_failure(self, token_validator):
        """Test token verification failure."""
        # Mock JWKS client to raise exception
        token_validator.jwks_client.verify_token = AsyncMock(side_effect=jwt.InvalidTokenError("Invalid token"))
        
        # Test
        result = await token_validator.verify_token("invalid_token")
        
        # Assertions
        assert result.valid is False
        assert result.claims is None
        assert "Invalid token" in result.error
    
    @pytest.mark.asyncio
    async def test_extract_claims_success(self, token_validator, mock_claims):
        """Test successful claims extraction."""
        # Mock JWKS client
        token_validator.jwks_client.verify_token = AsyncMock(return_value=mock_claims)
        
        # Test
        claims = await token_validator.extract_claims("valid_token")
        
        # Assertions
        assert claims == mock_claims
    
    @pytest.mark.asyncio
    async def test_extract_claims_failure(self, token_validator):
        """Test claims extraction failure."""
        # Mock JWKS client to raise exception
        token_validator.jwks_client.verify_token = AsyncMock(side_effect=jwt.InvalidTokenError("Invalid token"))
        
        # Test and assert exception
        with pytest.raises(AuthenticationError):
            await token_validator.extract_claims("invalid_token")
    
    @pytest.mark.asyncio
    async def test_get_user_info(self, token_validator, mock_claims):
        """Test user info extraction."""
        # Mock JWKS client
        token_validator.jwks_client.verify_token = AsyncMock(return_value=mock_claims)
        
        # Test
        user_info = await token_validator.get_user_info("valid_token")
        
        # Assertions
        assert user_info["user_id"] == "user1"
        assert user_info["tenant_id"] == "tenant-1"
        assert user_info["email"] == "john.doe@254carbon.com"
        assert user_info["username"] == "john.doe"
        assert user_info["roles"] == ["user", "analyst"]
        assert user_info["client_roles"] == {"access-layer": {"roles": ["user"]}}
    
    @pytest.mark.asyncio
    async def test_refresh_token_success(self, token_validator, mock_refresh_claims):
        """Test successful token refresh."""
        # Mock JWKS client
        token_validator.jwks_client.verify_token = AsyncMock(return_value=mock_refresh_claims)
        
        # Mock get_user_by_id
        mock_user_info = {
            "id": "user1",
            "username": "john.doe",
            "email": "john.doe@254carbon.com",
            "tenant_id": "tenant-1",
            "roles": ["user", "analyst"]
        }
        token_validator.get_user_by_id = AsyncMock(return_value=mock_user_info)
        
        # Mock _generate_new_tokens
        mock_tokens = {
            "access_token": "new_access_token",
            "refresh_token": "new_refresh_token",
            "expires_in": 3600
        }
        token_validator._generate_new_tokens = AsyncMock(return_value=mock_tokens)
        
        # Test
        result = await token_validator.refresh_token("valid_refresh_token")
        
        # Assertions
        assert result.valid is True
        assert result.access_token == "new_access_token"
        assert result.refresh_token == "new_refresh_token"
        assert result.expires_in == 3600
        assert result.token_type == "Bearer"
    
    @pytest.mark.asyncio
    async def test_refresh_token_invalid_type(self, token_validator):
        """Test refresh token with invalid type."""
        # Mock JWKS client with non-refresh token
        mock_claims = {"sub": "user1", "typ": "Access"}
        token_validator.jwks_client.verify_token = AsyncMock(return_value=mock_claims)
        
        # Test
        result = await token_validator.refresh_token("invalid_refresh_token")
        
        # Assertions
        assert result.valid is False
        assert "Invalid refresh token type" in result.error
    
    @pytest.mark.asyncio
    async def test_refresh_token_missing_user_id(self, token_validator):
        """Test refresh token missing user ID."""
        # Mock JWKS client
        mock_claims = {"typ": "Refresh"}  # Missing sub
        token_validator.jwks_client.verify_token = AsyncMock(return_value=mock_claims)
        
        # Test
        result = await token_validator.refresh_token("invalid_refresh_token")
        
        # Assertions
        assert result.valid is False
        assert "Refresh token missing user ID" in result.error
    
    @pytest.mark.asyncio
    async def test_refresh_token_user_not_found(self, token_validator, mock_refresh_claims):
        """Test refresh token with user not found."""
        # Mock JWKS client
        token_validator.jwks_client.verify_token = AsyncMock(return_value=mock_refresh_claims)
        
        # Mock get_user_by_id to return None
        token_validator.get_user_by_id = AsyncMock(return_value=None)
        
        # Test
        result = await token_validator.refresh_token("valid_refresh_token")
        
        # Assertions
        assert result.valid is False
        assert "User not found" in result.error
    
    @pytest.mark.asyncio
    async def test_revoke_token_success(self, token_validator, mock_claims):
        """Test successful token revocation."""
        # Mock JWKS client
        token_validator.jwks_client.verify_token = AsyncMock(return_value=mock_claims)
        
        # Test
        result = await token_validator.revoke_token("valid_token")
        
        # Assertions
        assert result is True
    
    @pytest.mark.asyncio
    async def test_revoke_token_failure(self, token_validator):
        """Test token revocation failure."""
        # Mock JWKS client to raise exception
        token_validator.jwks_client.verify_token = AsyncMock(side_effect=jwt.InvalidTokenError("Invalid token"))
        
        # Test
        result = await token_validator.revoke_token("invalid_token")
        
        # Assertions
        assert result is False
    
    @pytest.mark.asyncio
    async def test_get_user_by_id_success(self, token_validator):
        """Test successful user lookup by ID."""
        # Test
        user_info = await token_validator.get_user_by_id("user1")
        
        # Assertions
        assert user_info is not None
        assert user_info["id"] == "user1"
        assert user_info["username"] == "john.doe"
        assert user_info["email"] == "john.doe@254carbon.com"
        assert user_info["tenant_id"] == "tenant-1"
        assert user_info["roles"] == ["user", "analyst"]
    
    @pytest.mark.asyncio
    async def test_get_user_by_id_not_found(self, token_validator):
        """Test user lookup by ID not found."""
        # Test
        user_info = await token_validator.get_user_by_id("nonexistent_user")
        
        # Assertions
        assert user_info is None
    
    @pytest.mark.asyncio
    async def test_generate_new_tokens(self, token_validator):
        """Test new token generation."""
        # Mock user info
        user_info = {
            "id": "user1",
            "username": "john.doe",
            "email": "john.doe@254carbon.com",
            "tenant_id": "tenant-1",
            "roles": ["user", "analyst"]
        }
        
        # Test
        tokens = await token_validator._generate_new_tokens(user_info)
        
        # Assertions
        assert "access_token" in tokens
        assert "refresh_token" in tokens
        assert "expires_in" in tokens
        assert tokens["expires_in"] == 3600
        assert tokens["access_token"].startswith("mock_access_token_")
        assert tokens["refresh_token"].startswith("mock_refresh_token_")
