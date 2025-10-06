"""
Kafka consumer for Streaming Service.
"""

import asyncio
import json
from typing import Dict, Any, Optional, Callable, List
from dataclasses import dataclass
from kafka import KafkaConsumer
from kafka.errors import KafkaError
import sys
import os

# Add shared directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from shared.logging import get_logger
from shared.errors import AccessLayerException


@dataclass
class KafkaMessage:
    """Kafka message wrapper."""
    topic: str
    partition: int
    offset: int
    key: Optional[bytes]
    value: bytes
    timestamp: Optional[int]
    headers: Optional[Dict[str, bytes]]


class KafkaConsumerManager:
    """Manages Kafka consumer for streaming service."""
    
    def __init__(self, bootstrap_servers: str, group_id: str):
        self.bootstrap_servers = bootstrap_servers
        self.group_id = group_id
        self.logger = get_logger("streaming.kafka.consumer")
        self.consumer: Optional[KafkaConsumer] = None
        self.subscribed_topics: List[str] = []
        self.message_handlers: Dict[str, Callable[[KafkaMessage], None]] = {}
        self.running = False
        self._consumer_task: Optional[asyncio.Task] = None
    
    async def start(self):
        """Start the Kafka consumer."""
        try:
            self.consumer = KafkaConsumer(
                bootstrap_servers=self.bootstrap_servers,
                group_id=self.group_id,
                value_deserializer=lambda x: x,  # Keep as bytes for now
                key_deserializer=lambda x: x,
                auto_offset_reset='latest',
                enable_auto_commit=True,
                max_poll_records=100,
                session_timeout_ms=30000,
                heartbeat_interval_ms=10000
            )
            
            self.running = True
            self._consumer_task = asyncio.create_task(self._consume_loop())
            self.logger.info("Kafka consumer started", group_id=self.group_id)
            
        except Exception as e:
            self.logger.error("Failed to start Kafka consumer", error=str(e))
            raise AccessLayerException("KAFKA_CONSUMER_START_FAILED", str(e))
    
    async def stop(self):
        """Stop the Kafka consumer."""
        self.running = False
        if self._consumer_task:
            self._consumer_task.cancel()
            try:
                await self._consumer_task
            except asyncio.CancelledError:
                pass
        
        if self.consumer:
            self.consumer.close()
            self.logger.info("Kafka consumer stopped")
    
    async def subscribe_to_topic(self, topic: str, handler: Callable[[KafkaMessage], None]):
        """Subscribe to a Kafka topic."""
        if topic in self.subscribed_topics:
            self.logger.warning("Already subscribed to topic", topic=topic)
            return
        
        if not self.consumer:
            raise AccessLayerException("KAFKA_CONSUMER_NOT_STARTED", "Consumer not started")
        
        try:
            # Subscribe to topic
            self.consumer.subscribe([topic])
            self.subscribed_topics.append(topic)
            self.message_handlers[topic] = handler
            
            self.logger.info("Subscribed to topic", topic=topic)
            
        except Exception as e:
            self.logger.error("Failed to subscribe to topic", topic=topic, error=str(e))
            raise AccessLayerException("KAFKA_SUBSCRIBE_FAILED", str(e))
    
    async def unsubscribe_from_topic(self, topic: str):
        """Unsubscribe from a Kafka topic."""
        if topic not in self.subscribed_topics:
            self.logger.warning("Not subscribed to topic", topic=topic)
            return
        
        try:
            # Remove from subscriptions
            self.subscribed_topics.remove(topic)
            if topic in self.message_handlers:
                del self.message_handlers[topic]
            
            # Re-subscribe with remaining topics
            if self.subscribed_topics:
                self.consumer.subscribe(self.subscribed_topics)
            else:
                self.consumer.unsubscribe()
            
            self.logger.info("Unsubscribed from topic", topic=topic)
            
        except Exception as e:
            self.logger.error("Failed to unsubscribe from topic", topic=topic, error=str(e))
            raise AccessLayerException("KAFKA_UNSUBSCRIBE_FAILED", str(e))
    
    async def _consume_loop(self):
        """Main consumption loop."""
        while self.running:
            try:
                if not self.consumer:
                    await asyncio.sleep(1)
                    continue
                
                # Poll for messages
                message_batch = self.consumer.poll(timeout_ms=1000)
                
                if not message_batch:
                    continue
                
                # Process messages
                for topic_partition, messages in message_batch.items():
                    topic = topic_partition.topic
                    
                    if topic not in self.message_handlers:
                        continue
                    
                    handler = self.message_handlers[topic]
                    
                    for message in messages:
                        try:
                            # Wrap message
                            kafka_message = KafkaMessage(
                                topic=message.topic,
                                partition=message.partition,
                                offset=message.offset,
                                key=message.key,
                                value=message.value,
                                timestamp=message.timestamp,
                                headers=dict(message.headers) if message.headers else None
                            )
                            
                            # Call handler
                            await asyncio.get_event_loop().run_in_executor(
                                None, handler, kafka_message
                            )
                            
                        except Exception as e:
                            self.logger.error(
                                "Error processing message",
                                topic=topic,
                                offset=message.offset,
                                error=str(e)
                            )
                
            except KafkaError as e:
                self.logger.error("Kafka error in consume loop", error=str(e))
                await asyncio.sleep(5)  # Back off on errors
                
            except Exception as e:
                self.logger.error("Unexpected error in consume loop", error=str(e))
                await asyncio.sleep(1)
    
    def get_subscribed_topics(self) -> List[str]:
        """Get list of subscribed topics."""
        return self.subscribed_topics.copy()
    
    def is_running(self) -> bool:
        """Check if consumer is running."""
        return self.running
