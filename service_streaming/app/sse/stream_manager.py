"""
Server-Sent Events (SSE) stream manager for Streaming Service.
"""

import asyncio
import json
from typing import Dict, Any, Optional, Set, AsyncGenerator
from dataclasses import dataclass, field
from datetime import datetime
import sys
import os

# Add shared directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from shared.logging import get_logger
from shared.errors import AccessLayerException


@dataclass
class SSEConnection:
    """SSE connection data."""
    connection_id: str
    queue: asyncio.Queue
    subscribed_topics: Set[str] = field(default_factory=set)
    filters: Dict[str, Any] = field(default_factory=dict)
    user_id: Optional[str] = None
    tenant_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)


class SSEStreamManager:
    """Manages Server-Sent Events streams."""
    
    def __init__(self, max_connections: int = 1000):
        self.max_connections = max_connections
        self.logger = get_logger("streaming.sse.manager")
        
        # Connection storage
        self.connections: Dict[str, SSEConnection] = {}
        self.topic_subscribers: Dict[str, Set[str]] = {}  # topic -> connection_ids
        
        # Message queues for each connection
        self.message_queues: Dict[str, asyncio.Queue] = {}
    
    async def create_connection(
        self,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None
    ) -> str:
        """Create a new SSE connection."""
        if len(self.connections) >= self.max_connections:
            raise AccessLayerException(
                "SSE_CONNECTION_LIMIT_EXCEEDED",
                f"Maximum SSE connections ({self.max_connections}) exceeded"
            )
        
        import uuid
        connection_id = str(uuid.uuid4())
        
        # Create message queue
        message_queue = asyncio.Queue(maxsize=1000)
        
        # Create connection
        connection = SSEConnection(
            connection_id=connection_id,
            queue=message_queue,
            user_id=user_id,
            tenant_id=tenant_id
        )
        
        # Store connection
        self.connections[connection_id] = connection
        self.message_queues[connection_id] = message_queue
        
        self.logger.info(
            "SSE connection created",
            connection_id=connection_id,
            user_id=user_id,
            tenant_id=tenant_id,
            total_connections=len(self.connections)
        )
        
        return connection_id
    
    async def remove_connection(self, connection_id: str):
        """Remove an SSE connection."""
        if connection_id not in self.connections:
            return
        
        connection = self.connections[connection_id]
        
        # Remove from topic subscriptions
        for topic in connection.subscribed_topics:
            if topic in self.topic_subscribers:
                self.topic_subscribers[topic].discard(connection_id)
                if not self.topic_subscribers[topic]:
                    del self.topic_subscribers[topic]
        
        # Remove from storage
        del self.connections[connection_id]
        if connection_id in self.message_queues:
            del self.message_queues[connection_id]
        
        self.logger.info(
            "SSE connection removed",
            connection_id=connection_id,
            total_connections=len(self.connections)
        )
    
    async def subscribe_to_topic(
        self,
        connection_id: str,
        topic: str,
        filters: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Subscribe SSE connection to a topic."""
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
            "SSE connection subscribed to topic",
            connection_id=connection_id,
            topic=topic,
            subscriber_count=len(self.topic_subscribers[topic])
        )
        
        return True
    
    async def unsubscribe_from_topic(self, connection_id: str, topic: str) -> bool:
        """Unsubscribe SSE connection from a topic."""
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
            "SSE connection unsubscribed from topic",
            connection_id=connection_id,
            topic=topic
        )
        
        return True
    
    async def send_message_to_connection(
        self,
        connection_id: str,
        message: Dict[str, Any]
    ) -> bool:
        """Send message to a specific SSE connection."""
        if connection_id not in self.message_queues:
            return False
        
        try:
            queue = self.message_queues[connection_id]
            await queue.put(message)
            
            # Update last activity
            if connection_id in self.connections:
                self.connections[connection_id].last_activity = datetime.now()
            
            return True
            
        except Exception as e:
            self.logger.error(
                "Failed to send message to SSE connection",
                connection_id=connection_id,
                error=str(e)
            )
            return False
    
    async def broadcast_to_topic(
        self,
        topic: str,
        message: Dict[str, Any],
        exclude_connections: Optional[Set[str]] = None
    ) -> int:
        """Broadcast message to all SSE subscribers of a topic."""
        if topic not in self.topic_subscribers:
            return 0
        
        subscribers = self.topic_subscribers[topic]
        if exclude_connections:
            subscribers = subscribers - exclude_connections
        
        sent_count = 0
        failed_connections = set()
        
        for connection_id in subscribers:
            if await self.send_message_to_connection(connection_id, message):
                sent_count += 1
            else:
                failed_connections.add(connection_id)
        
        # Clean up failed connections
        for connection_id in failed_connections:
            await self.remove_connection(connection_id)
        
        self.logger.debug(
            "Broadcast message to SSE topic",
            topic=topic,
            sent_count=sent_count,
            failed_count=len(failed_connections)
        )
        
        return sent_count
    
    async def get_message_stream(
        self,
        connection_id: str
    ) -> AsyncGenerator[str, None]:
        """Get message stream for SSE connection."""
        if connection_id not in self.message_queues:
            raise AccessLayerException(
                "SSE_CONNECTION_NOT_FOUND",
                "SSE connection not found"
            )
        
        queue = self.message_queues[connection_id]
        
        try:
            while True:
                # Wait for message with timeout
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=30.0)
                    
                    # Format as SSE message
                    sse_message = f"data: {json.dumps(message)}\n\n"
                    yield sse_message
                    
                    # Mark task as done
                    queue.task_done()
                    
                except asyncio.TimeoutError:
                    # Send heartbeat
                    heartbeat = {
                        "type": "heartbeat",
                        "timestamp": int(asyncio.get_event_loop().time() * 1000)
                    }
                    yield f"data: {json.dumps(heartbeat)}\n\n"
                
        except Exception as e:
            self.logger.error(
                "Error in SSE message stream",
                connection_id=connection_id,
                error=str(e)
            )
            raise
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """Get SSE connection statistics."""
        return {
            "total_connections": len(self.connections),
            "max_connections": self.max_connections,
            "topic_subscribers": len(self.topic_subscribers),
            "topics": list(self.topic_subscribers.keys())
        }
    
    def get_connection(self, connection_id: str) -> Optional[SSEConnection]:
        """Get SSE connection by ID."""
        return self.connections.get(connection_id)
    
    def get_topic_subscribers(self, topic: str) -> Set[str]:
        """Get connection IDs subscribed to a topic."""
        return self.topic_subscribers.get(topic, set()).copy()
    
    async def cleanup_stale_connections(self, max_age_seconds: int = 3600):
        """Clean up stale SSE connections."""
        current_time = datetime.now()
        stale_connections = []
        
        for connection_id, connection in self.connections.items():
            age = (current_time - connection.last_activity).total_seconds()
            if age > max_age_seconds:
                stale_connections.append(connection_id)
        
        for connection_id in stale_connections:
            self.logger.info(
                "Removing stale SSE connection",
                connection_id=connection_id,
                age_seconds=age
            )
            await self.remove_connection(connection_id)
        
        if stale_connections:
            self.logger.info(
                "Cleaned up stale SSE connections",
                count=len(stale_connections)
            )
