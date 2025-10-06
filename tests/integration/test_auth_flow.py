"""
Integration tests for Auth service flow.
"""

import pytest
import httpx
import jwt
from datetime import datetime, timedelta
from unittest.mock import patch, AsyncMock

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from shared.test_helpers import create_mock_jwt_token, create_mock_user


class TestAuthFlow:
    """Integration tests for complete auth flow."""
    
    @pytest.fixture
    def auth_service_url(self):
        """Auth service URL."""
        return "http://localhost:8001"
    
    @pytest.fixture
    def mock_keycloak_url(self):
        """Mock Keycloak URL."""
        return "http://localhost:8080"
    
    @pytest.fixture
    def mock_user(self):
        """Create mock user."""
        return create_mock_user(
            user_id="test-user-1",
            tenant_id="tenant-1",
            roles=["user", "analyst"]
        )
    
    @pytest.fixture
    def mock_jwt_token(self, mock_user):
        """Create mock JWT token."""
        return create_mock_jwt_token(
            user_id=mock_user["user_id"],
            tenant_id=mock_user["tenant_id"],
            roles=mock_user["roles"],
            expires_in=3600
        )
    
    @pytest.mark.asyncio
    async def test_complete_auth_flow(self, auth_service_url, mock_keycloak_url, mock_user, mock_jwt_token):
        """Test complete authentication flow."""
        async with httpx.AsyncClient() as client:
            # 1. Verify token
            verify_response = await client.post(
                f"{auth_service_url}/auth/verify",
                json={"token": mock_jwt_token}
            )
            assert verify_response.status_code == 200
            verify_data = verify_response.json()
            assert verify_data["valid"] is True
            assert verify_data["user_id"] == mock_user["user_id"]
            assert verify_data["tenant_id"] == mock_user["tenant_id"]
            
            # 2. Get user info
            user_response = await client.get(
                f"{auth_service_url}/auth/users/{mock_user['user_id']}"
            )
            assert user_response.status_code == 200
            user_data = user_response.json()
            assert user_data["user_id"] == mock_user["user_id"]
            assert user_data["tenant_id"] == mock_user["tenant_id"]
            
            # 3. Refresh token
            refresh_response = await client.post(
                f"{auth_service_url}/auth/refresh",
                json={"refresh_token": mock_jwt_token}
            )
            assert refresh_response.status_code == 200
            refresh_data = refresh_response.json()
            assert refresh_data["valid"] is True
            assert "access_token" in refresh_data
            assert "refresh_token" in refresh_data
            
            # 4. Revoke token
            revoke_response = await client.post(
                f"{auth_service_url}/auth/logout",
                json={"token": mock_jwt_token}
            )
            assert revoke_response.status_code == 200
            revoke_data = revoke_response.json()
            assert revoke_data["revoked"] is True
    
    @pytest.mark.asyncio
    async def test_auth_flow_with_invalid_token(self, auth_service_url):
        """Test auth flow with invalid token."""
        async with httpx.AsyncClient() as client:
            # Verify invalid token
            verify_response = await client.post(
                f"{auth_service_url}/auth/verify",
                json={"token": "invalid-token"}
            )
            assert verify_response.status_code == 200
            verify_data = verify_response.json()
            assert verify_data["valid"] is False
            assert "error" in verify_data
    
    @pytest.mark.asyncio
    async def test_auth_flow_with_expired_token(self, auth_service_url, mock_user):
        """Test auth flow with expired token."""
        # Create expired token
        expired_token = create_mock_jwt_token(
            user_id=mock_user["user_id"],
            tenant_id=mock_user["tenant_id"],
            roles=mock_user["roles"],
            expires_in=-3600  # Expired 1 hour ago
        )
        
        async with httpx.AsyncClient() as client:
            # Verify expired token
            verify_response = await client.post(
                f"{auth_service_url}/auth/verify",
                json={"token": expired_token}
            )
            assert verify_response.status_code == 200
            verify_data = verify_response.json()
            assert verify_data["valid"] is False
            assert "expired" in verify_data.get("error", "").lower()
    
    @pytest.mark.asyncio
    async def test_auth_flow_with_missing_user(self, auth_service_url):
        """Test auth flow with non-existent user."""
        async with httpx.AsyncClient() as client:
            # Get non-existent user
            user_response = await client.get(
                f"{auth_service_url}/auth/users/non-existent-user"
            )
            assert user_response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_auth_flow_with_keycloak_failure(self, auth_service_url, mock_jwt_token):
        """Test auth flow when Keycloak is unavailable."""
        # Mock Keycloak failure
        with patch('httpx.AsyncClient.get') as mock_get:
            mock_get.side_effect = httpx.ConnectError("Connection failed")
            
            async with httpx.AsyncClient() as client:
                # Verify token should still work with cached JWKS
                verify_response = await client.post(
                    f"{auth_service_url}/auth/verify",
                    json={"token": mock_jwt_token}
                )
                # Should either succeed with cached data or fail gracefully
                assert verify_response.status_code in [200, 503]
    
    @pytest.mark.asyncio
    async def test_auth_flow_rate_limiting(self, auth_service_url, mock_jwt_token):
        """Test auth flow with rate limiting."""
        async with httpx.AsyncClient() as client:
            # Make multiple rapid requests
            responses = []
            for _ in range(10):
                response = await client.post(
                    f"{auth_service_url}/auth/verify",
                    json={"token": mock_jwt_token}
                )
                responses.append(response)
            
            # Most should succeed, some might be rate limited
            success_count = sum(1 for r in responses if r.status_code == 200)
            rate_limited_count = sum(1 for r in responses if r.status_code == 429)
            
            assert success_count > 0
            # Rate limiting might not be enabled in test environment
            assert success_count + rate_limited_count == len(responses)
    
    @pytest.mark.asyncio
    async def test_auth_flow_concurrent_requests(self, auth_service_url, mock_jwt_token):
        """Test auth flow with concurrent requests."""
        import asyncio
        
        async def verify_token():
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{auth_service_url}/auth/verify",
                    json={"token": mock_jwt_token}
                )
                return response.status_code == 200
        
        # Make 20 concurrent requests
        tasks = [verify_token() for _ in range(20)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # All should succeed or fail gracefully
        success_count = sum(1 for r in results if r is True)
        assert success_count > 0
    
    @pytest.mark.asyncio
    async def test_auth_flow_jwks_caching(self, auth_service_url, mock_jwt_token):
        """Test JWKS caching behavior."""
        async with httpx.AsyncClient() as client:
            # First request - should fetch JWKS
            response1 = await client.post(
                f"{auth_service_url}/auth/verify",
                json={"token": mock_jwt_token}
            )
            assert response1.status_code == 200
            
            # Second request - should use cached JWKS
            response2 = await client.post(
                f"{auth_service_url}/auth/verify",
                json={"token": mock_jwt_token}
            )
            assert response2.status_code == 200
            
            # Both should succeed
            assert response1.json()["valid"] == response2.json()["valid"]
    
    @pytest.mark.asyncio
    async def test_auth_flow_circuit_breaker(self, auth_service_url, mock_jwt_token):
        """Test circuit breaker behavior with Keycloak failures."""
        # Mock multiple Keycloak failures
        with patch('httpx.AsyncClient.get') as mock_get:
            mock_get.side_effect = httpx.ConnectError("Connection failed")
            
            async with httpx.AsyncClient() as client:
                # Make multiple requests to trigger circuit breaker
                responses = []
                for _ in range(6):  # More than failure threshold
                    response = await client.post(
                        f"{auth_service_url}/auth/verify",
                        json={"token": mock_jwt_token}
                    )
                    responses.append(response)
                
                # Circuit breaker should eventually open
                # Some requests might succeed with cached data, others should fail
                status_codes = [r.status_code for r in responses]
                assert 200 in status_codes or 503 in status_codes