"""
Unit tests for JWKSClient.
"""

import pytest
import httpx
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timedelta

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from service_auth.app.jwks.client import JWKSClient


class TestJWKSClient:
    """Test cases for JWKSClient."""
    
    @pytest.fixture
    def jwks_client(self):
        """Create JWKSClient instance."""
        with patch('service_auth.app.jwks.client.circuit_breaker_manager') as mock_cb_manager:
            mock_circuit_breaker = AsyncMock()
            mock_cb_manager.get_breaker.return_value = mock_circuit_breaker
            return JWKSClient("http://mock-keycloak/jwks")
    
    @pytest.fixture
    def mock_jwks_data(self):
        """Mock JWKS data."""
        return {
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
    
    @pytest.fixture
    def mock_token_header(self):
        """Mock JWT header."""
        return {"kid": "mock-key-1", "alg": "RS256"}
    
    @pytest.fixture
    def mock_token_payload(self):
        """Mock JWT payload."""
        return {
            "sub": "user1",
            "tenant_id": "tenant-1",
            "email": "john.doe@254carbon.com",
            "preferred_username": "john.doe",
            "exp": int((datetime.utcnow() + timedelta(hours=1)).timestamp()),
            "iat": int(datetime.utcnow().timestamp())
        }
    
    @pytest.mark.asyncio
    async def test_get_jwks_success(self, jwks_client, mock_jwks_data):
        """Test successful JWKS retrieval."""
        # Mock circuit breaker call
        jwks_client.circuit_breaker.call = AsyncMock(return_value=mock_jwks_data)
        
        # Test
        result = await jwks_client.get_jwks()
        
        # Assertions
        assert result == mock_jwks_data
        assert jwks_client._jwks_cache == mock_jwks_data
        assert jwks_client._cache_timestamp > 0
    
    @pytest.mark.asyncio
    async def test_get_jwks_cached(self, jwks_client, mock_jwks_data):
        """Test JWKS retrieval from cache."""
        # Set up cache
        jwks_client._jwks_cache = mock_jwks_data
        jwks_client._cache_timestamp = datetime.utcnow().timestamp()
        
        # Mock circuit breaker call
        jwks_client.circuit_breaker.call = AsyncMock(return_value=mock_jwks_data)
        
        # Test
        result = await jwks_client.get_jwks()
        
        # Assertions
        assert result == mock_jwks_data
        # Circuit breaker should not be called for cached data
        jwks_client.circuit_breaker.call.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_get_jwks_failure_with_stale_cache(self, jwks_client, mock_jwks_data):
        """Test JWKS retrieval failure with stale cache fallback."""
        # Set up stale cache
        jwks_client._jwks_cache = mock_jwks_data
        jwks_client._cache_timestamp = datetime.utcnow().timestamp() - 4000  # Stale
        
        # Mock circuit breaker call to raise exception
        jwks_client.circuit_breaker.call = AsyncMock(side_effect=httpx.HTTPError("Network error"))
        
        # Test
        result = await jwks_client.get_jwks()
        
        # Assertions
        assert result == mock_jwks_data  # Should return stale cache
    
    @pytest.mark.asyncio
    async def test_get_jwks_failure_no_cache(self, jwks_client):
        """Test JWKS retrieval failure with no cache."""
        # Mock circuit breaker call to raise exception
        jwks_client.circuit_breaker.call = AsyncMock(side_effect=httpx.HTTPError("Network error"))
        
        # Test and assert exception
        with pytest.raises(httpx.HTTPError):
            await jwks_client.get_jwks()
    
    @pytest.mark.asyncio
    async def test_get_key_success(self, jwks_client, mock_jwks_data):
        """Test successful key retrieval."""
        # Mock get_jwks
        jwks_client.get_jwks = AsyncMock(return_value=mock_jwks_data)
        
        # Test
        result = await jwks_client.get_key("mock-key-1")
        
        # Assertions
        assert result == mock_jwks_data["keys"][0]
        assert "mock-key-1" in jwks_client._key_cache
    
    @pytest.mark.asyncio
    async def test_get_key_cached(self, jwks_client, mock_jwks_data):
        """Test key retrieval from cache."""
        # Set up key cache
        jwks_client._key_cache["mock-key-1"] = mock_jwks_data["keys"][0]
        
        # Mock get_jwks
        jwks_client.get_jwks = AsyncMock(return_value=mock_jwks_data)
        
        # Test
        result = await jwks_client.get_key("mock-key-1")
        
        # Assertions
        assert result == mock_jwks_data["keys"][0]
        # get_jwks should not be called for cached key
        jwks_client.get_jwks.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_get_key_not_found(self, jwks_client, mock_jwks_data):
        """Test key retrieval for non-existent key."""
        # Mock get_jwks
        jwks_client.get_jwks = AsyncMock(return_value=mock_jwks_data)
        
        # Test
        result = await jwks_client.get_key("nonexistent-key")
        
        # Assertions
        assert result is None
    
    @pytest.mark.asyncio
    async def test_verify_token_success(self, jwks_client, mock_jwks_data, mock_token_header, mock_token_payload):
        """Test successful token verification."""
        # Mock get_key
        jwks_client.get_key = AsyncMock(return_value=mock_jwks_data["keys"][0])
        
        # Mock JWT operations
        with patch('service_auth.app.jwks.client.jwt') as mock_jwt:
            mock_jwt.get_unverified_header.return_value = mock_token_header
            mock_jwt.decode.return_value = mock_token_payload
            
            # Mock jwk.construct
            with patch('service_auth.app.jwks.client.jwk') as mock_jwk:
                mock_rsa_key = MagicMock()
                mock_jwk.construct.return_value = mock_rsa_key
                
                # Test
                result = await jwks_client.verify_token("valid_token")
                
                # Assertions
                assert result == mock_token_payload
                mock_jwt.get_unverified_header.assert_called_once_with("valid_token")
                mock_jwt.decode.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_verify_token_missing_kid(self, jwks_client):
        """Test token verification with missing key ID."""
        # Mock JWT operations
        with patch('service_auth.app.jwks.client.jwt') as mock_jwt:
            mock_jwt.get_unverified_header.return_value = {"alg": "RS256"}  # Missing kid
            
            # Test and assert exception
            with pytest.raises(Exception):  # JWTError
                await jwks_client.verify_token("invalid_token")
    
    @pytest.mark.asyncio
    async def test_verify_token_key_not_found(self, jwks_client, mock_token_header):
        """Test token verification with key not found."""
        # Mock get_key to return None
        jwks_client.get_key = AsyncMock(return_value=None)
        
        # Mock JWT operations
        with patch('service_auth.app.jwks.client.jwt') as mock_jwt:
            mock_jwt.get_unverified_header.return_value = mock_token_header
            
            # Test and assert exception
            with pytest.raises(Exception):  # JWTError
                await jwks_client.verify_token("invalid_token")
    
    @pytest.mark.asyncio
    async def test_verify_token_decode_error(self, jwks_client, mock_jwks_data, mock_token_header):
        """Test token verification with decode error."""
        # Mock get_key
        jwks_client.get_key = AsyncMock(return_value=mock_jwks_data["keys"][0])
        
        # Mock JWT operations
        with patch('service_auth.app.jwks.client.jwt') as mock_jwt:
            mock_jwt.get_unverified_header.return_value = mock_token_header
            mock_jwt.decode.side_effect = Exception("Invalid token")
            
            # Mock jwk.construct
            with patch('service_auth.app.jwks.client.jwk') as mock_jwk:
                mock_rsa_key = MagicMock()
                mock_jwk.construct.return_value = mock_rsa_key
                
                # Test and assert exception
                with pytest.raises(Exception):
                    await jwks_client.verify_token("invalid_token")
    
    def test_clear_cache(self, jwks_client, mock_jwks_data):
        """Test cache clearing."""
        # Set up cache
        jwks_client._jwks_cache = mock_jwks_data
        jwks_client._cache_timestamp = datetime.utcnow().timestamp()
        jwks_client._key_cache["mock-key-1"] = mock_jwks_data["keys"][0]
        
        # Test
        jwks_client.clear_cache()
        
        # Assertions
        assert jwks_client._jwks_cache is None
        assert jwks_client._cache_timestamp == 0
        assert len(jwks_client._key_cache) == 0
