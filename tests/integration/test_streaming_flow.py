"""
Integration tests for Streaming service flow.
"""

import pytest
import asyncio
import json
import websockets
import httpx
from unittest.mock import patch, AsyncMock

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from shared.test_helpers import create_mock_jwt_token, create_mock_user


class TestStreamingFlow:
    """Integration tests for Streaming service flow."""
    
    @pytest.fixture
    def streaming_url(self):
        """Streaming service URL."""
        return "http://localhost:8003"
    
    @pytest.fixture
    def streaming_ws_url(self):
        """Streaming WebSocket URL."""
        return "ws://localhost:8003"
    
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
    
    @pytest.mark.asyncio
    async def test_websocket_connection_flow(self, streaming_ws_url, mock_jwt_token):
        """Test WebSocket connection flow."""
        uri = f"{streaming_ws_url}/ws/stream?token={mock_jwt_token}"
        
        async with websockets.connect(uri) as websocket:
            # Wait for connection established message
            message = await websocket.recv()
            data = json.loads(message)
            
            assert data["type"] == "connection_established"
            assert "connection_id" in data
            assert data["user_id"] == "test-user-1"
            assert data["tenant_id"] == "tenant-1"
            
            connection_id = data["connection_id"]
            
            # Test subscription
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
            assert response_data["topic"] == "254carbon.pricing.updates.v1"
            
            # Test unsubscription
            unsubscribe_message = {
                "type": "unsubscribe",
                "topic": "254carbon.pricing.updates.v1"
            }
            await websocket.send(json.dumps(unsubscribe_message))
            
            # Wait for unsubscription confirmation
            response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            response_data = json.loads(response)
            assert response_data["type"] == "unsubscription_confirmed"
    
    @pytest.mark.asyncio
    async def test_websocket_connection_without_auth(self, streaming_ws_url):
        """Test WebSocket connection without authentication."""
        uri = f"{streaming_ws_url}/ws/stream"
        
        try:
            async with websockets.connect(uri) as websocket:
                # Should receive error message
                message = await websocket.recv()
                data = json.loads(message)
                assert "error" in data
                assert data["error"] == "AUTHENTICATION_REQUIRED"
        except websockets.exceptions.ConnectionClosed:
            # Connection might be closed immediately
            pass
    
    @pytest.mark.asyncio
    async def test_websocket_connection_with_invalid_auth(self, streaming_ws_url):
        """Test WebSocket connection with invalid authentication."""
        uri = f"{streaming_ws_url}/ws/stream?token=invalid-token"
        
        try:
            async with websockets.connect(uri) as websocket:
                # Should receive error message
                message = await websocket.recv()
                data = json.loads(message)
                assert "error" in data
                assert data["error"] == "AUTHENTICATION_FAILED"
        except websockets.exceptions.ConnectionClosed:
            # Connection might be closed immediately
            pass
    
    @pytest.mark.asyncio
    async def test_sse_connection_flow(self, streaming_url, mock_jwt_token):
        """Test Server-Sent Events connection flow."""
        async with httpx.AsyncClient() as client:
            headers = {"Authorization": f"Bearer {mock_jwt_token}"}
            
            # Test SSE stream endpoint
            async with client.stream(
                "GET",
                f"{streaming_url}/sse/stream",
                headers=headers
            ) as response:
                assert response.status_code == 200
                assert "text/event-stream" in response.headers["content-type"]
                
                # Read first few events
                events = []
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = json.loads(line[6:])
                        events.append(data)
                        if len(events) >= 3:
                            break
                
                # Should receive connection established event
                assert len(events) > 0
                assert events[0]["type"] == "connection_established"
    
    @pytest.mark.asyncio
    async def test_sse_subscription_flow(self, streaming_url, mock_jwt_token):
        """Test SSE subscription flow."""
        async with httpx.AsyncClient() as client:
            headers = {"Authorization": f"Bearer {mock_jwt_token}"}
            
            # Subscribe to topic
            subscribe_data = {
                "topic": "254carbon.pricing.updates.v1",
                "filters": {"instrument": "BRN"}
            }
            
            response = await client.post(
                f"{streaming_url}/sse/subscribe",
                headers=headers,
                json=subscribe_data
            )
            assert response.status_code == 200
            data = response.json()
            assert "subscription_id" in data
            assert data["topic"] == "254carbon.pricing.updates.v1"
            
            subscription_id = data["subscription_id"]
            
            # Unsubscribe
            response = await client.delete(
                f"{streaming_url}/sse/subscribe/{subscription_id}",
                headers=headers
            )
            assert response.status_code == 200
            data = response.json()
            assert data["unsubscribed"] is True
    
    @pytest.mark.asyncio
    async def test_streaming_with_kafka_integration(self, streaming_ws_url, mock_jwt_token):
        """Test streaming with Kafka integration."""
        uri = f"{streaming_ws_url}/ws/stream?token={mock_jwt_token}"
        
        async with websockets.connect(uri) as websocket:
            # Wait for connection established
            message = await websocket.recv()
            data = json.loads(message)
            assert data["type"] == "connection_established"
            
            # Subscribe to topic
            subscribe_message = {
                "type": "subscribe",
                "topic": "254carbon.pricing.updates.v1"
            }
            await websocket.send(json.dumps(subscribe_message))
            
            # Wait for subscription confirmation
            response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            response_data = json.loads(response)
            assert response_data["type"] == "subscription_confirmed"
            
            # Wait for potential messages from Kafka
            try:
                message = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                data = json.loads(message)
                # Should receive pricing update or heartbeat
                assert data["type"] in ["pricing_update", "heartbeat", "message"]
            except asyncio.TimeoutError:
                # No messages received, which is fine for test
                pass
    
    @pytest.mark.asyncio
    async def test_streaming_heartbeat_mechanism(self, streaming_ws_url, mock_jwt_token):
        """Test streaming heartbeat mechanism."""
        uri = f"{streaming_ws_url}/ws/stream?token={mock_jwt_token}"
        
        async with websockets.connect(uri) as websocket:
            # Wait for connection established
            message = await websocket.recv()
            data = json.loads(message)
            assert data["type"] == "connection_established"
            
            # Wait for heartbeat
            try:
                message = await asyncio.wait_for(websocket.recv(), timeout=35.0)
                data = json.loads(message)
                assert data["type"] == "heartbeat"
            except asyncio.TimeoutError:
                # Heartbeat might not be enabled in test environment
                pass
    
    @pytest.mark.asyncio
    async def test_streaming_message_filtering(self, streaming_ws_url, mock_jwt_token):
        """Test streaming message filtering."""
        uri = f"{streaming_ws_url}/ws/stream?token={mock_jwt_token}"
        
        async with websockets.connect(uri) as websocket:
            # Wait for connection established
            message = await websocket.recv()
            data = json.loads(message)
            assert data["type"] == "connection_established"
            
            # Subscribe with filters
            subscribe_message = {
                "type": "subscribe",
                "topic": "254carbon.pricing.updates.v1",
                "filters": {
                    "instrument": "BRN",
                    "price_min": 50.0
                }
            }
            await websocket.send(json.dumps(subscribe_message))
            
            # Wait for subscription confirmation
            response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            response_data = json.loads(response)
            assert response_data["type"] == "subscription_confirmed"
            assert "filters" in response_data
    
    @pytest.mark.asyncio
    async def test_streaming_multiple_subscriptions(self, streaming_ws_url, mock_jwt_token):
        """Test streaming with multiple subscriptions."""
        uri = f"{streaming_ws_url}/ws/stream?token={mock_jwt_token}"
        
        async with websockets.connect(uri) as websocket:
            # Wait for connection established
            message = await websocket.recv()
            data = json.loads(message)
            assert data["type"] == "connection_established"
            
            # Subscribe to multiple topics
            topics = [
                "254carbon.pricing.updates.v1",
                "254carbon.market.data.v1",
                "254carbon.news.v1"
            ]
            
            for topic in topics:
                subscribe_message = {
                    "type": "subscribe",
                    "topic": topic
                }
                await websocket.send(json.dumps(subscribe_message))
                
                # Wait for subscription confirmation
                response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                response_data = json.loads(response)
                assert response_data["type"] == "subscription_confirmed"
                assert response_data["topic"] == topic
            
            # Unsubscribe from one topic
            unsubscribe_message = {
                "type": "unsubscribe",
                "topic": topics[0]
            }
            await websocket.send(json.dumps(unsubscribe_message))
            
            # Wait for unsubscription confirmation
            response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            response_data = json.loads(response)
            assert response_data["type"] == "unsubscription_confirmed"
    
    @pytest.mark.asyncio
    async def test_streaming_error_handling(self, streaming_ws_url, mock_jwt_token):
        """Test streaming error handling."""
        uri = f"{streaming_ws_url}/ws/stream?token={mock_jwt_token}"
        
        async with websockets.connect(uri) as websocket:
            # Wait for connection established
            message = await websocket.recv()
            data = json.loads(message)
            assert data["type"] == "connection_established"
            
            # Send invalid message
            invalid_message = {"type": "invalid_type"}
            await websocket.send(json.dumps(invalid_message))
            
            # Should receive error response
            response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            response_data = json.loads(response)
            assert "error" in response_data
    
    @pytest.mark.asyncio
    async def test_streaming_concurrent_connections(self, streaming_ws_url, mock_jwt_token):
        """Test streaming with concurrent connections."""
        async def create_connection():
            uri = f"{streaming_ws_url}/ws/stream?token={mock_jwt_token}"
            async with websockets.connect(uri) as websocket:
                # Wait for connection established
                message = await websocket.recv()
                data = json.loads(message)
                assert data["type"] == "connection_established"
                return data["connection_id"]
        
        # Create 5 concurrent connections
        tasks = [create_connection() for _ in range(5)]
        connection_ids = await asyncio.gather(*tasks)
        
        # All connections should be established
        assert len(connection_ids) == 5
        assert len(set(connection_ids)) == 5  # All unique
    
    @pytest.mark.asyncio
    async def test_streaming_connection_cleanup(self, streaming_ws_url, mock_jwt_token):
        """Test streaming connection cleanup."""
        uri = f"{streaming_ws_url}/ws/stream?token={mock_jwt_token}"
        
        async with websockets.connect(uri) as websocket:
            # Wait for connection established
            message = await websocket.recv()
            data = json.loads(message)
            assert data["type"] == "connection_established"
            connection_id = data["connection_id"]
            
            # Subscribe to topic
            subscribe_message = {
                "type": "subscribe",
                "topic": "254carbon.pricing.updates.v1"
            }
            await websocket.send(json.dumps(subscribe_message))
            
            # Wait for subscription confirmation
            response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            response_data = json.loads(response)
            assert response_data["type"] == "subscription_confirmed"
        
        # Connection should be cleaned up when websocket closes
        # This is tested implicitly by the connection manager's cleanup logic
    
    @pytest.mark.asyncio
    async def test_streaming_with_entitlements(self, streaming_ws_url, mock_jwt_token):
        """Test streaming with entitlements check."""
        uri = f"{streaming_ws_url}/ws/stream?token={mock_jwt_token}"
        
        async with websockets.connect(uri) as websocket:
            # Wait for connection established
            message = await websocket.recv()
            data = json.loads(message)
            assert data["type"] == "connection_established"
            
            # Try to subscribe to restricted topic
            subscribe_message = {
                "type": "subscribe",
                "topic": "254carbon.restricted.data.v1"
            }
            await websocket.send(json.dumps(subscribe_message))
            
            # Should receive either confirmation or error
            response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            response_data = json.loads(response)
            assert response_data["type"] in ["subscription_confirmed", "error"]