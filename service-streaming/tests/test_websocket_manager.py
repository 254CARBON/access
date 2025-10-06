"""
Unit tests for WebSocketConnectionManager.
"""

import pytest
import uuid
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timedelta

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..'))

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
        """Create mock WebSocket."""
        websocket = AsyncMock()
        websocket.close = AsyncMock()
        websocket.send_text = AsyncMock()
        return websocket
    
    @pytest.fixture
    def mock_connection(self, mock_websocket):
        """Create mock WebSocketConnection."""
        return WebSocketConnection(
            connection_id="test-connection-1",
            websocket=mock_websocket,
            user_id="user1",
            tenant_id="tenant-1"
        )
    
    @pytest.mark.asyncio
    async def test_start(self, ws_manager):
        """Test starting the connection manager."""
        # Test
        await ws_manager.start()
        
        # Assertions
        assert ws_manager.running is True
        assert ws_manager._heartbeat_task is not None
    
    @pytest.mark.asyncio
    async def test_stop(self, ws_manager, mock_websocket):
        """Test stopping the connection manager."""
        # Add a connection
        await ws_manager.add_connection(mock_websocket, "user1", "tenant-1")
        
        # Test
        await ws_manager.stop()
        
        # Assertions
        assert ws_manager.running is False
        # WebSocket should be closed
        mock_websocket.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_add_connection_success(self, ws_manager, mock_websocket):
        """Test successful connection addition."""
        # Test
        connection_id = await ws_manager.add_connection(
            mock_websocket, "user1", "tenant-1", {"client_type": "web"}
        )
        
        # Assertions
        assert connection_id is not None
        assert connection_id in ws_manager.connections
        assert "user1" in ws_manager.user_connections
        assert "tenant-1" in ws_manager.tenant_connections
        assert connection_id in ws_manager.user_connections["user1"]
        assert connection_id in ws_manager.tenant_connections["tenant-1"]
    
    @pytest.mark.asyncio
    async def test_add_connection_limit_exceeded(self, ws_manager, mock_websocket):
        """Test connection addition with limit exceeded."""
        # Set up manager with limit of 1
        ws_manager.max_connections = 1
        await ws_manager.add_connection(mock_websocket, "user1", "tenant-1")
        
        # Test and assert exception
        with pytest.raises(AccessLayerException):
            await ws_manager.add_connection(mock_websocket, "user2", "tenant-2")
    
    @pytest.mark.asyncio
    async def test_remove_connection(self, ws_manager, mock_websocket):
        """Test connection removal."""
        # Add connection
        connection_id = await ws_manager.add_connection(mock_websocket, "user1", "tenant-1")
        
        # Test
        await ws_manager.remove_connection(connection_id)
        
        # Assertions
        assert connection_id not in ws_manager.connections
        assert connection_id not in ws_manager.user_connections["user1"]
        assert connection_id not in ws_manager.tenant_connections["tenant-1"]
        mock_websocket.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_remove_connection_not_found(self, ws_manager):
        """Test removal of non-existent connection."""
        # Test (should not raise exception)
        await ws_manager.remove_connection("nonexistent-connection")
        
        # Assertions - no exceptions should be raised
    
    @pytest.mark.asyncio
    async def test_subscribe_to_topic(self, ws_manager, mock_websocket):
        """Test topic subscription."""
        # Add connection
        connection_id = await ws_manager.add_connection(mock_websocket, "user1", "tenant-1")
        
        # Test
        result = await ws_manager.subscribe_to_topic(
            connection_id, "254carbon.pricing.updates.v1", {"instrument": "BRN"}
        )
        
        # Assertions
        assert result is True
        assert "254carbon.pricing.updates.v1" in ws_manager.connections[connection_id].subscribed_topics
        assert connection_id in ws_manager.topic_subscribers["254carbon.pricing.updates.v1"]
    
    @pytest.mark.asyncio
    async def test_subscribe_to_topic_connection_not_found(self, ws_manager):
        """Test topic subscription for non-existent connection."""
        # Test
        result = await ws_manager.subscribe_to_topic(
            "nonexistent-connection", "254carbon.pricing.updates.v1"
        )
        
        # Assertions
        assert result is False
    
    @pytest.mark.asyncio
    async def test_unsubscribe_from_topic(self, ws_manager, mock_websocket):
        """Test topic unsubscription."""
        # Add connection and subscribe
        connection_id = await ws_manager.add_connection(mock_websocket, "user1", "tenant-1")
        await ws_manager.subscribe_to_topic(connection_id, "254carbon.pricing.updates.v1")
        
        # Test
        result = await ws_manager.unsubscribe_from_topic(connection_id, "254carbon.pricing.updates.v1")
        
        # Assertions
        assert result is True
        assert "254carbon.pricing.updates.v1" not in ws_manager.connections[connection_id].subscribed_topics
        assert connection_id not in ws_manager.topic_subscribers["254carbon.pricing.updates.v1"]
    
    @pytest.mark.asyncio
    async def test_send_message_success(self, ws_manager, mock_websocket):
        """Test successful message sending."""
        # Add connection
        connection_id = await ws_manager.add_connection(mock_websocket, "user1", "tenant-1")
        
        # Test
        message = {"type": "pricing_update", "data": {"price": 52.50}}
        result = await ws_manager.send_message(connection_id, message)
        
        # Assertions
        assert result is True
        mock_websocket.send_text.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_send_message_connection_not_found(self, ws_manager):
        """Test message sending to non-existent connection."""
        # Test
        message = {"type": "pricing_update", "data": {"price": 52.50}}
        result = await ws_manager.send_message("nonexistent-connection", message)
        
        # Assertions
        assert result is False
    
    @pytest.mark.asyncio
    async def test_send_message_websocket_error(self, ws_manager, mock_websocket):
        """Test message sending with WebSocket error."""
        # Add connection
        connection_id = await ws_manager.add_connection(mock_websocket, "user1", "tenant-1")
        
        # Mock WebSocket to raise exception
        mock_websocket.send_text.side_effect = Exception("WebSocket error")
        
        # Test
        message = {"type": "pricing_update", "data": {"price": 52.50}}
        result = await ws_manager.send_message(connection_id, message)
        
        # Assertions
        assert result is False
        # Connection should be removed due to error
        assert connection_id not in ws_manager.connections
    
    @pytest.mark.asyncio
    async def test_broadcast_to_topic(self, ws_manager, mock_websocket):
        """Test topic broadcasting."""
        # Add connections
        connection_id1 = await ws_manager.add_connection(mock_websocket, "user1", "tenant-1")
        connection_id2 = await ws_manager.add_connection(mock_websocket, "user2", "tenant-2")
        
        # Subscribe both to topic
        await ws_manager.subscribe_to_topic(connection_id1, "254carbon.pricing.updates.v1")
        await ws_manager.subscribe_to_topic(connection_id2, "254carbon.pricing.updates.v1")
        
        # Test
        message = {"type": "pricing_update", "data": {"price": 52.50}}
        sent_count = await ws_manager.broadcast_to_topic("254carbon.pricing.updates.v1", message)
        
        # Assertions
        assert sent_count == 2
        assert mock_websocket.send_text.call_count == 2
    
    @pytest.mark.asyncio
    async def test_broadcast_to_topic_with_exclude(self, ws_manager, mock_websocket):
        """Test topic broadcasting with excluded connections."""
        # Add connections
        connection_id1 = await ws_manager.add_connection(mock_websocket, "user1", "tenant-1")
        connection_id2 = await ws_manager.add_connection(mock_websocket, "user2", "tenant-2")
        
        # Subscribe both to topic
        await ws_manager.subscribe_to_topic(connection_id1, "254carbon.pricing.updates.v1")
        await ws_manager.subscribe_to_topic(connection_id2, "254carbon.pricing.updates.v1")
        
        # Test with exclusion
        message = {"type": "pricing_update", "data": {"price": 52.50}}
        sent_count = await ws_manager.broadcast_to_topic(
            "254carbon.pricing.updates.v1", message, exclude_connections={connection_id1}
        )
        
        # Assertions
        assert sent_count == 1
        assert mock_websocket.send_text.call_count == 1
    
    @pytest.mark.asyncio
    async def test_broadcast_to_topic_no_subscribers(self, ws_manager):
        """Test topic broadcasting with no subscribers."""
        # Test
        message = {"type": "pricing_update", "data": {"price": 52.50}}
        sent_count = await ws_manager.broadcast_to_topic("nonexistent-topic", message)
        
        # Assertions
        assert sent_count == 0
    
    @pytest.mark.asyncio
    async def test_update_heartbeat(self, ws_manager, mock_websocket):
        """Test heartbeat update."""
        # Add connection
        connection_id = await ws_manager.add_connection(mock_websocket, "user1", "tenant-1")
        
        # Test
        await ws_manager.update_heartbeat(connection_id)
        
        # Assertions
        connection = ws_manager.connections[connection_id]
        assert connection.last_heartbeat is not None
    
    @pytest.mark.asyncio
    async def test_get_connection_stats(self, ws_manager, mock_websocket):
        """Test connection statistics retrieval."""
        # Add connections
        await ws_manager.add_connection(mock_websocket, "user1", "tenant-1")
        await ws_manager.add_connection(mock_websocket, "user2", "tenant-2")
        
        # Test
        stats = ws_manager.get_connection_stats()
        
        # Assertions
        assert stats["total_connections"] == 2
        assert stats["max_connections"] == 100
        assert stats["user_connections"] == 2
        assert stats["tenant_connections"] == 2
        assert stats["topic_subscribers"] == 0
    
    def test_get_connection(self, ws_manager, mock_websocket):
        """Test connection retrieval by ID."""
        # Add connection
        connection_id = ws_manager.add_connection(mock_websocket, "user1", "tenant-1")
        
        # Test
        connection = ws_manager.get_connection(connection_id)
        
        # Assertions
        assert connection is not None
        assert connection.connection_id == connection_id
        assert connection.user_id == "user1"
        assert connection.tenant_id == "tenant-1"
    
    def test_get_connection_not_found(self, ws_manager):
        """Test connection retrieval for non-existent connection."""
        # Test
        connection = ws_manager.get_connection("nonexistent-connection")
        
        # Assertions
        assert connection is None
    
    def test_get_connections_by_user(self, ws_manager, mock_websocket):
        """Test connection retrieval by user."""
        # Add connections
        connection_id1 = ws_manager.add_connection(mock_websocket, "user1", "tenant-1")
        connection_id2 = ws_manager.add_connection(mock_websocket, "user1", "tenant-1")
        
        # Test
        connections = ws_manager.get_connections_by_user("user1")
        
        # Assertions
        assert len(connections) == 2
        assert connection_id1 in connections
        assert connection_id2 in connections
    
    def test_get_connections_by_tenant(self, ws_manager, mock_websocket):
        """Test connection retrieval by tenant."""
        # Add connections
        connection_id1 = ws_manager.add_connection(mock_websocket, "user1", "tenant-1")
        connection_id2 = ws_manager.add_connection(mock_websocket, "user2", "tenant-1")
        
        # Test
        connections = ws_manager.get_connections_by_tenant("tenant-1")
        
        # Assertions
        assert len(connections) == 2
        assert connection_id1 in connections
        assert connection_id2 in connections
    
    def test_get_topic_subscribers(self, ws_manager, mock_websocket):
        """Test topic subscribers retrieval."""
        # Add connections and subscribe
        connection_id1 = ws_manager.add_connection(mock_websocket, "user1", "tenant-1")
        connection_id2 = ws_manager.add_connection(mock_websocket, "user2", "tenant-2")
        ws_manager.subscribe_to_topic(connection_id1, "254carbon.pricing.updates.v1")
        ws_manager.subscribe_to_topic(connection_id2, "254carbon.pricing.updates.v1")
        
        # Test
        subscribers = ws_manager.get_topic_subscribers("254carbon.pricing.updates.v1")
        
        # Assertions
        assert len(subscribers) == 2
        assert connection_id1 in subscribers
        assert connection_id2 in subscribers
