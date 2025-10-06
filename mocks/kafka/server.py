"""
Mock Kafka server providing in-memory message broker functionality.
"""

import asyncio
import json
import time
import uuid
from typing import Dict, Any, Optional, List, Set, Callable
from dataclasses import dataclass, field
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query
from fastapi.responses import StreamingResponse
import sys
import os

# Add shared directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from shared.logging import get_logger


@dataclass
class MockMessage:
    """Mock Kafka message."""
    topic: str
    partition: int
    offset: int
    key: Optional[str]
    value: bytes
    timestamp: Optional[int]
    headers: Dict[str, str] = field(default_factory=dict)


@dataclass
class MockTopic:
    """Mock Kafka topic."""
    name: str
    partitions: int
    messages: List[MockMessage] = field(default_factory=list)
    next_offset: int = 0


@dataclass
class MockConsumerGroup:
    """Mock Kafka consumer group."""
    group_id: str
    topics: Set[str] = field(default_factory=set)
    consumers: Set[str] = field(default_factory=set)
    offsets: Dict[str, int] = field(default_factory=dict)  # topic -> offset


class MockKafkaServer:
    """Mock Kafka server implementation."""
    
    def __init__(self, port: int = 9092):
        self.port = port
        self.logger = get_logger("mock.kafka")
        self.app = FastAPI(title="Mock Kafka", version="1.0.0")
        
        # In-memory storage
        self.topics: Dict[str, MockTopic] = {}
        self.consumer_groups: Dict[str, MockConsumerGroup] = {}
        self.subscribers: Dict[str, List[Callable]] = {}  # topic -> subscribers
        
        # WebSocket connections for streaming
        self.websocket_connections: Dict[str, WebSocket] = {}
        
        # Default topics
        self._create_default_topics()
        
        self._setup_routes()
    
    def _create_default_topics(self):
        """Create default topics."""
        default_topics = [
            "254carbon.pricing.updates.v1",
            "254carbon.instruments.updates.v1", 
            "254carbon.curves.updates.v1",
            "254carbon.metrics.request.count.v1",
            "254carbon.auth.token.refresh.v1"
        ]
        
        for topic_name in default_topics:
            self.create_topic(topic_name, partitions=3)
    
    def _setup_routes(self):
        """Set up mock Kafka routes."""
        
        @self.app.get("/")
        async def root():
            """Root endpoint."""
            return {
                "service": "mock-kafka",
                "message": "Mock Kafka server for 254Carbon Access Layer",
                "version": "1.0.0",
                "topics": list(self.topics.keys()),
                "consumer_groups": list(self.consumer_groups.keys())
            }
        
        @self.app.get("/topics")
        async def list_topics():
            """List all topics."""
            return {
                "topics": [
                    {
                        "name": topic.name,
                        "partitions": topic.partitions,
                        "message_count": len(topic.messages)
                    }
                    for topic in self.topics.values()
                ]
            }
        
        @self.app.post("/topics/{topic_name}")
        async def create_topic_endpoint(topic_name: str, partitions: int = Query(1)):
            """Create a topic."""
            if topic_name in self.topics:
                raise HTTPException(status_code=409, detail="Topic already exists")
            
            self.create_topic(topic_name, partitions)
            return {"message": f"Topic '{topic_name}' created successfully"}
        
        @self.app.get("/topics/{topic_name}")
        async def get_topic(topic_name: str):
            """Get topic information."""
            if topic_name not in self.topics:
                raise HTTPException(status_code=404, detail="Topic not found")
            
            topic = self.topics[topic_name]
            return {
                "name": topic.name,
                "partitions": topic.partitions,
                "message_count": len(topic.messages),
                "next_offset": topic.next_offset
            }
        
        @self.app.post("/topics/{topic_name}/messages")
        async def produce_message(
            topic_name: str,
            key: Optional[str] = Query(None),
            message: str = Query(...)
        ):
            """Produce a message to a topic."""
            if topic_name not in self.topics:
                raise HTTPException(status_code=404, detail="Topic not found")
            
            message_id = self.produce(topic_name, key, message.encode('utf-8'))
            return {
                "message_id": message_id,
                "topic": topic_name,
                "offset": message_id
            }
        
        @self.app.get("/topics/{topic_name}/messages")
        async def consume_messages(
            topic_name: str,
            group_id: str = Query(...),
            limit: int = Query(10),
            offset: Optional[int] = Query(None)
        ):
            """Consume messages from a topic."""
            if topic_name not in self.topics:
                raise HTTPException(status_code=404, detail="Topic not found")
            
            messages = self.consume(topic_name, group_id, limit, offset)
            return {
                "messages": [
                    {
                        "topic": msg.topic,
                        "partition": msg.partition,
                        "offset": msg.offset,
                        "key": msg.key,
                        "value": msg.value.decode('utf-8'),
                        "timestamp": msg.timestamp,
                        "headers": msg.headers
                    }
                    for msg in messages
                ]
            }
        
        @self.app.websocket("/stream/{topic_name}")
        async def stream_messages(websocket: WebSocket, topic_name: str):
            """WebSocket endpoint for streaming messages."""
            await websocket.accept()
            
            if topic_name not in self.topics:
                await websocket.close(code=1008, reason="Topic not found")
                return
            
            connection_id = str(uuid.uuid4())
            self.websocket_connections[connection_id] = websocket
            
            try:
                # Subscribe to topic
                self.subscribe(topic_name, lambda msg: self._send_to_websocket(connection_id, msg))
                
                # Keep connection alive
                while True:
                    try:
                        data = await websocket.receive_text()
                        # Echo back for heartbeat
                        await websocket.send_text(f"heartbeat: {data}")
                    except WebSocketDisconnect:
                        break
                        
            except Exception as e:
                self.logger.error("WebSocket error", error=str(e))
            finally:
                # Cleanup
                if connection_id in self.websocket_connections:
                    del self.websocket_connections[connection_id]
                self.unsubscribe(topic_name, connection_id)
        
        @self.app.get("/consumer-groups")
        async def list_consumer_groups():
            """List consumer groups."""
            return {
                "consumer_groups": [
                    {
                        "group_id": group.group_id,
                        "topics": list(group.topics),
                        "consumers": list(group.consumers),
                        "offsets": group.offsets
                    }
                    for group in self.consumer_groups.values()
                ]
            }
        
        @self.app.post("/consumer-groups/{group_id}/subscribe")
        async def subscribe_group(
            group_id: str,
            topics: List[str]
        ):
            """Subscribe consumer group to topics."""
            if group_id not in self.consumer_groups:
                self.consumer_groups[group_id] = MockConsumerGroup(group_id)
            
            group = self.consumer_groups[group_id]
            group.topics.update(topics)
            
            # Initialize offsets for new topics
            for topic in topics:
                if topic not in group.offsets:
                    group.offsets[topic] = 0
            
            return {"message": f"Consumer group '{group_id}' subscribed to topics"}
    
    def create_topic(self, name: str, partitions: int = 1):
        """Create a new topic."""
        self.topics[name] = MockTopic(name=name, partitions=partitions)
        self.subscribers[name] = []
        self.logger.info(f"Created topic '{name}' with {partitions} partitions")
    
    def produce(self, topic: str, key: Optional[str], value: bytes, headers: Optional[Dict[str, str]] = None) -> int:
        """Produce a message to a topic."""
        if topic not in self.topics:
            raise ValueError(f"Topic '{topic}' not found")
        
        topic_obj = self.topics[topic]
        message = MockMessage(
            topic=topic,
            partition=0,  # Simple partition assignment
            offset=topic_obj.next_offset,
            key=key,
            value=value,
            timestamp=int(time.time() * 1000),
            headers=headers or {}
        )
        
        topic_obj.messages.append(message)
        topic_obj.next_offset += 1
        
        # Notify subscribers
        for callback in self.subscribers.get(topic, []):
            try:
                callback(message)
            except Exception as e:
                self.logger.error(f"Error in subscriber callback: {e}")
        
        self.logger.debug(f"Produced message to topic '{topic}', offset {message.offset}")
        return message.offset
    
    def consume(self, topic: str, group_id: str, limit: int = 10, offset: Optional[int] = None) -> List[MockMessage]:
        """Consume messages from a topic."""
        if topic not in self.topics:
            raise ValueError(f"Topic '{topic}' not found")
        
        # Get or create consumer group
        if group_id not in self.consumer_groups:
            self.consumer_groups[group_id] = MockConsumerGroup(group_id)
        
        group = self.consumer_groups[group_id]
        topic_obj = self.topics[topic]
        
        # Get current offset
        current_offset = group.offsets.get(topic, 0)
        if offset is not None:
            current_offset = offset
        
        # Get messages
        messages = []
        for msg in topic_obj.messages[current_offset:current_offset + limit]:
            messages.append(msg)
        
        # Update offset
        if messages:
            group.offsets[topic] = current_offset + len(messages)
        
        return messages
    
    def subscribe(self, topic: str, callback: Callable[[MockMessage], None]):
        """Subscribe to a topic."""
        if topic not in self.subscribers:
            self.subscribers[topic] = []
        
        self.subscribers[topic].append(callback)
        self.logger.debug(f"Subscribed to topic '{topic}'")
    
    def unsubscribe(self, topic: str, callback_id: str):
        """Unsubscribe from a topic."""
        if topic in self.subscribers:
            # Remove callback by ID (simplified)
            self.subscribers[topic] = [
                cb for cb in self.subscribers[topic] 
                if str(id(cb)) != callback_id
            ]
            self.logger.debug(f"Unsubscribed from topic '{topic}'")
    
    async def _send_to_websocket(self, connection_id: str, message: MockMessage):
        """Send message to WebSocket connection."""
        if connection_id in self.websocket_connections:
            websocket = self.websocket_connections[connection_id]
            try:
                message_data = {
                    "topic": message.topic,
                    "partition": message.partition,
                    "offset": message.offset,
                    "key": message.key,
                    "value": message.value.decode('utf-8'),
                    "timestamp": message.timestamp,
                    "headers": message.headers
                }
                await websocket.send_text(json.dumps(message_data))
            except Exception as e:
                self.logger.error(f"Error sending to WebSocket: {e}")


def create_app():
    """Create mock Kafka application."""
    server = MockKafkaServer()
    return server.app


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(create_app(), host="0.0.0.0", port=9092)
