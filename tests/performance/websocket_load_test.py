"""
WebSocket Load Testing Script

This script provides comprehensive WebSocket load testing for the Streaming Service,
including connection management, message handling, and performance monitoring.
"""

import asyncio
import json
import random
import time
import statistics
from typing import Dict, List, Any, Optional
import websockets
import httpx
from dataclasses import dataclass
from datetime import datetime, timedelta
import argparse
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class WebSocketConnection:
    """Represents a WebSocket connection."""
    websocket: websockets.WebSocketServerProtocol
    connection_id: Optional[str] = None
    user_id: str = ""
    tenant_id: str = ""
    subscribed_topics: List[str] = None
    connected_at: datetime = None
    messages_received: int = 0
    last_message_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.subscribed_topics is None:
            self.subscribed_topics = []
        if self.connected_at is None:
            self.connected_at = datetime.now()


@dataclass
class LoadTestMetrics:
    """Metrics for load testing."""
    total_connections: int = 0
    successful_connections: int = 0
    failed_connections: int = 0
    total_messages_sent: int = 0
    total_messages_received: int = 0
    connection_times: List[float] = None
    message_latencies: List[float] = None
    errors: List[str] = None
    
    def __post_init__(self):
        if self.connection_times is None:
            self.connection_times = []
        if self.message_latencies is None:
            self.message_latencies = []
        if self.errors is None:
            self.errors = []


class WebSocketLoadTester:
    """WebSocket load tester for the Streaming Service."""
    
    def __init__(self, 
                 streaming_url: str = "ws://localhost:8001",
                 auth_url: str = "http://localhost:8010",
                 max_connections: int = 100,
                 message_rate: float = 1.0,
                 test_duration: int = 300):
        """
        Initialize the WebSocket load tester.
        
        Args:
            streaming_url: WebSocket streaming service URL
            auth_url: Auth service URL for token validation
            max_connections: Maximum number of concurrent connections
            message_rate: Messages per second per connection
            test_duration: Test duration in seconds
        """
        self.streaming_url = streaming_url
        self.auth_url = auth_url
        self.max_connections = max_connections
        self.message_rate = message_rate
        self.test_duration = test_duration
        
        self.connections: List[WebSocketConnection] = []
        self.metrics = LoadTestMetrics()
        self.running = False
        self.start_time = None
        
        # Test configuration
        self.topics = [
            "pricing.updates",
            "curve.changes", 
            "instruments.new",
            "alerts.system",
            "alerts.user"
        ]
        
        self.filters = [
            {"commodity": "oil"},
            {"commodity": "gas"},
            {"region": "north_sea"},
            {"region": "gulf_of_mexico"},
            {"instrument_type": "futures"},
            {"instrument_type": "options"}
        ]
    
    async def get_auth_token(self) -> str:
        """Get authentication token for testing."""
        # Mock JWT token for testing
        return "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c2VyLTEyMyIsInRlbmFudF9pZCI6InRlbmFudC0xIiwicm9sZXMiOlsidXNlciIsImFuYWx5c3QiXSwiZXhwIjoxNzA1MzE1ODAwfQ.test"
    
    async def create_connection(self, user_id: str, tenant_id: str) -> Optional[WebSocketConnection]:
        """Create a WebSocket connection."""
        try:
            token = await self.get_auth_token()
            uri = f"{self.streaming_url}/ws/stream?token={token}"
            
            start_time = time.time()
            websocket = await websockets.connect(uri)
            connection_time = time.time() - start_time
            
            connection = WebSocketConnection(
                websocket=websocket,
                user_id=user_id,
                tenant_id=tenant_id
            )
            
            self.metrics.connection_times.append(connection_time)
            self.metrics.successful_connections += 1
            
            # Wait for connection established message
            try:
                message = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                data = json.loads(message)
                if data.get("type") == "connection_established":
                    connection.connection_id = data.get("connection_id")
                    logger.info(f"Connection established: {connection.connection_id}")
                else:
                    logger.warning(f"Unexpected message: {data}")
            except asyncio.TimeoutError:
                logger.warning("Timeout waiting for connection established message")
            
            return connection
            
        except Exception as e:
            self.metrics.failed_connections += 1
            self.metrics.errors.append(f"Connection failed: {str(e)}")
            logger.error(f"Failed to create connection: {e}")
            return None
    
    async def subscribe_to_topics(self, connection: WebSocketConnection) -> bool:
        """Subscribe to random topics."""
        try:
            # Select random topics and filters
            num_topics = random.randint(1, 3)
            selected_topics = random.sample(self.topics, num_topics)
            selected_filters = random.choice(self.filters)
            
            subscribe_message = {
                "action": "subscribe",
                "data": {
                    "topics": selected_topics,
                    "filters": selected_filters
                }
            }
            
            await connection.websocket.send(json.dumps(subscribe_message))
            connection.subscribed_topics = selected_topics
            
            # Wait for subscription confirmation
            try:
                message = await asyncio.wait_for(connection.websocket.recv(), timeout=5.0)
                data = json.loads(message)
                if data.get("type") == "subscription_confirmed":
                    logger.info(f"Subscribed to topics: {selected_topics}")
                    return True
                else:
                    logger.warning(f"Unexpected subscription response: {data}")
                    return False
            except asyncio.TimeoutError:
                logger.warning("Timeout waiting for subscription confirmation")
                return False
                
        except Exception as e:
            self.metrics.errors.append(f"Subscription failed: {str(e)}")
            logger.error(f"Failed to subscribe: {e}")
            return False
    
    async def send_ping(self, connection: WebSocketConnection) -> bool:
        """Send ping message."""
        try:
            ping_message = {
                "action": "ping",
                "data": {}
            }
            
            start_time = time.time()
            await connection.websocket.send(json.dumps(ping_message))
            
            # Wait for pong response
            try:
                message = await asyncio.wait_for(connection.websocket.recv(), timeout=5.0)
                data = json.loads(message)
                if data.get("type") == "pong":
                    latency = time.time() - start_time
                    self.metrics.message_latencies.append(latency)
                    self.metrics.total_messages_sent += 1
                    return True
                else:
                    logger.warning(f"Unexpected ping response: {data}")
                    return False
            except asyncio.TimeoutError:
                logger.warning("Timeout waiting for pong response")
                return False
                
        except Exception as e:
            self.metrics.errors.append(f"Ping failed: {str(e)}")
            logger.error(f"Failed to send ping: {e}")
            return False
    
    async def handle_messages(self, connection: WebSocketConnection):
        """Handle incoming messages."""
        try:
            async for message in connection.websocket:
                try:
                    data = json.loads(message)
                    connection.messages_received += 1
                    connection.last_message_at = datetime.now()
                    self.metrics.total_messages_received += 1
                    
                    # Log data messages
                    if data.get("type") == "data":
                        logger.debug(f"Received data message: {data.get('topic')}")
                    
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON message: {message}")
                except Exception as e:
                    logger.error(f"Error handling message: {e}")
                    
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"Connection closed: {connection.connection_id}")
        except Exception as e:
            self.metrics.errors.append(f"Message handling failed: {str(e)}")
            logger.error(f"Error in message handling: {e}")
    
    async def connection_worker(self, user_id: str, tenant_id: str):
        """Worker for managing a single connection."""
        connection = await self.create_connection(user_id, tenant_id)
        if not connection:
            return
        
        self.connections.append(connection)
        
        try:
            # Subscribe to topics
            await self.subscribe_to_topics(connection)
            
            # Start message handling task
            message_task = asyncio.create_task(self.handle_messages(connection))
            
            # Send periodic pings
            ping_interval = 1.0 / self.message_rate
            last_ping = time.time()
            
            while self.running and connection.websocket.open:
                current_time = time.time()
                
                # Send ping if interval has passed
                if current_time - last_ping >= ping_interval:
                    await self.send_ping(connection)
                    last_ping = current_time
                
                # Small delay to prevent busy waiting
                await asyncio.sleep(0.01)
            
            # Cancel message handling task
            message_task.cancel()
            try:
                await message_task
            except asyncio.CancelledError:
                pass
                
        except Exception as e:
            self.metrics.errors.append(f"Connection worker failed: {str(e)}")
            logger.error(f"Connection worker error: {e}")
        finally:
            # Close connection
            try:
                await connection.websocket.close()
            except Exception as e:
                logger.error(f"Error closing connection: {e}")
            
            # Remove from connections list
            if connection in self.connections:
                self.connections.remove(connection)
    
    async def run_load_test(self):
        """Run the load test."""
        logger.info(f"Starting WebSocket load test:")
        logger.info(f"  Max connections: {self.max_connections}")
        logger.info(f"  Message rate: {self.message_rate} msg/sec per connection")
        logger.info(f"  Test duration: {self.test_duration} seconds")
        logger.info(f"  Streaming URL: {self.streaming_url}")
        
        self.running = True
        self.start_time = time.time()
        
        # Create connections gradually
        connection_tasks = []
        for i in range(self.max_connections):
            user_id = f"load-test-user-{i}"
            tenant_id = f"tenant-{(i % 5) + 1}"  # Distribute across 5 tenants
            
            task = asyncio.create_task(self.connection_worker(user_id, tenant_id))
            connection_tasks.append(task)
            
            # Small delay between connections to avoid overwhelming the server
            await asyncio.sleep(0.1)
        
        logger.info(f"Created {len(connection_tasks)} connection tasks")
        
        # Run for specified duration
        try:
            await asyncio.sleep(self.test_duration)
        except KeyboardInterrupt:
            logger.info("Test interrupted by user")
        
        # Stop the test
        self.running = False
        logger.info("Stopping load test...")
        
        # Wait for all connections to close
        for task in connection_tasks:
            task.cancel()
        
        # Wait for tasks to complete
        await asyncio.gather(*connection_tasks, return_exceptions=True)
        
        # Calculate and display results
        self.display_results()
    
    def display_results(self):
        """Display test results."""
        end_time = time.time()
        total_time = end_time - self.start_time
        
        logger.info("\n" + "="*60)
        logger.info("WEBSOCKET LOAD TEST RESULTS")
        logger.info("="*60)
        
        # Connection statistics
        logger.info(f"Total connections attempted: {self.max_connections}")
        logger.info(f"Successful connections: {self.metrics.successful_connections}")
        logger.info(f"Failed connections: {self.metrics.failed_connections}")
        logger.info(f"Success rate: {(self.metrics.successful_connections / self.max_connections) * 100:.2f}%")
        
        # Connection timing
        if self.metrics.connection_times:
            logger.info(f"Average connection time: {statistics.mean(self.metrics.connection_times):.3f}s")
            logger.info(f"Min connection time: {min(self.metrics.connection_times):.3f}s")
            logger.info(f"Max connection time: {max(self.metrics.connection_times):.3f}s")
            logger.info(f"Median connection time: {statistics.median(self.metrics.connection_times):.3f}s")
        
        # Message statistics
        logger.info(f"Total messages sent: {self.metrics.total_messages_sent}")
        logger.info(f"Total messages received: {self.metrics.total_messages_received}")
        logger.info(f"Messages per second: {self.metrics.total_messages_sent / total_time:.2f}")
        
        # Message latency
        if self.metrics.message_latencies:
            logger.info(f"Average message latency: {statistics.mean(self.metrics.message_latencies):.3f}s")
            logger.info(f"Min message latency: {min(self.metrics.message_latencies):.3f}s")
            logger.info(f"Max message latency: {max(self.metrics.message_latencies):.3f}s")
            logger.info(f"Median message latency: {statistics.median(self.metrics.message_latencies):.3f}s")
        
        # Error statistics
        logger.info(f"Total errors: {len(self.metrics.errors)}")
        if self.metrics.errors:
            error_counts = {}
            for error in self.metrics.errors:
                error_type = error.split(':')[0]
                error_counts[error_type] = error_counts.get(error_type, 0) + 1
            
            logger.info("Error breakdown:")
            for error_type, count in error_counts.items():
                logger.info(f"  {error_type}: {count}")
        
        # Active connections
        active_connections = len([c for c in self.connections if c.websocket.open])
        logger.info(f"Active connections at end: {active_connections}")
        
        # Performance assessment
        logger.info("\nPERFORMANCE ASSESSMENT:")
        if self.metrics.successful_connections / self.max_connections >= 0.95:
            logger.info("✅ Connection success rate: EXCELLENT")
        elif self.metrics.successful_connections / self.max_connections >= 0.90:
            logger.info("✅ Connection success rate: GOOD")
        elif self.metrics.successful_connections / self.max_connections >= 0.80:
            logger.info("⚠️  Connection success rate: ACCEPTABLE")
        else:
            logger.info("❌ Connection success rate: POOR")
        
        if self.metrics.message_latencies:
            avg_latency = statistics.mean(self.metrics.message_latencies)
            if avg_latency <= 0.1:
                logger.info("✅ Message latency: EXCELLENT")
            elif avg_latency <= 0.5:
                logger.info("✅ Message latency: GOOD")
            elif avg_latency <= 1.0:
                logger.info("⚠️  Message latency: ACCEPTABLE")
            else:
                logger.info("❌ Message latency: POOR")
        
        if len(self.metrics.errors) == 0:
            logger.info("✅ Error rate: EXCELLENT")
        elif len(self.metrics.errors) / self.max_connections <= 0.01:
            logger.info("✅ Error rate: GOOD")
        elif len(self.metrics.errors) / self.max_connections <= 0.05:
            logger.info("⚠️  Error rate: ACCEPTABLE")
        else:
            logger.info("❌ Error rate: POOR")
        
        logger.info("="*60)


async def main():
    """Main function for running WebSocket load tests."""
    parser = argparse.ArgumentParser(description="WebSocket Load Testing")
    parser.add_argument("--streaming-url", default="ws://localhost:8001", 
                       help="WebSocket streaming service URL")
    parser.add_argument("--auth-url", default="http://localhost:8010",
                       help="Auth service URL")
    parser.add_argument("--max-connections", type=int, default=100,
                       help="Maximum number of concurrent connections")
    parser.add_argument("--message-rate", type=float, default=1.0,
                       help="Messages per second per connection")
    parser.add_argument("--test-duration", type=int, default=300,
                       help="Test duration in seconds")
    parser.add_argument("--log-level", default="INFO",
                       choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                       help="Logging level")
    
    args = parser.parse_args()
    
    # Set logging level
    logging.getLogger().setLevel(getattr(logging, args.log_level))
    
    # Create and run load tester
    tester = WebSocketLoadTester(
        streaming_url=args.streaming_url,
        auth_url=args.auth_url,
        max_connections=args.max_connections,
        message_rate=args.message_rate,
        test_duration=args.test_duration
    )
    
    try:
        await tester.run_load_test()
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
    except Exception as e:
        logger.error(f"Test failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
