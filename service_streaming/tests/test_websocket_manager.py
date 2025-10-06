"""
Unit tests for Streaming WebSocket Connection Manager.
"""

import pytest
import uuid
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
from typing import Dict, Any

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from service_streaming.app.ws.connection_manager import WebSocketConnectionManager, WebSocketConnection
from shared.errors import AccessLayerException


class TestWebSocketConnectionManager:
    """Test cases for WebSocketConnectionManager."""

    @pytest.fixture
    def ws_manager(self):
        """Create WebSocketConnectionManager instance."""
        return WebSocketConnectionManager(max_connections=100, heartbeat_timeout=30)

    @pytest.fixture
    def mock_websocket(self):
        """Mock WebSocket object."""
        websocket = AsyncMock()
        websocket.close = AsyncMock()
        websocket.send_text = AsyncMock()
        return websocket

    @pytest.fixture
    def mock_connection_data(self):
        """Mock connection data."""
        return {
            "user_id": "user-123",
            "tenant_id": "tenant-1",
            "metadata": {"client_type": "web"}
        }

    @pytest.mark.asyncio
    async def test_start_success(self, ws_manager):
        """Test successful manager start."""
        await ws_manager.start()

        assert ws_manager.running is True
        assert ws_manager._heartbeat_task is not None

    @pytest.mark.asyncio
    async def test_stop_success(self, ws_manager, mock_websocket):
        """Test successful manager stop."""
        # Add a connection first
        connection_id = await ws_manager.add_connection(
            websocket=mock_websocket,
            user_id="user-123",
            tenant_id="tenant-1"
        )

        await ws_manager.start()
        await ws_manager.stop()

        assert ws_manager.running is False
        mock_websocket.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_connection_success(self, ws_manager, mock_websocket, mock_connection_data):
        """Test successful connection addition."""
        connection_id = await ws_manager.add_connection(
            websocket=mock_websocket,
            user_id=mock_connection_data["user_id"],
            tenant_id=mock_connection_data["tenant_id"],
            metadata=mock_connection_data["metadata"]
        )

        assert connection_id is not None
        assert connection_id in ws_manager.connections
        assert ws_manager.connections[connection_id].user_id == "user-123"
        assert ws_manager.connections[connection_id].tenant_id == "tenant-1"

        # Check indices
        assert "user-123" in ws_manager.user_connections
        assert connection_id in ws_manager.user_connections["user-123"]
        assert "tenant-1" in ws_manager.tenant_connections
        assert connection_id in ws_manager.tenant_connections["tenant-1"]

    @pytest.mark.asyncio
    async def test_add_connection_max_limit(self, ws_manager, mock_websocket):
        """Test connection addition when max limit reached."""
        # Fill up connections to max limit
        for i in range(100):
            mock_ws = AsyncMock()
            await ws_manager.add_connection(
                websocket=mock_ws,
                user_id=f"user-{i}",
                tenant_id=f"tenant-{i}"
            )

        # Try to add one more connection
        with pytest.raises(AccessLayerException) as exc_info:
            await ws_manager.add_connection(
                websocket=mock_websocket,
                user_id="user-overflow",
                tenant_id="tenant-overflow"
            )

        assert exc_info.value.code == "CONNECTION_LIMIT_EXCEEDED"

    @pytest.mark.asyncio
    async def test_remove_connection_success(self, ws_manager, mock_websocket):
        """Test successful connection removal."""
        connection_id = await ws_manager.add_connection(
            websocket=mock_websocket,
            user_id="user-123",
            tenant_id="tenant-1"
        )

        await ws_manager.remove_connection(connection_id)

        assert connection_id not in ws_manager.connections
        assert connection_id not in ws_manager.user_connections["user-123"]
        assert connection_id not in ws_manager.tenant_connections["tenant-1"]

    @pytest.mark.asyncio
    async def test_remove_connection_not_found(self, ws_manager):
        """Test connection removal when connection not found."""
        connection_id = str(uuid.uuid4())

        # Should not raise exception
        await ws_manager.remove_connection(connection_id)

    @pytest.mark.asyncio
    async def test_get_connection_success(self, ws_manager, mock_websocket):
        """Test successful connection retrieval."""
        connection_id = await ws_manager.add_connection(
            websocket=mock_websocket,
            user_id="user-123",
            tenant_id="tenant-1"
        )

        connection = ws_manager.get_connection(connection_id)

        assert connection is not None
        assert connection.connection_id == connection_id
        assert connection.user_id == "user-123"
        assert connection.tenant_id == "tenant-1"

    @pytest.mark.asyncio
    async def test_get_connection_not_found(self, ws_manager):
        """Test connection retrieval when connection not found."""
        connection_id = str(uuid.uuid4())

        connection = ws_manager.get_connection(connection_id)

        assert connection is None

    @pytest.mark.asyncio
    async def test_subscribe_to_topic_success(self, ws_manager, mock_websocket):
        """Test successful topic subscription."""
        connection_id = await ws_manager.add_connection(
            websocket=mock_websocket,
            user_id="user-123",
            tenant_id="tenant-1"
        )

        topic = "test-topic"
        filters = {"commodity": "oil"}

        success = await ws_manager.subscribe_to_topic(connection_id, topic, filters)

        assert success is True
        assert topic in ws_manager.connections[connection_id].subscribed_topics
        assert ws_manager.connections[connection_id].filters[topic] == filters
        assert connection_id in ws_manager.topic_subscribers[topic]

    @pytest.mark.asyncio
    async def test_subscribe_to_topic_connection_not_found(self, ws_manager):
        """Test topic subscription when connection not found."""
        connection_id = str(uuid.uuid4())
        topic = "test-topic"

        success = await ws_manager.subscribe_to_topic(connection_id, topic)

        assert success is False

    @pytest.mark.asyncio
    async def test_unsubscribe_from_topic_success(self, ws_manager, mock_websocket):
        """Test successful topic unsubscription."""
        connection_id = await ws_manager.add_connection(
            websocket=mock_websocket,
            user_id="user-123",
            tenant_id="tenant-1"
        )

        topic = "test-topic"
        await ws_manager.subscribe_to_topic(connection_id, topic)

        success = await ws_manager.unsubscribe_from_topic(connection_id, topic)

        assert success is True
        assert topic not in ws_manager.connections[connection_id].subscribed_topics
        assert connection_id not in ws_manager.topic_subscribers[topic]

    @pytest.mark.asyncio
    async def test_broadcast_to_topic_success(self, ws_manager, mock_websocket):
        """Test successful topic broadcast."""
        connection_id = await ws_manager.add_connection(
            websocket=mock_websocket,
            user_id="user-123",
            tenant_id="tenant-1"
        )

        topic = "test-topic"
        await ws_manager.subscribe_to_topic(connection_id, topic)

        message = {"type": "test", "data": "test-data"}

        sent_count = await ws_manager.broadcast_to_topic(topic, message)

        assert sent_count == 1
        mock_websocket.send_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_broadcast_to_topic_no_subscribers(self, ws_manager):
        """Test topic broadcast with no subscribers."""
        topic = "test-topic"
        message = {"type": "test", "data": "test-data"}

        sent_count = await ws_manager.broadcast_to_topic(topic, message)

        assert sent_count == 0

    @pytest.mark.asyncio
    async def test_send_to_connection_success(self, ws_manager, mock_websocket):
        """Test successful message send to connection."""
        connection_id = await ws_manager.add_connection(
            websocket=mock_websocket,
            user_id="user-123",
            tenant_id="tenant-1"
        )

        message = {"type": "test", "data": "test-data"}

        success = await ws_manager.send_to_connection(connection_id, message)

        assert success is True
        mock_websocket.send_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_to_connection_not_found(self, ws_manager):
        """Test message send to non-existent connection."""
        connection_id = str(uuid.uuid4())
        message = {"type": "test", "data": "test-data"}

        success = await ws_manager.send_to_connection(connection_id, message)

        assert success is False

    @pytest.mark.asyncio
    async def test_update_heartbeat_success(self, ws_manager, mock_websocket):
        """Test successful heartbeat update."""
        connection_id = await ws_manager.add_connection(
            websocket=mock_websocket,
            user_id="user-123",
            tenant_id="tenant-1"
        )

        old_heartbeat = ws_manager.connections[connection_id].last_heartbeat
        await asyncio.sleep(0.01)  # Small delay

        await ws_manager.update_heartbeat(connection_id)

        new_heartbeat = ws_manager.connections[connection_id].last_heartbeat
        assert new_heartbeat > old_heartbeat

    @pytest.mark.asyncio
    async def test_heartbeat_loop_timeout(self, ws_manager, mock_websocket):
        """Test heartbeat loop timeout handling."""
        # Set short timeout for testing
        ws_manager.heartbeat_timeout = 0.1

        connection_id = await ws_manager.add_connection(
            websocket=mock_websocket,
            user_id="user-123",
            tenant_id="tenant-1"
        )

        # Set old heartbeat
        ws_manager.connections[connection_id].last_heartbeat = datetime.now() - timedelta(seconds=1)

        await ws_manager.start()

        # Wait for heartbeat loop to process
        await asyncio.sleep(0.2)

        # Connection should be removed due to timeout
        assert connection_id not in ws_manager.connections

    def test_get_connection_stats(self, ws_manager):
        """Test connection statistics retrieval."""
        stats = ws_manager.get_connection_stats()

        assert "total_connections" in stats
        assert "user_connections" in stats
        assert "tenant_connections" in stats
        assert "topic_subscribers" in stats

        assert stats["total_connections"] == 0
        assert stats["user_connections"] == 0
        assert stats["tenant_connections"] == 0
        assert stats["topic_subscribers"] == 0

    @pytest.mark.asyncio
    async def test_get_connections_by_user(self, ws_manager, mock_websocket):
        """Test getting connections by user."""
        connection_id1 = await ws_manager.add_connection(
            websocket=mock_websocket,
            user_id="user-123",
            tenant_id="tenant-1"
        )

        connection_id2 = await ws_manager.add_connection(
            websocket=mock_websocket,
            user_id="user-123",
            tenant_id="tenant-1"
        )

        connections = ws_manager.get_connections_by_user("user-123")

        assert len(connections) == 2
        assert connection_id1 in connections
        assert connection_id2 in connections

    @pytest.mark.asyncio
    async def test_get_connections_by_tenant(self, ws_manager, mock_websocket):
        """Test getting connections by tenant."""
        connection_id1 = await ws_manager.add_connection(
            websocket=mock_websocket,
            user_id="user-123",
            tenant_id="tenant-1"
        )

        connection_id2 = await ws_manager.add_connection(
            websocket=mock_websocket,
            user_id="user-456",
            tenant_id="tenant-1"
        )

        connections = ws_manager.get_connections_by_tenant("tenant-1")

        assert len(connections) == 2
        assert connection_id1 in connections
        assert connection_id2 in connections

    def test_websocket_connection_creation(self, mock_websocket):
        """Test WebSocketConnection creation."""
        connection_id = str(uuid.uuid4())
        connection = WebSocketConnection(
            connection_id=connection_id,
            websocket=mock_websocket,
            user_id="user-123",
            tenant_id="tenant-1"
        )

        assert connection.connection_id == connection_id
        assert connection.websocket == mock_websocket
        assert connection.user_id == "user-123"
        assert connection.tenant_id == "tenant-1"
        assert len(connection.subscribed_topics) == 0
        assert len(connection.filters) == 0
        assert isinstance(connection.last_heartbeat, datetime)

    @pytest.mark.asyncio
    async def test_connection_cleanup_on_error(self, ws_manager, mock_websocket):
        """Test connection cleanup when WebSocket operations fail."""
        connection_id = await ws_manager.add_connection(
            websocket=mock_websocket,
            user_id="user-123",
            tenant_id="tenant-1"
        )

        # Mock WebSocket send to raise exception
        mock_websocket.send_text.side_effect = Exception("Send failed")

        message = {"type": "test", "data": "test-data"}
        success = await ws_manager.send_to_connection(connection_id, message)

        assert success is False
        # Connection should still exist
        assert connection_id in ws_manager.connections