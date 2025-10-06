"""
Unit tests for Streaming main service.
"""

import pytest
import json
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from fastapi import FastAPI

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from service_streaming.app.main import StreamingService, create_app
from shared.errors import AccessLayerException


class TestStreamingService:
    """Test cases for StreamingService."""

    @pytest.fixture
    def streaming_service(self):
        """Create StreamingService instance."""
        return StreamingService()

    @pytest.fixture
    def app(self):
        """Create FastAPI app instance."""
        return create_app()

    @pytest.fixture
    def client(self, app):
        """Create test client."""
        return TestClient(app)

    @pytest.fixture
    def mock_user_info(self):
        """Mock user info."""
        return {
            "user_id": "user-123",
            "tenant_id": "tenant-1",
            "roles": ["user", "analyst"],
            "email": "test@example.com"
        }

    @pytest.fixture
    def mock_jwt_token(self):
        """Mock JWT token."""
        return "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test.signature"

    def test_root_endpoint(self, client):
        """Test root endpoint."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "streaming"
        assert data["message"] == "254Carbon Access Layer - Streaming Service"
        assert "websocket" in data["capabilities"]
        assert "sse" in data["capabilities"]
        assert "kafka" in data["capabilities"]

    def test_health_endpoint(self, client):
        """Test health endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "streaming"
        assert data["status"] == "ok"

    @patch('service_streaming.app.main.StreamingService._check_dependencies')
    def test_health_with_dependencies(self, mock_check_deps, client):
        """Test health endpoint with dependency checks."""
        mock_check_deps.return_value = {
            "kafka": "ok",
            "auth": "ok",
            "entitlements": "ok"
        }

        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["dependencies"]["kafka"] == "ok"
        assert data["dependencies"]["auth"] == "ok"

    def test_stats_endpoint(self, client):
        """Test stats endpoint."""
        response = client.get("/stats")
        assert response.status_code == 200
        data = response.json()
        assert "websocket" in data
        assert "sse" in data
        assert "subscriptions" in data
        assert "kafka" in data

    def test_service_initialization(self, streaming_service):
        """Test service initialization."""
        assert streaming_service.name == "streaming"
        assert streaming_service.port == 8001
        assert streaming_service.kafka_consumer is not None
        assert streaming_service.kafka_producer is not None
        assert streaming_service.ws_manager is not None
        assert streaming_service.sse_manager is not None
        assert streaming_service.subscription_manager is not None
        assert streaming_service.auth_client is not None

    def test_observability_setup(self, streaming_service):
        """Test observability setup."""
        assert streaming_service.observability is not None
        assert hasattr(streaming_service.observability, 'log_request')
        assert hasattr(streaming_service.observability, 'log_error')
        assert hasattr(streaming_service.observability, 'log_business_event')

    @patch('service_streaming.app.main.AuthClient.verify_websocket_token')
    async def test_authenticate_websocket_success(self, mock_verify, streaming_service, mock_user_info):
        """Test successful WebSocket authentication."""
        mock_verify.return_value = {
            "valid": True,
            "user_info": mock_user_info
        }

        result = await streaming_service._authenticate_websocket("test-token")

        assert result == mock_user_info
        mock_verify.assert_called_once_with("test-token")

    @patch('service_streaming.app.main.AuthClient.verify_websocket_token')
    async def test_authenticate_websocket_invalid_token(self, mock_verify, streaming_service):
        """Test WebSocket authentication with invalid token."""
        mock_verify.return_value = {
            "valid": False,
            "error": "Token expired"
        }

        with pytest.raises(AccessLayerException) as exc_info:
            await streaming_service._authenticate_websocket("invalid-token")

        assert exc_info.value.code == "INVALID_TOKEN"

    async def test_authenticate_websocket_missing_token(self, streaming_service):
        """Test WebSocket authentication with missing token."""
        with pytest.raises(AccessLayerException) as exc_info:
            await streaming_service._authenticate_websocket(None)

        assert exc_info.value.code == "MISSING_TOKEN"

    @patch('service_streaming.app.main.AuthClient.verify_token')
    async def test_authenticate_sse_success(self, mock_verify, streaming_service, mock_user_info):
        """Test successful SSE authentication."""
        mock_verify.return_value = {
            "valid": True,
            "user_info": mock_user_info
        }

        result = await streaming_service._authenticate_sse("test-token")

        assert result == mock_user_info
        mock_verify.assert_called_once_with("test-token")

    @patch('service_streaming.app.main.AuthClient.verify_token')
    async def test_authenticate_sse_invalid_token(self, mock_verify, streaming_service):
        """Test SSE authentication with invalid token."""
        mock_verify.return_value = {
            "valid": False,
            "error": "Token expired"
        }

        with pytest.raises(AccessLayerException) as exc_info:
            await streaming_service._authenticate_sse("invalid-token")

        assert exc_info.value.code == "INVALID_TOKEN"

    async def test_authenticate_sse_missing_token(self, streaming_service):
        """Test SSE authentication with missing token."""
        with pytest.raises(AccessLayerException) as exc_info:
            await streaming_service._authenticate_sse(None)

        assert exc_info.value.code == "MISSING_TOKEN"

    @patch('service_streaming.app.main.KafkaConsumerManager.is_running')
    @patch('service_streaming.app.main.KafkaProducerManager.is_running')
    async def test_check_dependencies(self, mock_producer_running, mock_consumer_running, streaming_service):
        """Test dependency checks."""
        mock_consumer_running.return_value = True
        mock_producer_running.return_value = True

        dependencies = await streaming_service._check_dependencies()

        assert dependencies["kafka"] == "ok"
        assert dependencies["auth"] == "ok"
        assert dependencies["entitlements"] == "ok"

    @patch('service_streaming.app.main.KafkaConsumerManager.is_running')
    async def test_check_dependencies_kafka_error(self, mock_consumer_running, streaming_service):
        """Test dependency checks with Kafka error."""
        mock_consumer_running.return_value = False

        dependencies = await streaming_service._check_dependencies()

        assert dependencies["kafka"] == "error"
        assert dependencies["auth"] == "ok"
        assert dependencies["entitlements"] == "ok"

    @patch('service_streaming.app.main.KafkaConsumerManager.start')
    @patch('service_streaming.app.main.KafkaProducerManager.start')
    @patch('service_streaming.app.main.WebSocketConnectionManager.start')
    async def test_start_service(self, mock_ws_start, mock_producer_start, mock_consumer_start, streaming_service):
        """Test service start."""
        await streaming_service.start()

        mock_consumer_start.assert_called_once()
        mock_producer_start.assert_called_once()
        mock_ws_start.assert_called_once()

    @patch('service_streaming.app.main.KafkaConsumerManager.stop')
    @patch('service_streaming.app.main.KafkaProducerManager.stop')
    @patch('service_streaming.app.main.WebSocketConnectionManager.stop')
    async def test_stop_service(self, mock_ws_stop, mock_producer_stop, mock_consumer_stop, streaming_service):
        """Test service stop."""
        await streaming_service.stop()

        mock_consumer_stop.assert_called_once()
        mock_producer_stop.assert_called_once()
        mock_ws_stop.assert_called_once()

    @patch('service_streaming.app.main.StreamingService._authenticate_websocket')
    @patch('service_streaming.app.main.WebSocketConnectionManager.add_connection')
    @patch('service_streaming.app.main.KafkaProducerManager.send_connection_event')
    async def test_handle_kafka_message(self, mock_send_event, mock_add_connection, mock_auth, streaming_service):
        """Test Kafka message handling."""
        # Mock Kafka message
        mock_message = MagicMock()
        mock_message.topic = "test-topic"
        mock_message.value = b'{"test": "data"}'
        mock_message.timestamp = 1640995200000
        mock_message.partition = 0
        mock_message.offset = 123

        # Mock subscription manager
        with patch.object(streaming_service.subscription_manager, 'get_topic_subscribers', new_callable=AsyncMock) as mock_get_subscribers:
            mock_get_subscribers.return_value = ["connection-1"]

            # Mock WebSocket manager broadcast
            with patch.object(streaming_service.ws_manager, 'broadcast_to_topic', new_callable=AsyncMock) as mock_ws_broadcast:
                mock_ws_broadcast.return_value = 1

                # Mock SSE manager broadcast
                with patch.object(streaming_service.sse_manager, 'broadcast_to_topic', new_callable=AsyncMock) as mock_sse_broadcast:
                    mock_sse_broadcast.return_value = 1

                    await streaming_service._handle_kafka_message(mock_message)

                    mock_get_subscribers.assert_called_once_with("test-topic")
                    mock_ws_broadcast.assert_called_once()
                    mock_sse_broadcast.assert_called_once()

    @patch('service_streaming.app.main.StreamingService._authenticate_websocket')
    @patch('service_streaming.app.main.WebSocketConnectionManager.add_connection')
    @patch('service_streaming.app.main.KafkaProducerManager.send_connection_event')
    async def test_handle_kafka_message_error(self, mock_send_event, mock_add_connection, mock_auth, streaming_service):
        """Test Kafka message handling with error."""
        # Mock Kafka message with invalid JSON
        mock_message = MagicMock()
        mock_message.topic = "test-topic"
        mock_message.value = b'invalid json'
        mock_message.timestamp = 1640995200000
        mock_message.partition = 0
        mock_message.offset = 123

        # Should handle error gracefully
        await streaming_service._handle_kafka_message(mock_message)

        # No exceptions should be raised

    def test_sse_endpoint_requires_token(self, client):
        """Test SSE endpoint requires token."""
        response = client.get("/sse/stream")
        assert response.status_code == 401

    @patch('service_streaming.app.main.StreamingService._authenticate_sse')
    @patch('service_streaming.app.main.SSEStreamManager.create_connection')
    def test_sse_endpoint_success(self, mock_create_connection, mock_auth, client, mock_user_info):
        """Test SSE endpoint success."""
        mock_auth.return_value = mock_user_info
        mock_create_connection.return_value = "connection-123"

        response = client.get("/sse/stream?token=test-token")

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"

    @patch('service_streaming.app.main.StreamingService._authenticate_sse')
    def test_sse_endpoint_auth_error(self, mock_auth, client):
        """Test SSE endpoint authentication error."""
        mock_auth.side_effect = AccessLayerException("INVALID_TOKEN", "Invalid token")

        response = client.get("/sse/stream?token=invalid-token")

        assert response.status_code == 401
        data = response.json()
        assert data["detail"]["error"] == "INVALID_TOKEN"

    @patch('service_streaming.app.main.SSEStreamManager.subscribe_to_topic')
    def test_sse_subscribe_success(self, mock_subscribe, client):
        """Test SSE subscription success."""
        mock_subscribe.return_value = True

        response = client.post(
            "/sse/subscribe",
            params={
                "connection_id": "connection-123",
                "topic": "test-topic",
                "filters": '{"commodity": "oil"}'
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["topic"] == "test-topic"

    @patch('service_streaming.app.main.SSEStreamManager.subscribe_to_topic')
    def test_sse_subscribe_failure(self, mock_subscribe, client):
        """Test SSE subscription failure."""
        mock_subscribe.return_value = False

        response = client.post(
            "/sse/subscribe",
            params={
                "connection_id": "connection-123",
                "topic": "test-topic"
            }
        )

        assert response.status_code == 400
        data = response.json()
        assert data["detail"] == "Subscription failed"

    def test_sse_subscribe_invalid_filters(self, client):
        """Test SSE subscription with invalid filters."""
        response = client.post(
            "/sse/subscribe",
            params={
                "connection_id": "connection-123",
                "topic": "test-topic",
                "filters": "invalid json"
            }
        )

        assert response.status_code == 500

    def test_service_configuration(self, streaming_service):
        """Test service configuration."""
        assert streaming_service.config.kafka_bootstrap is not None
        assert streaming_service.config.auth_service_url is not None
        assert streaming_service.config.max_ws_connections > 0
        assert streaming_service.config.max_sse_connections > 0
        assert streaming_service.config.heartbeat_timeout > 0

    @patch('service_streaming.app.main.KafkaConsumerManager.start')
    @patch('service_streaming.app.main.KafkaProducerManager.start')
    @patch('service_streaming.app.main.WebSocketConnectionManager.start')
    async def test_service_lifecycle(self, mock_ws_start, mock_producer_start, mock_consumer_start, streaming_service):
        """Test complete service lifecycle."""
        # Start service
        await streaming_service.start()

        # Verify all components started
        mock_consumer_start.assert_called_once()
        mock_producer_start.assert_called_once()
        mock_ws_start.assert_called_once()

        # Stop service
        with patch('service_streaming.app.main.KafkaConsumerManager.stop') as mock_consumer_stop, \
             patch('service_streaming.app.main.KafkaProducerManager.stop') as mock_producer_stop, \
             patch('service_streaming.app.main.WebSocketConnectionManager.stop') as mock_ws_stop:

            await streaming_service.stop()

            mock_consumer_stop.assert_called_once()
            mock_producer_stop.assert_called_once()
            mock_ws_stop.assert_called_once()