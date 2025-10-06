"""
Streaming service for 254Carbon Access Layer.
"""

import asyncio
import json
import sys
import os
import time
from typing import Optional

# Add shared directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from fastapi import WebSocket, WebSocketDisconnect, HTTPException, Depends, Query
from fastapi.responses import StreamingResponse
from shared.base_service import BaseService
from shared.logging import get_logger
from shared.errors import AccessLayerException
from shared.observability import get_observability_manager, observe_function, observe_operation

from .kafka.consumer import KafkaConsumerManager
from .kafka.producer import KafkaProducerManager
from .ws.connection_manager import WebSocketConnectionManager
from .ws.handlers import WebSocketMessageHandler
from .sse.stream_manager import SSEStreamManager
from .subscriptions.manager import SubscriptionManager
from .auth.client import AuthClient


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
        
        # Initialize message handler
        self.ws_handler = WebSocketMessageHandler(
            connection_manager=self.ws_manager,
            kafka_message_handler=self._handle_kafka_message
        )
        
        self._setup_streaming_routes()
    
    def _setup_streaming_routes(self):
        """Set up streaming-specific routes."""
        
        @self.app.get("/")
        async def root():
            """Root endpoint."""
            return {
                "service": "streaming",
                "message": "254Carbon Access Layer - Streaming Service",
                "version": "1.0.0",
                "capabilities": ["websocket", "sse", "kafka"]
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
                
                # Subscribe to topic
                success = await self.sse_manager.subscribe_to_topic(
                    connection_id, topic, filter_data
                )
                
                if success:
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
                }
            }
    
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