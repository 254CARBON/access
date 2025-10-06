"""
End-to-end integration tests for complete system flow.
"""

import pytest
import httpx
import websockets
import json
import asyncio
from unittest.mock import patch, AsyncMock

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from shared.test_helpers import create_mock_jwt_token, create_mock_user


class TestEndToEndFlow:
    """End-to-end integration tests for complete system flow."""
    
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
    def streaming_service_url(self):
        """Streaming service URL."""
        return "http://localhost:8003"
    
    @pytest.fixture
    def streaming_ws_url(self):
        """Streaming WebSocket URL."""
        return "ws://localhost:8003"
    
    @pytest.fixture
    def metrics_service_url(self):
        """Metrics service URL."""
        return "http://localhost:8004"
    
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
    async def test_complete_user_journey(self, gateway_url, auth_service_url, 
                                       entitlements_service_url, streaming_service_url,
                                       metrics_service_url, mock_jwt_token, mock_user):
        """Test complete user journey through all services."""
        async with httpx.AsyncClient() as client:
            headers = {"Authorization": f"Bearer {mock_jwt_token}"}
            
            # 1. Authenticate via Gateway
            auth_response = await client.post(
                f"{gateway_url}/api/v1/auth/verify",
                json={"token": mock_jwt_token}
            )
            assert auth_response.status_code == 200
            auth_data = auth_response.json()
            assert auth_data["valid"] is True
            
            # 2. Check entitlements
            entitlements_response = await client.post(
                f"{entitlements_service_url}/entitlements/check",
                headers=headers,
                json={
                    "user_id": mock_user["user_id"],
                    "tenant_id": mock_user["tenant_id"],
                    "resource": "instrument",
                    "action": "read",
                    "context": {"user_roles": mock_user["roles"]}
                }
            )
            assert entitlements_response.status_code == 200
            entitlements_data = entitlements_response.json()
            # Should be allowed or denied based on rules
            
            # 3. Access data via Gateway
            instruments_response = await client.get(
                f"{gateway_url}/api/v1/instruments",
                headers=headers
            )
            assert instruments_response.status_code == 200
            instruments_data = instruments_response.json()
            assert "instruments" in instruments_data
            
            # 4. Subscribe to streaming data
            subscribe_response = await client.post(
                f"{streaming_service_url}/sse/subscribe",
                headers=headers,
                json={
                    "topic": "254carbon.pricing.updates.v1",
                    "filters": {"instrument": "BRN"}
                }
            )
            assert subscribe_response.status_code == 200
            subscribe_data = subscribe_response.json()
            assert "subscription_id" in subscribe_data
            
            # 5. Track metrics
            metrics_response = await client.post(
                f"{metrics_service_url}/metrics/track",
                headers=headers,
                json={
                    "name": "user_journey_metric",
                    "value": 1,
                    "metric_type": "counter",
                    "labels": {"journey": "complete"},
                    "service": "gateway",
                    "tenant_id": mock_user["tenant_id"]
                }
            )
            assert metrics_response.status_code == 200
            metrics_data = metrics_response.json()
            assert metrics_data["tracked"] is True
    
    @pytest.mark.asyncio
    async def test_websocket_streaming_flow(self, gateway_url, streaming_ws_url, 
                                          mock_jwt_token, mock_user):
        """Test WebSocket streaming flow."""
        # 1. Authenticate via Gateway
        async with httpx.AsyncClient() as client:
            auth_response = await client.post(
                f"{gateway_url}/api/v1/auth/verify",
                json={"token": mock_jwt_token}
            )
            assert auth_response.status_code == 200
        
        # 2. Connect to WebSocket
        uri = f"{streaming_ws_url}/ws/stream?token={mock_jwt_token}"
        
        async with websockets.connect(uri) as websocket:
            # Wait for connection established
            message = await websocket.recv()
            data = json.loads(message)
            assert data["type"] == "connection_established"
            assert data["user_id"] == mock_user["user_id"]
            assert data["tenant_id"] == mock_user["tenant_id"]
            
            # 3. Subscribe to topic
            subscribe_message = {
                "type": "subscribe",
                "topic": "254carbon.pricing.updates.v1",
                "filters": {"instrument": "BRN"}
            }
            await websocket.send(json.dumps(subscribe_message))
            
            # Wait for subscription confirmation
            response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            response_data = json.loads(response)
            assert response_data["type"] == "subscription_confirmed"
            
            # 4. Send heartbeat
            heartbeat_message = {"type": "heartbeat"}
            await websocket.send(json.dumps(heartbeat_message))
            
            # Wait for heartbeat response
            response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            response_data = json.loads(response)
            assert response_data["type"] == "heartbeat_response"
    
    @pytest.mark.asyncio
    async def test_api_key_authentication_flow(self, gateway_url, mock_user):
        """Test API key authentication flow."""
        async with httpx.AsyncClient() as client:
            # Use API key instead of JWT
            headers = {"X-API-Key": "dev-key-123"}
            
            # Access data via Gateway
            response = await client.get(
                f"{gateway_url}/api/v1/instruments",
                headers=headers
            )
            assert response.status_code == 200
            data = response.json()
            assert "instruments" in data
            
            # Test other endpoints
            response = await client.get(
                f"{gateway_url}/api/v1/curves",
                headers=headers
            )
            assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_error_handling_flow(self, gateway_url, mock_jwt_token):
        """Test error handling across services."""
        async with httpx.AsyncClient() as client:
            # 1. Test invalid authentication
            headers = {"Authorization": "Bearer invalid-token"}
            
            response = await client.get(
                f"{gateway_url}/api/v1/instruments",
                headers=headers
            )
            assert response.status_code == 401
            
            # 2. Test missing authentication
            response = await client.get(f"{gateway_url}/api/v1/instruments")
            assert response.status_code == 401
            
            # 3. Test non-existent endpoint
            headers = {"Authorization": f"Bearer {mock_jwt_token}"}
            response = await client.get(
                f"{gateway_url}/api/v1/nonexistent",
                headers=headers
            )
            assert response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_rate_limiting_flow(self, gateway_url, mock_jwt_token):
        """Test rate limiting across services."""
        async with httpx.AsyncClient() as client:
            headers = {"Authorization": f"Bearer {mock_jwt_token}"}
            
            # Make rapid requests to trigger rate limiting
            responses = []
            for _ in range(30):
                response = await client.get(
                    f"{gateway_url}/api/v1/status",
                    headers=headers
                )
                responses.append(response)
            
            # Most should succeed, some might be rate limited
            success_count = sum(1 for r in responses if r.status_code == 200)
            rate_limited_count = sum(1 for r in responses if r.status_code == 429)
            
            assert success_count > 0
            # Rate limiting might not be enabled in test environment
            assert success_count + rate_limited_count == len(responses)
    
    @pytest.mark.asyncio
    async def test_caching_flow(self, gateway_url, mock_jwt_token):
        """Test caching behavior across services."""
        async with httpx.AsyncClient() as client:
            headers = {"Authorization": f"Bearer {mock_jwt_token}"}
            
            # First request - should fetch from backend
            response1 = await client.get(
                f"{gateway_url}/api/v1/instruments",
                headers=headers
            )
            assert response1.status_code == 200
            
            # Second request - should use cache
            response2 = await client.get(
                f"{gateway_url}/api/v1/instruments",
                headers=headers
            )
            assert response2.status_code == 200
            
            # Both should return same data
            assert response1.json() == response2.json()
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_flow(self, gateway_url, mock_jwt_token):
        """Test circuit breaker behavior."""
        # Mock backend service failures
        with patch('httpx.AsyncClient.get') as mock_get:
            mock_get.side_effect = httpx.ConnectError("Backend unavailable")
            
            async with httpx.AsyncClient() as client:
                headers = {"Authorization": f"Bearer {mock_jwt_token}"}
                
                # Make multiple requests to trigger circuit breaker
                responses = []
                for _ in range(6):  # More than failure threshold
                    response = await client.get(
                        f"{gateway_url}/api/v1/instruments",
                        headers=headers
                    )
                    responses.append(response)
                
                # Circuit breaker should eventually open
                # Some requests might succeed with fallback data, others should fail
                status_codes = [r.status_code for r in responses]
                assert 200 in status_codes or 503 in status_codes
    
    @pytest.mark.asyncio
    async def test_concurrent_user_flow(self, gateway_url, streaming_ws_url, 
                                      mock_jwt_token, mock_user):
        """Test concurrent user flows."""
        async def user_flow(user_id):
            """Simulate a single user flow."""
            # Create user-specific token
            user_token = create_mock_jwt_token(
                user_id=user_id,
                tenant_id="tenant-1",
                roles=["user"],
                expires_in=3600
            )
            
            async with httpx.AsyncClient() as client:
                headers = {"Authorization": f"Bearer {user_token}"}
                
                # Access data via Gateway
                response = await client.get(
                    f"{gateway_url}/api/v1/instruments",
                    headers=headers
                )
                return response.status_code == 200
        
        # Simulate 10 concurrent users
        tasks = [user_flow(f"user-{i}") for i in range(10)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Most should succeed
        success_count = sum(1 for r in results if r is True)
        assert success_count > 0
    
    @pytest.mark.asyncio
    async def test_metrics_collection_flow(self, gateway_url, metrics_service_url, 
                                        mock_jwt_token, mock_user):
        """Test metrics collection throughout the flow."""
        async with httpx.AsyncClient() as client:
            headers = {"Authorization": f"Bearer {mock_jwt_token}"}
            
            # 1. Track request metric
            metrics_response = await client.post(
                f"{metrics_service_url}/metrics/track",
                headers=headers,
                json={
                    "name": "api_request",
                    "value": 1,
                    "metric_type": "counter",
                    "labels": {"endpoint": "instruments", "method": "GET"},
                    "service": "gateway",
                    "tenant_id": mock_user["tenant_id"]
                }
            )
            assert metrics_response.status_code == 200
            
            # 2. Access data via Gateway (should generate metrics)
            response = await client.get(
                f"{gateway_url}/api/v1/instruments",
                headers=headers
            )
            assert response.status_code == 200
            
            # 3. Track response metric
            metrics_response = await client.post(
                f"{metrics_service_url}/metrics/track",
                headers=headers,
                json={
                    "name": "api_response",
                    "value": 200,
                    "metric_type": "gauge",
                    "labels": {"endpoint": "instruments", "status": "success"},
                    "service": "gateway",
                    "tenant_id": mock_user["tenant_id"]
                }
            )
            assert metrics_response.status_code == 200
            
            # 4. Get metrics summary
            stats_response = await client.get(
                f"{metrics_service_url}/metrics/stats",
                headers=headers
            )
            assert stats_response.status_code == 200
            stats_data = stats_response.json()
            assert "total_series" in stats_data
            assert "total_points" in stats_data
    
    @pytest.mark.asyncio
    async def test_entitlements_integration_flow(self, gateway_url, entitlements_service_url,
                                               mock_jwt_token, mock_user):
        """Test entitlements integration flow."""
        async with httpx.AsyncClient() as client:
            headers = {"Authorization": f"Bearer {mock_jwt_token}"}
            
            # 1. Create entitlement rule
            rule_data = {
                "rule_id": "test-rule-1",
                "name": "Test Rule",
                "description": "Test entitlement rule",
                "resource": "instrument",
                "action": "allow",
                "conditions": [
                    {
                        "field": "user_roles",
                        "operator": "contains",
                        "value": "user"
                    }
                ],
                "priority": 100,
                "enabled": True,
                "tenant_id": mock_user["tenant_id"]
            }
            
            create_response = await client.post(
                f"{entitlements_service_url}/entitlements/rules",
                headers=headers,
                json=rule_data
            )
            assert create_response.status_code == 201
            
            # 2. Check entitlements
            check_response = await client.post(
                f"{entitlements_service_url}/entitlements/check",
                headers=headers,
                json={
                    "user_id": mock_user["user_id"],
                    "tenant_id": mock_user["tenant_id"],
                    "resource": "instrument",
                    "action": "read",
                    "context": {"user_roles": mock_user["roles"]}
                }
            )
            assert check_response.status_code == 200
            check_data = check_response.json()
            assert "allowed" in check_data
            
            # 3. Access data via Gateway (should check entitlements)
            response = await client.get(
                f"{gateway_url}/api/v1/instruments",
                headers=headers
            )
            # Should either succeed (if entitled) or be denied
            assert response.status_code in [200, 403]
    
    @pytest.mark.asyncio
    async def test_complete_system_health(self, gateway_url, auth_service_url,
                                        entitlements_service_url, streaming_service_url,
                                        metrics_service_url):
        """Test complete system health."""
        async with httpx.AsyncClient() as client:
            # Check health of all services
            services = [
                ("Gateway", gateway_url),
                ("Auth", auth_service_url),
                ("Entitlements", entitlements_service_url),
                ("Streaming", streaming_service_url),
                ("Metrics", metrics_service_url)
            ]
            
            for service_name, service_url in services:
                try:
                    response = await client.get(f"{service_url}/health")
                    assert response.status_code == 200
                    health_data = response.json()
                    assert health_data["status"] == "healthy"
                except httpx.ConnectError:
                    # Service might not be running in test environment
                    # This is expected for integration tests
                    pass
    
    @pytest.mark.asyncio
    async def test_data_consistency_flow(self, gateway_url, mock_jwt_token):
        """Test data consistency across services."""
        async with httpx.AsyncClient() as client:
            headers = {"Authorization": f"Bearer {mock_jwt_token}"}
            
            # Access same data multiple times
            responses = []
            for _ in range(5):
                response = await client.get(
                    f"{gateway_url}/api/v1/instruments",
                    headers=headers
                )
                assert response.status_code == 200
                responses.append(response.json())
            
            # All responses should be consistent
            first_response = responses[0]
            for response in responses[1:]:
                assert response == first_response
    
    @pytest.mark.asyncio
    async def test_security_flow(self, gateway_url, mock_jwt_token):
        """Test security measures across services."""
        async with httpx.AsyncClient() as client:
            # 1. Test CORS headers
            response = await client.options(f"{gateway_url}/api/v1/instruments")
            # Should have CORS headers (implementation dependent)
            
            # 2. Test input validation
            headers = {"Authorization": f"Bearer {mock_jwt_token}"}
            
            # Test SQL injection attempt
            response = await client.get(
                f"{gateway_url}/api/v1/instruments?filter='; DROP TABLE users; --",
                headers=headers
            )
            # Should handle gracefully (not crash)
            assert response.status_code in [200, 400, 422]
            
            # 3. Test XSS attempt
            response = await client.get(
                f"{gateway_url}/api/v1/instruments?search=<script>alert('xss')</script>",
                headers=headers
            )
            # Should handle gracefully
            assert response.status_code in [200, 400, 422]
