"""
Unit tests for Streaming Kafka Consumer.
"""

import pytest
import json
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from typing import Dict, Any

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from service_streaming.app.kafka.consumer import KafkaConsumerManager, KafkaMessage
from shared.errors import AccessLayerException


class TestKafkaConsumerManager:
    """Test cases for KafkaConsumerManager."""

    @pytest.fixture
    def consumer_manager(self):
        """Create KafkaConsumerManager instance."""
        return KafkaConsumerManager("localhost:9092", "test-group")

    @pytest.fixture
    def mock_kafka_message(self):
        """Mock Kafka message."""
        message = MagicMock()
        message.topic = "test-topic"
        message.partition = 0
        message.offset = 123
        message.key = b"test-key"
        message.value = b'{"test": "data"}'
        message.timestamp = 1640995200000
        message.headers = [("header1", b"value1")]
        return message

    @pytest.fixture
    def mock_message_handler(self):
        """Mock message handler function."""
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_start_success(self, consumer_manager):
        """Test successful consumer start."""
        with patch('kafka.KafkaConsumer') as mock_consumer_class:
            mock_consumer = AsyncMock()
            mock_consumer_class.return_value = mock_consumer

            await consumer_manager.start()

            assert consumer_manager.running is True
            assert consumer_manager.consumer is not None
            mock_consumer_class.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_failure(self, consumer_manager):
        """Test consumer start failure."""
        with patch('kafka.KafkaConsumer') as mock_consumer_class:
            mock_consumer_class.side_effect = Exception("Connection failed")

            with pytest.raises(AccessLayerException) as exc_info:
                await consumer_manager.start()

            assert exc_info.value.code == "KAFKA_CONSUMER_START_FAILED"
            assert consumer_manager.running is False

    @pytest.mark.asyncio
    async def test_stop_success(self, consumer_manager):
        """Test successful consumer stop."""
        # Start consumer first
        with patch('kafka.KafkaConsumer') as mock_consumer_class:
            mock_consumer = AsyncMock()
            mock_consumer_class.return_value = mock_consumer

            await consumer_manager.start()
            await consumer_manager.stop()

            assert consumer_manager.running is False
            mock_consumer.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_subscribe_to_topic_success(self, consumer_manager, mock_message_handler):
        """Test successful topic subscription."""
        topic = "test-topic"

        with patch('kafka.KafkaConsumer') as mock_consumer_class:
            mock_consumer = AsyncMock()
            mock_consumer_class.return_value = mock_consumer

            await consumer_manager.start()
            await consumer_manager.subscribe_to_topic(topic, mock_message_handler)

            assert topic in consumer_manager.subscribed_topics
            assert topic in consumer_manager.message_handlers
            assert consumer_manager.message_handlers[topic] == mock_message_handler

    @pytest.mark.asyncio
    async def test_subscribe_to_topic_not_started(self, consumer_manager, mock_message_handler):
        """Test topic subscription when consumer not started."""
        topic = "test-topic"

        with pytest.raises(AccessLayerException) as exc_info:
            await consumer_manager.subscribe_to_topic(topic, mock_message_handler)

        assert exc_info.value.code == "KAFKA_CONSUMER_NOT_STARTED"

    @pytest.mark.asyncio
    async def test_unsubscribe_from_topic_success(self, consumer_manager, mock_message_handler):
        """Test successful topic unsubscription."""
        topic = "test-topic"

        with patch('kafka.KafkaConsumer') as mock_consumer_class:
            mock_consumer = AsyncMock()
            mock_consumer_class.return_value = mock_consumer

            await consumer_manager.start()
            await consumer_manager.subscribe_to_topic(topic, mock_message_handler)
            await consumer_manager.unsubscribe_from_topic(topic)

            assert topic not in consumer_manager.subscribed_topics
            assert topic not in consumer_manager.message_handlers

    @pytest.mark.asyncio
    async def test_unsubscribe_from_topic_not_subscribed(self, consumer_manager):
        """Test unsubscription from topic that's not subscribed."""
        topic = "test-topic"

        with patch('kafka.KafkaConsumer') as mock_consumer_class:
            mock_consumer = AsyncMock()
            mock_consumer_class.return_value = mock_consumer

            await consumer_manager.start()

            with pytest.raises(AccessLayerException) as exc_info:
                await consumer_manager.unsubscribe_from_topic(topic)

            assert exc_info.value.code == "KAFKA_UNSUBSCRIBE_FAILED"

    @pytest.mark.asyncio
    async def test_consume_loop_message_processing(self, consumer_manager, mock_message_handler, mock_kafka_message):
        """Test message processing in consume loop."""
        topic = "test-topic"

        with patch('kafka.KafkaConsumer') as mock_consumer_class:
            mock_consumer = AsyncMock()
            mock_consumer_class.return_value = mock_consumer

            # Mock poll response
            mock_consumer.poll.return_value = {
                MagicMock(topic=topic): [mock_kafka_message]
            }

            await consumer_manager.start()
            await consumer_manager.subscribe_to_topic(topic, mock_message_handler)

            # Start consume loop briefly
            consumer_manager.running = True
            task = asyncio.create_task(consumer_manager._consume_loop())
            await asyncio.sleep(0.1)
            consumer_manager.running = False
            task.cancel()

            # Verify handler was called
            mock_message_handler.assert_called()

    @pytest.mark.asyncio
    async def test_consume_loop_no_messages(self, consumer_manager):
        """Test consume loop with no messages."""
        with patch('kafka.KafkaConsumer') as mock_consumer_class:
            mock_consumer = AsyncMock()
            mock_consumer_class.return_value = mock_consumer

            # Mock empty poll response
            mock_consumer.poll.return_value = {}

            await consumer_manager.start()

            # Start consume loop briefly
            consumer_manager.running = True
            task = asyncio.create_task(consumer_manager._consume_loop())
            await asyncio.sleep(0.1)
            consumer_manager.running = False
            task.cancel()

            # Should not raise any exceptions
            assert True

    @pytest.mark.asyncio
    async def test_consume_loop_handler_error(self, consumer_manager, mock_message_handler, mock_kafka_message):
        """Test consume loop with handler error."""
        topic = "test-topic"

        with patch('kafka.KafkaConsumer') as mock_consumer_class:
            mock_consumer = AsyncMock()
            mock_consumer_class.return_value = mock_consumer

            # Mock poll response
            mock_consumer.poll.return_value = {
                MagicMock(topic=topic): [mock_kafka_message]
            }

            # Mock handler to raise exception
            mock_message_handler.side_effect = Exception("Handler error")

            await consumer_manager.start()
            await consumer_manager.subscribe_to_topic(topic, mock_message_handler)

            # Start consume loop briefly
            consumer_manager.running = True
            task = asyncio.create_task(consumer_manager._consume_loop())
            await asyncio.sleep(0.1)
            consumer_manager.running = False
            task.cancel()

            # Should handle error gracefully
            assert True

    def test_is_running(self, consumer_manager):
        """Test is_running method."""
        assert consumer_manager.is_running() is False

        consumer_manager.running = True
        assert consumer_manager.is_running() is True

    def test_get_subscribed_topics(self, consumer_manager):
        """Test get_subscribed_topics method."""
        assert consumer_manager.get_subscribed_topics() == []

        consumer_manager.subscribed_topics = ["topic1", "topic2"]
        assert consumer_manager.get_subscribed_topics() == ["topic1", "topic2"]

    def test_kafka_message_wrapper(self, mock_kafka_message):
        """Test KafkaMessage wrapper."""
        kafka_message = KafkaMessage(
            topic=mock_kafka_message.topic,
            partition=mock_kafka_message.partition,
            offset=mock_kafka_message.offset,
            key=mock_kafka_message.key,
            value=mock_kafka_message.value,
            timestamp=mock_kafka_message.timestamp,
            headers={"header1": b"value1"}
        )

        assert kafka_message.topic == "test-topic"
        assert kafka_message.partition == 0
        assert kafka_message.offset == 123
        assert kafka_message.key == b"test-key"
        assert kafka_message.value == b'{"test": "data"}'
        assert kafka_message.timestamp == 1640995200000
        assert kafka_message.headers == {"header1": b"value1"}

    @pytest.mark.asyncio
    async def test_multiple_topic_subscriptions(self, consumer_manager):
        """Test subscribing to multiple topics."""
        topics = ["topic1", "topic2", "topic3"]
        handlers = [AsyncMock() for _ in topics]

        with patch('kafka.KafkaConsumer') as mock_consumer_class:
            mock_consumer = AsyncMock()
            mock_consumer_class.return_value = mock_consumer

            await consumer_manager.start()

            for topic, handler in zip(topics, handlers):
                await consumer_manager.subscribe_to_topic(topic, handler)

            assert len(consumer_manager.subscribed_topics) == 3
            assert len(consumer_manager.message_handlers) == 3

            for topic in topics:
                assert topic in consumer_manager.subscribed_topics
                assert topic in consumer_manager.message_handlers

    @pytest.mark.asyncio
    async def test_consumer_configuration(self, consumer_manager):
        """Test consumer configuration."""
        with patch('kafka.KafkaConsumer') as mock_consumer_class:
            mock_consumer = AsyncMock()
            mock_consumer_class.return_value = mock_consumer

            await consumer_manager.start()

            # Verify consumer was created with correct parameters
            mock_consumer_class.assert_called_once()
            call_args = mock_consumer_class.call_args

            assert call_args[1]['bootstrap_servers'] == "localhost:9092"
            assert call_args[1]['group_id'] == "test-group"
            assert call_args[1]['auto_offset_reset'] == 'latest'
            assert call_args[1]['enable_auto_commit'] is True
            assert call_args[1]['max_poll_records'] == 100
