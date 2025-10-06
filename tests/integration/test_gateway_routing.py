"""
Integration tests for Gateway routing flow.
"""

import pytest
import httpx
import json
from unittest.mock import patch, AsyncMock

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from shared.test_helpers import create_mock_jwt_token, create_mock_user


class TestGatewayRouting:
    """Integration tests for Gateway routing flow."""
    
    @pytest.fixture
    def gateway_url(self):
        """Gateway service URL."""
        return "http://localhost:8000"
    
    @pytest.fixture
    def auth_service_url(self):
        """Auth service URL."""
        return "http://localhost:8001"
    
    @pytest.fixture
    def entitlements_service_url(self):
        """Entitlements service URL."""
        return "http://localhost:8002"
    
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
    
    @pytest.fixture
    def mock_api_key(self):
        """Mock API key."""
        return "dev-key-123"
    
    @pytest.mark.asyncio
    async def test_gateway_routing_with_jwt_auth(self, gateway_url, mock_jwt_token):
        """Test Gateway routing with JWT authentication."""
        async with httpx.AsyncClient() as client:
            headers = {"Authorization": f"Bearer {mock_jwt_token}"}
            
            # Test status endpoint
            response = await client.get(f"{gateway_url}/api/v1/status", headers=headers)
            assert response.status_code == 200
            data = response.json()
            assert "status" in data
            assert data["status"] == "healthy"
            
            # Test instruments endpoint
            response = await client.get(f"{gateway_url}/api/v1/instruments", headers=headers)
            assert response.status_code == 200
            data = response.json()
            assert "instruments" in data
            
            # Test curves endpoint
            response = await client.get(f"{gateway_url}/api/v1/curves", headers=headers)
            assert response.status_code == 200
            data = response.json()
            assert "curves" in data
    
    @pytest.mark.asyncio
    async def test_gateway_routing_with_api_key_auth(self, gateway_url, mock_api_key):
        """Test Gateway routing with API key authentication."""
        async with httpx.AsyncClient() as client:
            headers = {"X-API-Key": mock_api_key}
            
            # Test status endpoint
            response = await client.get(f"{gateway_url}/api/v1/status", headers=headers)
            assert response.status_code == 200
            data = response.json()
            assert "status" in data
            
            # Test instruments endpoint
            response = await client.get(f"{gateway_url}/api/v1/instruments", headers=headers)
            assert response.status_code == 200
            data = response.json()
            assert "instruments" in data
    
    @pytest.mark.asyncio
    async def test_gateway_routing_without_auth(self, gateway_url):
        """Test Gateway routing without authentication."""
        async with httpx.AsyncClient() as client:
            # Test status endpoint (should be public)
            response = await client.get(f"{gateway_url}/api/v1/status")
            assert response.status_code == 200
            
            # Test protected endpoint without auth
            response = await client.get(f"{gateway_url}/api/v1/instruments")
            assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_gateway_routing_with_invalid_auth(self, gateway_url):
        """Test Gateway routing with invalid authentication."""
        async with httpx.AsyncClient() as client:
            headers = {"Authorization": "Bearer invalid-token"}
            
            # Test protected endpoint with invalid token
            response = await client.get(f"{gateway_url}/api/v1/instruments", headers=headers)
            assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_gateway_routing_rate_limiting(self, gateway_url, mock_jwt_token):
        """Test Gateway routing with rate limiting."""
        async with httpx.AsyncClient() as client:
            headers = {"Authorization": f"Bearer {mock_jwt_token}"}
            
            # Make multiple rapid requests
            responses = []
            for _ in range(20):
                response = await client.get(f"{gateway_url}/api/v1/status", headers=headers)
                responses.append(response)
            
            # Most should succeed, some might be rate limited
            success_count = sum(1 for r in responses if r.status_code == 200)
            rate_limited_count = sum(1 for r in responses if r.status_code == 429)
            
            assert success_count > 0
            # Rate limiting might not be enabled in test environment
            assert success_count + rate_limited_count == len(responses)
    
    @pytest.mark.asyncio
    async def test_gateway_routing_caching(self, gateway_url, mock_jwt_token):
        """Test Gateway routing with caching."""
        async with httpx.AsyncClient() as client:
            headers = {"Authorization": f"Bearer {mock_jwt_token}"}
            
            # First request - should fetch from backend
            response1 = await client.get(f"{gateway_url}/api/v1/instruments", headers=headers)
            assert response1.status_code == 200
            
            # Second request - should use cache
            response2 = await client.get(f"{gateway_url}/api/v1/instruments", headers=headers)
            assert response2.status_code == 200
            
            # Both should return same data
            assert response1.json() == response2.json()
    
    @pytest.mark.asyncio
    async def test_gateway_routing_new_endpoints(self, gateway_url, mock_jwt_token):
        """Test Gateway routing with new endpoints."""
        async with httpx.AsyncClient() as client:
            headers = {"Authorization": f"Bearer {mock_jwt_token}"}
            
            # Test products endpoint
            response = await client.get(f"{gateway_url}/api/v1/products", headers=headers)
            assert response.status_code == 200
            data = response.json()
            assert "products" in data
            
            # Test pricing endpoint
            response = await client.get(f"{gateway_url}/api/v1/pricing", headers=headers)
            assert response.status_code == 200
            data = response.json()
            assert "pricing" in data
            
            # Test historical endpoint
            response = await client.get(f"{gateway_url}/api/v1/historical", headers=headers)
            assert response.status_code == 200
            data = response.json()
            assert "historical" in data
    
    @pytest.mark.asyncio
    async def test_gateway_routing_with_entitlements(self, gateway_url, mock_jwt_token):
        """Test Gateway routing with entitlements check."""
        async with httpx.AsyncClient() as client:
            headers = {"Authorization": f"Bearer {mock_jwt_token}"}
            
            # Test endpoint that requires entitlements
            response = await client.get(f"{gateway_url}/api/v1/instruments", headers=headers)
            assert response.status_code in [200, 403]  # 200 if entitled, 403 if not
    
    @pytest.mark.asyncio
    async def test_gateway_routing_fallback_to_mock_data(self, gateway_url, mock_jwt_token):
        """Test Gateway routing fallback to mock data when backend is unavailable."""
        # Mock backend service failure
        with patch('httpx.AsyncClient.get') as mock_get:
            mock_get.side_effect = httpx.ConnectError("Backend unavailable")
            
            async with httpx.AsyncClient() as client:
                headers = {"Authorization": f"Bearer {mock_jwt_token}"}
                
                # Should fallback to mock data
                response = await client.get(f"{gateway_url}/api/v1/instruments", headers=headers)
                assert response.status_code == 200
                data = response.json()
                assert "instruments" in data
                # Should contain mock data
                assert len(data["instruments"]) > 0
    
    @pytest.mark.asyncio
    async def test_gateway_routing_circuit_breaker(self, gateway_url, mock_jwt_token):
        """Test Gateway routing with circuit breaker."""
        # Mock backend service failures
        with patch('httpx.AsyncClient.get') as mock_get:
            mock_get.side_effect = httpx.ConnectError("Backend unavailable")
            
            async with httpx.AsyncClient() as client:
                headers = {"Authorization": f"Bearer {mock_jwt_token}"}
                
                # Make multiple requests to trigger circuit breaker
                responses = []
                for _ in range(6):  # More than failure threshold
                    response = await client.get(f"{gateway_url}/api/v1/instruments", headers=headers)
                    responses.append(response)
                
                # Circuit breaker should eventually open
                # Some requests might succeed with fallback data, others should fail
                status_codes = [r.status_code for r in responses]
                assert 200 in status_codes or 503 in status_codes
    
    @pytest.mark.asyncio
    async def test_gateway_routing_concurrent_requests(self, gateway_url, mock_jwt_token):
        """Test Gateway routing with concurrent requests."""
        import asyncio
        
        async def make_request():
            async with httpx.AsyncClient() as client:
                headers = {"Authorization": f"Bearer {mock_jwt_token}"}
                response = await client.get(f"{gateway_url}/api/v1/status", headers=headers)
                return response.status_code == 200
        
        # Make 20 concurrent requests
        tasks = [make_request() for _ in range(20)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # All should succeed or fail gracefully
        success_count = sum(1 for r in results if r is True)
        assert success_count > 0
    
    @pytest.mark.asyncio
    async def test_gateway_routing_error_handling(self, gateway_url, mock_jwt_token):
        """Test Gateway routing error handling."""
        async with httpx.AsyncClient() as client:
            headers = {"Authorization": f"Bearer {mock_jwt_token}"}
            
            # Test non-existent endpoint
            response = await client.get(f"{gateway_url}/api/v1/nonexistent", headers=headers)
            assert response.status_code == 404
            
            # Test invalid method
            response = await client.post(f"{gateway_url}/api/v1/status", headers=headers)
            assert response.status_code == 405
    
    @pytest.mark.asyncio
    async def test_gateway_routing_request_transformation(self, gateway_url, mock_jwt_token):
        """Test Gateway routing request transformation."""
        async with httpx.AsyncClient() as client:
            headers = {
                "Authorization": f"Bearer {mock_jwt_token}",
                "Content-Type": "application/json"
            }
            
            # Test POST request with body
            data = {"query": "test", "filters": {"type": "commodity"}}
            response = await client.post(
                f"{gateway_url}/api/v1/instruments/search",
                headers=headers,
                json=data
            )
            # Should either succeed or return method not allowed
            assert response.status_code in [200, 405]
    
    @pytest.mark.asyncio
    async def test_gateway_routing_response_transformation(self, gateway_url, mock_jwt_token):
        """Test Gateway routing response transformation."""
        async with httpx.AsyncClient() as client:
            headers = {"Authorization": f"Bearer {mock_jwt_token}"}
            
            # Test response format
            response = await client.get(f"{gateway_url}/api/v1/instruments", headers=headers)
            assert response.status_code == 200
            
            data = response.json()
            # Should have consistent response format
            assert "instruments" in data
            assert isinstance(data["instruments"], list)
            
            # Check response headers
            assert "content-type" in response.headers
            assert "application/json" in response.headers["content-type"]
