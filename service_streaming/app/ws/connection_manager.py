"""
WebSocket connection manager for Streaming Service.
"""

import asyncio
import json
import uuid
from typing import Dict, Any, Optional, Set, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import sys
import os

# Add shared directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from shared.logging import get_logger
from shared.errors import AccessLayerException


@dataclass
class WebSocketConnection:
    """WebSocket connection data."""
    connection_id: str
    websocket: Any  # WebSocket object
    user_id: Optional[str] = None
    tenant_id: Optional[str] = None
    subscribed_topics: Set[str] = field(default_factory=set)
    filters: Dict[str, Any] = field(default_factory=dict)
    last_heartbeat: datetime = field(default_factory=datetime.now)
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


class WebSocketConnectionManager:
    """Manages WebSocket connections for streaming service."""
    
    def __init__(self, max_connections: int = 5000, heartbeat_timeout: int = 30):
        self.max_connections = max_connections
        self.heartbeat_timeout = heartbeat_timeout
        self.logger = get_logger("streaming.ws.connection_manager")
        
        # Connection storage
        self.connections: Dict[str, WebSocketConnection] = {}
        self.user_connections: Dict[str, Set[str]] = {}  # user_id -> connection_ids
        self.tenant_connections: Dict[str, Set[str]] = {}  # tenant_id -> connection_ids
        self.topic_subscribers: Dict[str, Set[str]] = {}  # topic -> connection_ids
        
        # Heartbeat task
        self._heartbeat_task: Optional[asyncio.Task] = None
        self.running = False
    
    async def start(self):
        """Start the connection manager."""
        self.running = True
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        self.logger.info("WebSocket connection manager started")
    
    async def stop(self):
        """Stop the connection manager."""
        self.running = False
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
        
        # Close all connections
        for connection in self.connections.values():
            try:
                await connection.websocket.close()
            except Exception:
                pass
        
        self.logger.info("WebSocket connection manager stopped")
    
    async def add_connection(
        self,
        websocket: Any,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Add a new WebSocket connection."""
        if len(self.connections) >= self.max_connections:
            raise AccessLayerException(
                "CONNECTION_LIMIT_EXCEEDED",
                f"Maximum connections ({self.max_connections}) exceeded"
            )
        
        connection_id = str(uuid.uuid4())
        connection = WebSocketConnection(
            connection_id=connection_id,
            websocket=websocket,
            user_id=user_id,
            tenant_id=tenant_id,
            metadata=metadata or {}
        )
        
        # Store connection
        self.connections[connection_id] = connection
        
        # Update indices
        if user_id:
            if user_id not in self.user_connections:
                self.user_connections[user_id] = set()
            self.user_connections[user_id].add(connection_id)
        
        if tenant_id:
            if tenant_id not in self.tenant_connections:
                self.tenant_connections[tenant_id] = set()
            self.tenant_connections[tenant_id].add(connection_id)
        
        self.logger.info(
            "WebSocket connection added",
            connection_id=connection_id,
            user_id=user_id,
            tenant_id=tenant_id,
            total_connections=len(self.connections)
        )
        
        return connection_id
    
    async def remove_connection(self, connection_id: str):
        """Remove a WebSocket connection."""
        if connection_id not in self.connections:
            return
        
        connection = self.connections[connection_id]
        
        # Remove from indices
        if connection.user_id and connection.user_id in self.user_connections:
            self.user_connections[connection.user_id].discard(connection_id)
            if not self.user_connections[connection.user_id]:
                del self.user_connections[connection.user_id]
        
        if connection.tenant_id and connection.tenant_id in self.tenant_connections:
            self.tenant_connections[connection.tenant_id].discard(connection_id)
            if not self.tenant_connections[connection.tenant_id]:
                del self.tenant_connections[connection.tenant_id]
        
        # Remove from topic subscriptions
        for topic in connection.subscribed_topics:
            if topic in self.topic_subscribers:
                self.topic_subscribers[topic].discard(connection_id)
                if not self.topic_subscribers[topic]:
                    del self.topic_subscribers[topic]
        
        # Close WebSocket
        try:
            await connection.websocket.close()
        except Exception:
            pass
        
        # Remove from connections
        del self.connections[connection_id]
        
        self.logger.info(
            "WebSocket connection removed",
            connection_id=connection_id,
            total_connections=len(self.connections)
        )
    
    async def subscribe_to_topic(
        self,
        connection_id: str,
        topic: str,
        filters: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Subscribe connection to a topic."""
        if connection_id not in self.connections:
            return False
        
        connection = self.connections[connection_id]
        
        # Add to connection's subscriptions
        connection.subscribed_topics.add(topic)
        if filters:
            connection.filters[topic] = filters
        
        # Add to topic subscribers
        if topic not in self.topic_subscribers:
            self.topic_subscribers[topic] = set()
        self.topic_subscribers[topic].add(connection_id)
        
        self.logger.info(
            "Connection subscribed to topic",
            connection_id=connection_id,
            topic=topic,
            subscriber_count=len(self.topic_subscribers[topic])
        )
        
        return True
    
    async def unsubscribe_from_topic(self, connection_id: str, topic: str) -> bool:
        """Unsubscribe connection from a topic."""
        if connection_id not in self.connections:
            return False
        
        connection = self.connections[connection_id]
        
        # Remove from connection's subscriptions
        connection.subscribed_topics.discard(topic)
        if topic in connection.filters:
            del connection.filters[topic]
        
        # Remove from topic subscribers
        if topic in self.topic_subscribers:
            self.topic_subscribers[topic].discard(connection_id)
            if not self.topic_subscribers[topic]:
                del self.topic_subscribers[topic]
        
        self.logger.info(
            "Connection unsubscribed from topic",
            connection_id=connection_id,
            topic=topic
        )
        
        return True
    
    async def send_message(
        self,
        connection_id: str,
        message: Dict[str, Any]
    ) -> bool:
        """Send message to a specific connection."""
        if connection_id not in self.connections:
            return False
        
        connection = self.connections[connection_id]
        
        try:
            await connection.websocket.send_text(json.dumps(message))
            return True
        except Exception as e:
            self.logger.error(
                "Failed to send message to connection",
                connection_id=connection_id,
                error=str(e)
            )
            # Remove failed connection
            await self.remove_connection(connection_id)
            return False
    
    async def broadcast_to_topic(
        self,
        topic: str,
        message: Dict[str, Any],
        exclude_connections: Optional[Set[str]] = None
    ) -> int:
        """Broadcast message to all subscribers of a topic."""
        if topic not in self.topic_subscribers:
            return 0
        
        subscribers = self.topic_subscribers[topic]
        if exclude_connections:
            subscribers = subscribers - exclude_connections
        
        sent_count = 0
        failed_connections = set()
        
        for connection_id in subscribers:
            if await self.send_message(connection_id, message):
                sent_count += 1
            else:
                failed_connections.add(connection_id)
        
        # Clean up failed connections
        for connection_id in failed_connections:
            await self.remove_connection(connection_id)
        
        self.logger.debug(
            "Broadcast message to topic",
            topic=topic,
            sent_count=sent_count,
            failed_count=len(failed_connections)
        )
        
        return sent_count
    
    async def update_heartbeat(self, connection_id: str):
        """Update connection heartbeat."""
        if connection_id in self.connections:
            self.connections[connection_id].last_heartbeat = datetime.now()
    
    async def _heartbeat_loop(self):
        """Heartbeat monitoring loop."""
        while self.running:
            try:
                current_time = datetime.now()
                timeout_threshold = current_time - timedelta(seconds=self.heartbeat_timeout)
                
                # Find stale connections
                stale_connections = []
                for connection_id, connection in self.connections.items():
                    if connection.last_heartbeat < timeout_threshold:
                        stale_connections.append(connection_id)
                
                # Remove stale connections
                for connection_id in stale_connections:
                    self.logger.info(
                        "Removing stale connection",
                        connection_id=connection_id,
                        last_heartbeat=connection.last_heartbeat.isoformat()
                    )
                    await self.remove_connection(connection_id)
                
                await asyncio.sleep(10)  # Check every 10 seconds
                
            except Exception as e:
                self.logger.error("Error in heartbeat loop", error=str(e))
                await asyncio.sleep(5)
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """Get connection statistics."""
        return {
            "total_connections": len(self.connections),
            "max_connections": self.max_connections,
            "user_connections": len(self.user_connections),
            "tenant_connections": len(self.tenant_connections),
            "topic_subscribers": len(self.topic_subscribers),
            "topics": list(self.topic_subscribers.keys())
        }
    
    def get_connection(self, connection_id: str) -> Optional[WebSocketConnection]:
        """Get connection by ID."""
        return self.connections.get(connection_id)
    
    def get_connections_by_user(self, user_id: str) -> Set[str]:
        """Get connection IDs for a user."""
        return self.user_connections.get(user_id, set()).copy()
    
    def get_connections_by_tenant(self, tenant_id: str) -> Set[str]:
        """Get connection IDs for a tenant."""
        return self.tenant_connections.get(tenant_id, set()).copy()
    
    def get_topic_subscribers(self, topic: str) -> Set[str]:
        """Get connection IDs subscribed to a topic."""
        return self.topic_subscribers.get(topic, set()).copy()
