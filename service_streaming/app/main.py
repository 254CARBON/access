"""
Streaming service for 254Carbon Access Layer.
"""

import asyncio
import json
import sys
import os
import time
from typing import Optional, Dict, Any

# Add shared directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from fastapi import WebSocket, WebSocketDisconnect, HTTPException, Depends, Query
from fastapi.responses import StreamingResponse
from shared.base_service import BaseService
from shared.logging import get_logger
from shared.errors import AccessLayerException, AuthorizationError
from shared.observability import get_observability_manager, observe_function, observe_operation

from .kafka.consumer import KafkaConsumerManager
from .kafka.producer import KafkaProducerManager
from .ws.connection_manager import WebSocketConnectionManager
from .ws.handlers import WebSocketMessageHandler
from .sse.stream_manager import SSEStreamManager
from .subscriptions.manager import SubscriptionManager
from .auth.client import AuthClient
from .entitlements.client import EntitlementsClient


class StreamingService(BaseService):
    """Streaming service implementation."""
    
    def __init__(self):
        super().__init__("streaming", 8001)
        
        # Initialize observability
        self.observability = get_observability_manager(
            "streaming",
            log_level=self.config.log_level,
            otel_exporter=self.config.otel_exporter,
            enable_console=self.config.enable_console_tracing
        )
        
        # Initialize components
        self.kafka_consumer = KafkaConsumerManager(
            bootstrap_servers=self.config.kafka_bootstrap,
            group_id=f"streaming-{self.config.env}"
        )
        self.kafka_producer = KafkaProducerManager(
            bootstrap_servers=self.config.kafka_bootstrap
        )
        self.ws_manager = WebSocketConnectionManager(
            max_connections=self.config.max_ws_connections,
            heartbeat_timeout=self.config.heartbeat_timeout
        )
        self.sse_manager = SSEStreamManager(
            max_connections=self.config.max_sse_connections
        )
        self.subscription_manager = SubscriptionManager()
        self.auth_client = AuthClient(self.config.auth_service_url)
        self.entitlements_client = EntitlementsClient(self.config.entitlements_service_url)

        self.supported_topics: Dict[str, Dict[str, Any]] = {
            "served.market.latest_prices.v1": {
                "resource": "market_data",
                "action": "read",
                "description": "Served latest price updates"
            },
            "pricing.curve.updates.v1": {
                "resource": "curve",
                "action": "read",
                "description": "Curve pricing updates"
            },
            "market.data.updates.v1": {
                "resource": "market_data",
                "action": "read",
                "description": "Real-time market data updates"
            }
        }
        self.default_stream_topics = list(self.supported_topics.keys())
        self._topic_subscription_lock = asyncio.Lock()
        
        # Initialize message handler
        self.ws_handler = WebSocketMessageHandler(
            connection_manager=self.ws_manager,
            kafka_message_handler=self._handle_kafka_message,
            subscription_manager=self.subscription_manager,
            entitlement_checker=self._check_topic_entitlements,
            ensure_topic_subscription=self._ensure_kafka_subscription,
            topic_registry=self.supported_topics
        )
        
        self._setup_streaming_routes()
        self.app.state.streaming_service = self
    
    def _setup_streaming_routes(self):
        """Set up streaming-specific routes."""
        
        @self.app.get("/")
        async def root():
            """Root endpoint."""
            return {
                "service": "streaming",
                "message": "254Carbon Access Layer - Streaming Service",
                "version": "1.0.0",
                "capabilities": ["websocket", "sse", "kafka"],
                "topics": self.supported_topics
            }
        
        @self.app.get("/ws/stream")
        async def websocket_info():
            """Informational endpoint for WebSocket route."""
            return {
                "message": "WebSocket endpoint available at /ws/stream (WebSocket handshake required)."
            }
        
        @self.app.websocket("/ws/stream")
        @observe_function("streaming_websocket_connection")
        async def websocket_endpoint(websocket: WebSocket, token: Optional[str] = Query(None)):
            """WebSocket streaming endpoint."""
            await websocket.accept()
            
            try:
                # Authenticate user
                user_info = await self._authenticate_websocket(token)
                
                # Set user context for logging
                self.observability.trace_request(
                    user_id=user_info.get("user_id"),
                    tenant_id=user_info.get("tenant_id")
                )
                
                # Add connection
                connection_id = await self.ws_manager.add_connection(
                    websocket=websocket,
                    user_id=user_info.get("user_id"),
                    tenant_id=user_info.get("tenant_id")
                )
                
                # Log WebSocket connection
                self.observability.log_business_event(
                    "websocket_connected",
                    connection_id=connection_id,
                    user_id=user_info.get("user_id"),
                    tenant_id=user_info.get("tenant_id")
                )
                
                # Send connection established message
                await websocket.send_text(json.dumps({
                    "type": "connection_established",
                    "connection_id": connection_id,
                    "user_id": user_info.get("user_id"),
                    "tenant_id": user_info.get("tenant_id")
                }))
                
                # Send connection event to Kafka
                await self.kafka_producer.send_connection_event(
                    event_type="connected",
                    connection_id=connection_id,
                    user_id=user_info.get("user_id"),
                    tenant_id=user_info.get("tenant_id")
                )
                
                # Handle messages
                while True:
                    try:
                        message_text = await websocket.receive_text()
                        response = await self.ws_handler.handle_message(connection_id, message_text)
                        
                        if response:
                            await websocket.send_text(json.dumps(response))
                    
                    except WebSocketDisconnect:
                        break
                    except Exception as e:
                        self.logger.error("WebSocket error", error=str(e))
                        await websocket.send_text(json.dumps({
                            "error": "INTERNAL_ERROR",
                            "message": "Internal server error"
                        }))
                
            except AccessLayerException as e:
                await websocket.send_text(json.dumps({
                    "error": e.code,
                    "message": e.message
                }))
                await websocket.close()
            except Exception as e:
                self.logger.error("WebSocket connection error", error=str(e))
                await websocket.close()
            finally:
                # Clean up connection
                if 'connection_id' in locals():
                    await self.ws_manager.remove_connection(connection_id)
                    await self.subscription_manager.remove_connection_subscriptions(connection_id)
                    
                    # Log WebSocket disconnection
                    if 'user_info' in locals():
                        self.observability.log_business_event(
                            "websocket_disconnected",
                            connection_id=connection_id,
                            user_id=user_info.get("user_id"),
                            tenant_id=user_info.get("tenant_id")
                        )
                    
                    # Send disconnect event
                    await self.kafka_producer.send_connection_event(
                        event_type="disconnected",
                        connection_id=connection_id,
                        user_id=user_info.get("user_id") if 'user_info' in locals() else None,
                        tenant_id=user_info.get("tenant_id") if 'user_info' in locals() else None
                    )
        
        @self.app.get("/sse/stream")
        async def sse_endpoint(token: Optional[str] = Query(None)):
            """Server-Sent Events streaming endpoint."""
            if token is None:
                return {
                    "message": "SSE endpoint available at /sse/stream (token required for live data)."
                }
            try:
                # Authenticate user
                user_info = await self._authenticate_sse(token)
                
                # Create SSE connection
                connection_id = await self.sse_manager.create_connection(
                    user_id=user_info.get("user_id"),
                    tenant_id=user_info.get("tenant_id")
                )
                
                # Return SSE stream
                return StreamingResponse(
                    self._sse_stream_generator(connection_id),
                    media_type="text/event-stream",
                    headers={
                        "Cache-Control": "no-cache",
                        "Connection": "keep-alive",
                        "Access-Control-Allow-Origin": "*",
                        "Access-Control-Allow-Headers": "Cache-Control"
                    }
                )
                
            except AccessLayerException as e:
                raise HTTPException(status_code=401, detail={
                    "error": e.code,
                    "message": e.message
                })
            except Exception as e:
                self.logger.error("SSE connection error", error=str(e))
                raise HTTPException(status_code=500, detail="Internal server error")
        
        @self.app.post("/sse/subscribe")
        async def sse_subscribe(
            connection_id: str = Query(...),
            topic: str = Query(...),
            filters: Optional[str] = Query(None)
        ):
            """Subscribe SSE connection to topic."""
            try:
                # Parse filters
                filter_data = json.loads(filters) if filters else {}

                if topic not in self.supported_topics:
                    raise HTTPException(status_code=400, detail="Unsupported topic")

                connection = self.sse_manager.connections.get(connection_id)
                if not connection:
                    raise HTTPException(status_code=404, detail="Connection not found")

                # Check entitlements
                if not await self._check_topic_entitlements(connection, topic):
                    raise HTTPException(status_code=403, detail="Entitlement denied")

                await self._ensure_kafka_subscription(topic)
                
                # Subscribe to topic
                success = await self.sse_manager.subscribe_to_topic(
                    connection_id, topic, filter_data
                )
                
                if success:
                    await self.subscription_manager.create_subscription(
                        connection_id=connection_id,
                        topic=topic,
                        filters=filter_data,
                        user_id=connection.user_id,
                        tenant_id=connection.tenant_id
                    )
                    return {"success": True, "topic": topic}
                else:
                    raise HTTPException(status_code=400, detail="Subscription failed")
                    
            except Exception as e:
                self.logger.error("SSE subscription error", error=str(e))
                raise HTTPException(status_code=500, detail="Internal server error")
        
        @self.app.get("/stats")
        async def get_stats():
            """Get streaming service statistics."""
            return {
                "websocket": self.ws_manager.get_connection_stats(),
                "sse": self.sse_manager.get_connection_stats(),
                "subscriptions": self.subscription_manager.get_subscription_stats(),
                "kafka": {
                    "consumer_running": self.kafka_consumer.is_running(),
                    "subscribed_topics": self.kafka_consumer.get_subscribed_topics()
                },
                "supported_topics": self.supported_topics
            }
    
    async def _check_topic_entitlements(self, connection, topic: str) -> bool:
        """Verify that a connection has entitlements for a topic."""
        topic_info = self.supported_topics.get(topic)
        if not topic_info:
            return False

        user_id = getattr(connection, "user_id", None)
        tenant_id = getattr(connection, "tenant_id", None)
        connection_id = getattr(connection, "connection_id", "unknown")

        if not user_id or not tenant_id:
            return False

        try:
            await self.entitlements_client.check_access(
                user_id=user_id,
                tenant_id=tenant_id,
                resource=topic_info["resource"],
                action=topic_info.get("action", "read"),
                context={
                    "topic": topic,
                    "connection_id": connection_id
                }
            )
            return True
        except AuthorizationError as exc:
            self.logger.warning(
                "Entitlement denied",
                topic=topic,
                connection_id=connection_id,
                user_id=user_id,
                tenant_id=tenant_id,
                error=str(exc)
            )
            return False
        except Exception as exc:
            self.logger.error(
                "Entitlement check error",
                topic=topic,
                connection_id=connection_id,
                error=str(exc)
            )
            return False

    async def _ensure_kafka_subscription(self, topic: str):
        """Ensure Kafka consumer is subscribed to the topic."""
        if topic not in self.supported_topics:
            raise AccessLayerException("UNKNOWN_TOPIC", f"Unsupported topic: {topic}")

        async with self._topic_subscription_lock:
            if topic in self.kafka_consumer.get_subscribed_topics():
                return

            await self.kafka_consumer.subscribe_to_topic(topic, self._handle_kafka_message)
            self.logger.info("Subscribed to Kafka topic", topic=topic)
    
    async def _authenticate_websocket(self, token: Optional[str]) -> dict:
        """Authenticate WebSocket connection."""
        if not token:
            raise AccessLayerException("MISSING_TOKEN", "WebSocket token required")
        
        try:
            # Call auth service
            response = await self.auth_client.verify_websocket_token(token)
            
            if not response.get("valid"):
                raise AccessLayerException("INVALID_TOKEN", "Invalid WebSocket token")
            
            return response.get("user_info", {})
            
        except Exception as e:
            self.logger.error("WebSocket authentication error", error=str(e))
            raise AccessLayerException("AUTH_ERROR", "Authentication failed")
    
    async def _authenticate_sse(self, token: Optional[str]) -> dict:
        """Authenticate SSE connection."""
        if not token:
            raise AccessLayerException("MISSING_TOKEN", "SSE token required")
        
        try:
            # Call auth service
            response = await self.auth_client.verify_token(token)
            
            if not response.get("valid"):
                raise AccessLayerException("INVALID_TOKEN", "Invalid SSE token")
            
            return response.get("user_info", {})
            
        except Exception as e:
            self.logger.error("SSE authentication error", error=str(e))
            raise AccessLayerException("AUTH_ERROR", "Authentication failed")
    
    async def _sse_stream_generator(self, connection_id: str):
        """SSE stream generator."""
        try:
            async for message in self.sse_manager.get_message_stream(connection_id):
                yield message
        except Exception as e:
            self.logger.error("SSE stream error", connection_id=connection_id, error=str(e))
        finally:
            # Clean up connection
            await self.sse_manager.remove_connection(connection_id)
            await self.subscription_manager.remove_connection_subscriptions(connection_id)
    
    async def _handle_kafka_message(self, kafka_message):
        """Handle incoming Kafka message."""
        try:
            # Parse message
            message_data = json.loads(kafka_message.value.decode('utf-8'))
            topic = kafka_message.topic
            
            # Get subscribers
            subscribers = await self.subscription_manager.get_topic_subscribers(topic)
            
            # Create WebSocket message
            ws_message = {
                "topic": topic,
                "data": message_data,
                "timestamp": kafka_message.timestamp or int(asyncio.get_event_loop().time() * 1000),
                "partition": kafka_message.partition,
                "offset": kafka_message.offset
            }
            
            # Broadcast to WebSocket connections
            ws_sent = await self.ws_manager.broadcast_to_topic(topic, ws_message)
            
            # Broadcast to SSE connections
            sse_sent = await self.sse_manager.broadcast_to_topic(topic, ws_message)
            
            self.logger.debug(
                "Kafka message broadcasted",
                topic=topic,
                ws_sent=ws_sent,
                sse_sent=sse_sent,
                total_subscribers=len(subscribers)
            )
            
        except Exception as e:
            self.logger.error("Error handling Kafka message", error=str(e))
    
    async def _check_dependencies(self):
        """Check streaming service dependencies."""
        dependencies = {}

        try:
            # Check Kafka
            if self.kafka_consumer.is_running():
                dependencies["kafka"] = "ok"
            else:
                dependencies["kafka"] = "error"
        except Exception:
            dependencies["kafka"] = "error"

        try:
            # Check auth service
            # Simple health check
            dependencies["auth"] = "ok"
        except Exception:
            dependencies["auth"] = "error"

        try:
            # Check entitlements service
            dependencies["entitlements"] = "ok"
        except Exception:
            dependencies["entitlements"] = "error"

        return dependencies
    
    async def start(self):
        """Start streaming service components."""
        await self.kafka_consumer.start()
        await self.kafka_producer.start()
        await self.ws_manager.start()

        for topic in self.default_stream_topics:
            try:
                await self._ensure_kafka_subscription(topic)
            except Exception as exc:
                self.logger.error(
                    "Failed to subscribe to default topic",
                    topic=topic,
                    error=str(exc)
                )
        
        self.logger.info("Streaming service components started")
    
    async def stop(self):
        """Stop streaming service components."""
        await self.kafka_consumer.stop()
        await self.kafka_producer.stop()
        await self.ws_manager.stop()
        
        self.logger.info("Streaming service components stopped")


def create_app():
    """Create streaming service application."""
    service = StreamingService()
    return service.app


if __name__ == "__main__":
    service = StreamingService()
    service.run()
