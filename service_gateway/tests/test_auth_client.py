"""
Unit tests for Gateway Auth Client.
"""

import pytest
import httpx
from unittest.mock import AsyncMock, patch, MagicMock
import json

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from service_gateway.app.adapters.auth_client import AuthClient
from shared.errors import AuthenticationError


class TestAuthClient:
    """Test cases for AuthClient."""

    @pytest.fixture
    def auth_client(self):
        """Create AuthClient instance."""
        return AuthClient("http://localhost:8010")

    @pytest.fixture
    def mock_token(self):
        """Mock JWT token."""
        return "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test.signature"

    @pytest.fixture
    def mock_user_info(self):
        """Mock user info response."""
        return {
            "user_id": "user-123",
            "tenant_id": "tenant-1",
            "roles": ["user", "analyst"],
            "email": "test@example.com"
        }

    @pytest.mark.asyncio
    async def test_verify_token_success(self, auth_client, mock_token, mock_user_info):
        """Test successful token verification."""
        mock_response = {
            "valid": True,
            "claims": {"sub": "user-123", "tenant_id": "tenant-1"},
            "user_info": mock_user_info
        }

        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=httpx.Response(
                    status_code=200,
                    content=json.dumps(mock_response),
                    request=httpx.Request("POST", "http://localhost:8010/auth/verify")
                )
            )

            result = await auth_client.verify_token(mock_token)

            assert result["valid"] is True
            assert result["user_info"]["user_id"] == "user-123"
            assert result["user_info"]["tenant_id"] == "tenant-1"

    @pytest.mark.asyncio
    async def test_verify_token_invalid(self, auth_client, mock_token):
        """Test invalid token verification."""
        mock_response = {
            "valid": False,
            "error": "Token expired"
        }

        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=httpx.Response(
                    status_code=200,
                    content=json.dumps(mock_response),
                    request=httpx.Request("POST", "http://localhost:8010/auth/verify")
                )
            )

            result = await auth_client.verify_token(mock_token)

            assert result["valid"] is False
            assert result["error"] == "Token expired"

    @pytest.mark.asyncio
    async def test_verify_token_websocket_success(self, auth_client, mock_token, mock_user_info):
        """Test successful WebSocket token verification."""
        mock_response = {
            "valid": True,
            "claims": {"sub": "user-123", "tenant_id": "tenant-1"},
            "user_info": mock_user_info
        }

        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=httpx.Response(
                    status_code=200,
                    content=json.dumps(mock_response),
                    request=httpx.Request("POST", "http://localhost:8010/auth/verify-ws")
                )
            )

            result = await auth_client.verify_websocket_token(mock_token)

            assert result["valid"] is True
            assert result["user_info"]["user_id"] == "user-123"

    @pytest.mark.asyncio
    async def test_verify_token_http_error(self, auth_client, mock_token):
        """Test HTTP error during token verification."""
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                side_effect=httpx.HTTPError("Connection failed")
            )

            with pytest.raises(AuthenticationError):
                await auth_client.verify_token(mock_token)

    @pytest.mark.asyncio
    async def test_verify_token_timeout(self, auth_client, mock_token):
        """Test timeout during token verification."""
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                side_effect=httpx.TimeoutException("Request timeout")
            )

            with pytest.raises(AuthenticationError):
                await auth_client.verify_token(mock_token)

    @pytest.mark.asyncio
    async def test_circuit_breaker_activation(self, auth_client, mock_token):
        """Test circuit breaker activation after failures."""
        with patch('httpx.AsyncClient') as mock_client:
            # Simulate multiple failures
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                side_effect=httpx.HTTPError("Service unavailable")
            )

            # First few calls should raise AuthenticationError
            for _ in range(3):
                with pytest.raises(AuthenticationError):
                    await auth_client.verify_token(mock_token)

            # Circuit breaker should be open now
            assert auth_client.circuit_breaker.is_open()

    @pytest.mark.asyncio
    async def test_get_user_info_success(self, auth_client, mock_user_info):
        """Test successful user info retrieval."""
        user_id = "user-123"
        mock_response = {
            "user_id": user_id,
            "username": "testuser",
            "email": "test@example.com",
            "tenant_id": "tenant-1",
            "roles": ["user"]
        }

        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=httpx.Response(
                    status_code=200,
                    content=json.dumps(mock_response),
                    request=httpx.Request("GET", f"http://localhost:8010/auth/users/{user_id}")
                )
            )

            result = await auth_client.get_user_info(user_id)

            assert result["user_id"] == user_id
            assert result["username"] == "testuser"
            assert result["tenant_id"] == "tenant-1"

    @pytest.mark.asyncio
    async def test_get_user_info_not_found(self, auth_client):
        """Test user info retrieval for non-existent user."""
        user_id = "nonexistent-user"

        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=httpx.Response(
                    status_code=404,
                    content=json.dumps({"error": "User not found"}),
                    request=httpx.Request("GET", f"http://localhost:8010/auth/users/{user_id}")
                )
            )

            result = await auth_client.get_user_info(user_id)

            assert "error" in result
            assert result["error"] == "User not found"
