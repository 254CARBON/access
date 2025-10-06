"""
WebSocket message handlers for Streaming Service.
"""

import json
import asyncio
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import sys
import os

# Add shared directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from shared.logging import get_logger
from shared.errors import AccessLayerException
from .connection_manager import WebSocketConnectionManager
from ..kafka.consumer import KafkaMessage


@dataclass
class WebSocketMessage:
    """WebSocket message wrapper."""
    action: str
    data: Dict[str, Any]
    connection_id: str


class WebSocketMessageHandler:
    """Handles WebSocket messages and routing."""
    
    def __init__(
        self,
        connection_manager: WebSocketConnectionManager,
        kafka_message_handler: callable
    ):
        self.connection_manager = connection_manager
        self.kafka_message_handler = kafka_message_handler
        self.logger = get_logger("streaming.ws.handler")
    
    async def handle_message(
        self,
        connection_id: str,
        message_text: str
    ) -> Optional[Dict[str, Any]]:
        """Handle incoming WebSocket message."""
        try:
            # Parse message
            message_data = json.loads(message_text)
            
            if not isinstance(message_data, dict):
                raise ValueError("Message must be a JSON object")
            
            action = message_data.get("action")
            if not action:
                raise ValueError("Message must have 'action' field")
            
            # Create message wrapper
            message = WebSocketMessage(
                action=action,
                data=message_data.get("data", {}),
                connection_id=connection_id
            )
            
            # Route to appropriate handler
            response = await self._route_message(message)
            
            return response
            
        except json.JSONDecodeError as e:
            self.logger.error("Invalid JSON message", error=str(e))
            return {
                "error": "INVALID_JSON",
                "message": "Message must be valid JSON"
            }
        
        except ValueError as e:
            self.logger.error("Invalid message format", error=str(e))
            return {
                "error": "INVALID_FORMAT",
                "message": str(e)
            }
        
        except Exception as e:
            self.logger.error("Error handling message", error=str(e))
            return {
                "error": "INTERNAL_ERROR",
                "message": "Internal server error"
            }
    
    async def _route_message(self, message: WebSocketMessage) -> Optional[Dict[str, Any]]:
        """Route message to appropriate handler."""
        handlers = {
            "subscribe": self._handle_subscribe,
            "unsubscribe": self._handle_unsubscribe,
            "ping": self._handle_ping,
            "list_topics": self._handle_list_topics,
            "get_stats": self._handle_get_stats
        }
        
        handler = handlers.get(message.action)
        if not handler:
            return {
                "error": "UNKNOWN_ACTION",
                "message": f"Unknown action: {message.action}",
                "available_actions": list(handlers.keys())
            }
        
        return await handler(message)
    
    async def _handle_subscribe(self, message: WebSocketMessage) -> Dict[str, Any]:
        """Handle subscription request."""
        connection_id = message.connection_id
        data = message.data
        
        # Validate required fields
        topics = data.get("topics")
        if not topics:
            return {
                "error": "MISSING_TOPICS",
                "message": "Topics list is required"
            }
        
        if not isinstance(topics, list):
            return {
                "error": "INVALID_TOPICS",
                "message": "Topics must be a list"
            }
        
        # Get connection
        connection = self.connection_manager.get_connection(connection_id)
        if not connection:
            return {
                "error": "CONNECTION_NOT_FOUND",
                "message": "Connection not found"
            }
        
        # Subscribe to each topic
        subscribed_topics = []
        failed_topics = []
        
        for topic in topics:
            try:
                # Validate topic format
                if not self._validate_topic(topic):
                    failed_topics.append({"topic": topic, "error": "INVALID_TOPIC_FORMAT"})
                    continue
                
                # Check entitlements (simplified for now)
                if not await self._check_topic_entitlements(connection, topic):
                    failed_topics.append({"topic": topic, "error": "ENTITLEMENT_DENIED"})
                    continue
                
                # Subscribe
                filters = data.get("filters", {}).get(topic, {})
                success = await self.connection_manager.subscribe_to_topic(
                    connection_id, topic, filters
                )
                
                if success:
                    subscribed_topics.append(topic)
                else:
                    failed_topics.append({"topic": topic, "error": "SUBSCRIPTION_FAILED"})
                
            except Exception as e:
                self.logger.error("Error subscribing to topic", topic=topic, error=str(e))
                failed_topics.append({"topic": topic, "error": "INTERNAL_ERROR"})
        
        return {
            "action": "subscribe_response",
            "subscribed_topics": subscribed_topics,
            "failed_topics": failed_topics,
            "success": len(failed_topics) == 0
        }
    
    async def _handle_unsubscribe(self, message: WebSocketMessage) -> Dict[str, Any]:
        """Handle unsubscription request."""
        connection_id = message.connection_id
        data = message.data
        
        topics = data.get("topics", [])
        if not isinstance(topics, list):
            return {
                "error": "INVALID_TOPICS",
                "message": "Topics must be a list"
            }
        
        unsubscribed_topics = []
        failed_topics = []
        
        for topic in topics:
            success = await self.connection_manager.unsubscribe_from_topic(connection_id, topic)
            if success:
                unsubscribed_topics.append(topic)
            else:
                failed_topics.append({"topic": topic, "error": "UNSUBSCRIBE_FAILED"})
        
        return {
            "action": "unsubscribe_response",
            "unsubscribed_topics": unsubscribed_topics,
            "failed_topics": failed_topics,
            "success": len(failed_topics) == 0
        }
    
    async def _handle_ping(self, message: WebSocketMessage) -> Dict[str, Any]:
        """Handle ping/heartbeat."""
        connection_id = message.connection_id
        
        # Update heartbeat
        await self.connection_manager.update_heartbeat(connection_id)
        
        return {
            "action": "pong",
            "timestamp": int(asyncio.get_event_loop().time() * 1000)
        }
    
    async def _handle_list_topics(self, message: WebSocketMessage) -> Dict[str, Any]:
        """Handle list topics request."""
        connection_id = message.connection_id
        
        connection = self.connection_manager.get_connection(connection_id)
        if not connection:
            return {
                "error": "CONNECTION_NOT_FOUND",
                "message": "Connection not found"
            }
        
        return {
            "action": "topics_list",
            "subscribed_topics": list(connection.subscribed_topics),
            "available_topics": [
                "254carbon.pricing.curve.updates.v1",
                "254carbon.pricing.instrument.updates.v1",
                "254carbon.market.data.v1"
            ]
        }
    
    async def _handle_get_stats(self, message: WebSocketMessage) -> Dict[str, Any]:
        """Handle get stats request."""
        connection_id = message.connection_id
        
        connection = self.connection_manager.get_connection(connection_id)
        if not connection:
            return {
                "error": "CONNECTION_NOT_FOUND",
                "message": "Connection not found"
            }
        
        stats = self.connection_manager.get_connection_stats()
        
        return {
            "action": "stats_response",
            "connection_stats": stats,
            "connection_info": {
                "connection_id": connection_id,
                "user_id": connection.user_id,
                "tenant_id": connection.tenant_id,
                "subscribed_topics": list(connection.subscribed_topics),
                "created_at": connection.created_at.isoformat(),
                "last_heartbeat": connection.last_heartbeat.isoformat()
            }
        }
    
    def _validate_topic(self, topic: str) -> bool:
        """Validate topic format."""
        # Basic validation - should be in format: domain.event.version
        parts = topic.split('.')
        return len(parts) >= 3 and parts[0] == "254carbon"
    
    async def _check_topic_entitlements(
        self,
        connection,
        topic: str
    ) -> bool:
        """Check if connection has entitlements for topic."""
        # Simplified entitlement check
        # In real implementation, this would call the Entitlements Service
        
        if not connection.user_id:
            return False
        
        # For now, allow all topics for authenticated users
        # TODO: Implement proper entitlement checking
        return True
    
    async def handle_kafka_message(self, kafka_message: KafkaMessage):
        """Handle incoming Kafka message and route to WebSocket connections."""
        topic = kafka_message.topic
        
        try:
            # Parse message data
            message_data = json.loads(kafka_message.value.decode('utf-8'))
            
            # Create WebSocket message
            ws_message = {
                "topic": topic,
                "data": message_data,
                "timestamp": kafka_message.timestamp or int(asyncio.get_event_loop().time() * 1000),
                "partition": kafka_message.partition,
                "offset": kafka_message.offset
            }
            
            # Broadcast to subscribers
            sent_count = await self.connection_manager.broadcast_to_topic(topic, ws_message)
            
            self.logger.debug(
                "Kafka message broadcasted",
                topic=topic,
                sent_count=sent_count
            )
            
        except Exception as e:
            self.logger.error(
                "Error handling Kafka message",
                topic=topic,
                error=str(e)
            )
