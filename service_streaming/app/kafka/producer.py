"""
Kafka producer for Streaming Service.
"""

import json
import time
from typing import Dict, Any, Optional
from kafka import KafkaProducer
from kafka.errors import KafkaError
import sys
import os

# Add shared directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from shared.logging import get_logger
from shared.errors import AccessLayerException


class KafkaProducerManager:
    """Manages Kafka producer for streaming service."""
    
    def __init__(self, bootstrap_servers: str):
        self.bootstrap_servers = bootstrap_servers
        self.logger = get_logger("streaming.kafka.producer")
        self.producer: Optional[KafkaProducer] = None
    
    async def start(self):
        """Start the Kafka producer."""
        try:
            self.producer = KafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda x: json.dumps(x).encode('utf-8'),
                key_serializer=lambda x: x.encode('utf-8') if x else None,
                acks='all',
                retries=3,
                batch_size=16384,
                linger_ms=10,
                compression_type='gzip'
            )
            
            self.logger.info("Kafka producer started")
            
        except Exception as e:
            self.logger.error("Failed to start Kafka producer", error=str(e))
            raise AccessLayerException("KAFKA_PRODUCER_START_FAILED", str(e))
    
    async def stop(self):
        """Stop the Kafka producer."""
        if self.producer:
            self.producer.flush()
            self.producer.close()
            self.logger.info("Kafka producer stopped")
    
    async def send_message(
        self,
        topic: str,
        message: Dict[str, Any],
        key: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> bool:
        """Send a message to Kafka topic."""
        if not self.producer:
            raise AccessLayerException("KAFKA_PRODUCER_NOT_STARTED", "Producer not started")
        
        try:
            # Prepare headers
            kafka_headers = []
            if headers:
                for k, v in headers.items():
                    kafka_headers.append((k, v.encode('utf-8')))
            
            # Send message
            future = self.producer.send(
                topic=topic,
                value=message,
                key=key,
                headers=kafka_headers
            )
            
            # Wait for confirmation
            record_metadata = future.get(timeout=10)
            
            self.logger.debug(
                "Message sent successfully",
                topic=topic,
                partition=record_metadata.partition,
                offset=record_metadata.offset
            )
            
            return True
            
        except KafkaError as e:
            self.logger.error("Kafka error sending message", topic=topic, error=str(e))
            return False
            
        except Exception as e:
            self.logger.error("Error sending message", topic=topic, error=str(e))
            return False
    
    async def send_metrics_message(
        self,
        service_name: str,
        metric_name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None
    ) -> bool:
        """Send metrics message to Kafka."""
        message = {
            "service": service_name,
            "metric": metric_name,
            "value": value,
            "labels": labels or {},
            "timestamp": int(time.time() * 1000)  # milliseconds
        }
        
        return await self.send_message(
            topic="254carbon.metrics.streaming.v1",
            message=message,
            key=service_name
        )
    
    async def send_connection_event(
        self,
        event_type: str,
        connection_id: str,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Send connection event to Kafka."""
        message = {
            "event_type": event_type,
            "connection_id": connection_id,
            "user_id": user_id,
            "tenant_id": tenant_id,
            "metadata": metadata or {},
            "timestamp": int(time.time() * 1000)
        }
        
        return await self.send_message(
            topic="254carbon.streaming.connection.events.v1",
            message=message,
            key=connection_id
        )
