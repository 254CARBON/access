"""
Unit tests for MetricsCollector.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timedelta

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from service_metrics.app.ingestion.collector import MetricsCollector, MetricPoint, MetricSeries, MetricType


class TestMetricsCollector:
    """Test cases for MetricsCollector."""
    
    @pytest.fixture
    def metrics_collector(self):
        """Create MetricsCollector instance."""
        return MetricsCollector(max_queue_size=1000, batch_size=100)
    
    @pytest.fixture
    def mock_metric_point(self):
        """Create mock MetricPoint."""
        return MetricPoint(
            name="test_metric",
            value=42.5,
            metric_type=MetricType.GAUGE,
            labels={"environment": "test", "service": "test-service"},
            timestamp=datetime.now(),
            service="test-service",
            tenant_id="tenant-1"
        )
    
    @pytest.fixture
    def mock_metric_series(self):
        """Create mock MetricSeries."""
        return MetricSeries(
            name="test_metric",
            metric_type=MetricType.GAUGE,
            labels={"environment": "test", "service": "test-service"},
            points=[],
            service="test-service",
            tenant_id="tenant-1"
        )
    
    @pytest.mark.asyncio
    async def test_start(self, metrics_collector):
        """Test starting the collector."""
        # Test
        await metrics_collector.start()
        
        # Assertions
        assert metrics_collector.running is True
        assert metrics_collector._processing_task is not None
    
    @pytest.mark.asyncio
    async def test_stop(self, metrics_collector):
        """Test stopping the collector."""
        # Start collector
        await metrics_collector.start()
        
        # Test
        await metrics_collector.stop()
        
        # Assertions
        assert metrics_collector.running is False
        assert metrics_collector._processing_task is None
    
    @pytest.mark.asyncio
    async def test_collect_metric_success(self, metrics_collector, mock_metric_point):
        """Test successful metric collection."""
        # Test
        result = await metrics_collector.collect_metric(mock_metric_point)
        
        # Assertions
        assert result is True
        assert metrics_collector.queue.qsize() == 1
    
    @pytest.mark.asyncio
    async def test_collect_metric_queue_full(self, metrics_collector, mock_metric_point):
        """Test metric collection with full queue."""
        # Fill queue
        for _ in range(1000):
            await metrics_collector.collect_metric(mock_metric_point)
        
        # Test
        result = await metrics_collector.collect_metric(mock_metric_point)
        
        # Assertions
        assert result is False
        assert metrics_collector.queue.qsize() == 1000
    
    @pytest.mark.asyncio
    async def test_collect_metric_not_running(self, metrics_collector, mock_metric_point):
        """Test metric collection when not running."""
        # Test
        result = await metrics_collector.collect_metric(mock_metric_point)
        
        # Assertions
        assert result is False
        assert metrics_collector.queue.qsize() == 0
    
    @pytest.mark.asyncio
    async def test_collect_metric_batch_success(self, metrics_collector, mock_metric_point):
        """Test successful batch metric collection."""
        # Create batch
        batch = [mock_metric_point for _ in range(5)]
        
        # Test
        result = await metrics_collector.collect_metric_batch(batch)
        
        # Assertions
        assert result is True
        assert metrics_collector.queue.qsize() == 5
    
    @pytest.mark.asyncio
    async def test_collect_metric_batch_empty(self, metrics_collector):
        """Test batch metric collection with empty batch."""
        # Test
        result = await metrics_collector.collect_metric_batch([])
        
        # Assertions
        assert result is True
        assert metrics_collector.queue.qsize() == 0
    
    @pytest.mark.asyncio
    async def test_collect_metric_batch_not_running(self, metrics_collector, mock_metric_point):
        """Test batch metric collection when not running."""
        # Create batch
        batch = [mock_metric_point for _ in range(5)]
        
        # Test
        result = await metrics_collector.collect_metric_batch(batch)
        
        # Assertions
        assert result is False
        assert metrics_collector.queue.qsize() == 0
    
    @pytest.mark.asyncio
    async def test_collect_metric_batch_queue_full(self, metrics_collector, mock_metric_point):
        """Test batch metric collection with full queue."""
        # Fill queue
        for _ in range(1000):
            await metrics_collector.collect_metric(mock_metric_point)
        
        # Create batch
        batch = [mock_metric_point for _ in range(5)]
        
        # Test
        result = await metrics_collector.collect_metric_batch(batch)
        
        # Assertions
        assert result is False
        assert metrics_collector.queue.qsize() == 1000
    
    @pytest.mark.asyncio
    async def test_get_metric_series_success(self, metrics_collector, mock_metric_point):
        """Test successful metric series retrieval."""
        # Collect metric
        await metrics_collector.collect_metric(mock_metric_point)
        
        # Process queue
        await metrics_collector._process_queue()
        
        # Test
        series = metrics_collector.get_metric_series("test_metric")
        
        # Assertions
        assert series is not None
        assert series.name == "test_metric"
        assert len(series.points) == 1
        assert series.points[0] == mock_metric_point
    
    @pytest.mark.asyncio
    async def test_get_metric_series_not_found(self, metrics_collector):
        """Test metric series retrieval for non-existent series."""
        # Test
        series = metrics_collector.get_metric_series("nonexistent_metric")
        
        # Assertions
        assert series is None
    
    @pytest.mark.asyncio
    async def test_get_all_metric_series(self, metrics_collector, mock_metric_point):
        """Test retrieval of all metric series."""
        # Collect metric
        await metrics_collector.collect_metric(mock_metric_point)
        
        # Process queue
        await metrics_collector._process_queue()
        
        # Test
        series_list = metrics_collector.get_all_metric_series()
        
        # Assertions
        assert len(series_list) == 1
        assert series_list[0].name == "test_metric"
    
    @pytest.mark.asyncio
    async def test_get_metric_series_by_service(self, metrics_collector, mock_metric_point):
        """Test metric series retrieval by service."""
        # Collect metric
        await metrics_collector.collect_metric(mock_metric_point)
        
        # Process queue
        await metrics_collector._process_queue()
        
        # Test
        series_list = metrics_collector.get_metric_series_by_service("test-service")
        
        # Assertions
        assert len(series_list) == 1
        assert series_list[0].service == "test-service"
    
    @pytest.mark.asyncio
    async def test_get_metric_series_by_tenant(self, metrics_collector, mock_metric_point):
        """Test metric series retrieval by tenant."""
        # Collect metric
        await metrics_collector.collect_metric(mock_metric_point)
        
        # Process queue
        await metrics_collector._process_queue()
        
        # Test
        series_list = metrics_collector.get_metric_series_by_tenant("tenant-1")
        
        # Assertions
        assert len(series_list) == 1
        assert series_list[0].tenant_id == "tenant-1"
    
    @pytest.mark.asyncio
    async def test_get_metric_series_by_type(self, metrics_collector, mock_metric_point):
        """Test metric series retrieval by type."""
        # Collect metric
        await metrics_collector.collect_metric(mock_metric_point)
        
        # Process queue
        await metrics_collector._process_queue()
        
        # Test
        series_list = metrics_collector.get_metric_series_by_type(MetricType.GAUGE)
        
        # Assertions
        assert len(series_list) == 1
        assert series_list[0].metric_type == MetricType.GAUGE
    
    @pytest.mark.asyncio
    async def test_get_metric_series_with_labels(self, metrics_collector, mock_metric_point):
        """Test metric series retrieval with label filters."""
        # Collect metric
        await metrics_collector.collect_metric(mock_metric_point)
        
        # Process queue
        await metrics_collector._process_queue()
        
        # Test
        series_list = metrics_collector.get_metric_series_with_labels({"environment": "test"})
        
        # Assertions
        assert len(series_list) == 1
        assert series_list[0].labels["environment"] == "test"
    
    @pytest.mark.asyncio
    async def test_get_metric_series_with_labels_no_match(self, metrics_collector, mock_metric_point):
        """Test metric series retrieval with non-matching label filters."""
        # Collect metric
        await metrics_collector.collect_metric(mock_metric_point)
        
        # Process queue
        await metrics_collector._process_queue()
        
        # Test
        series_list = metrics_collector.get_metric_series_with_labels({"environment": "production"})
        
        # Assertions
        assert len(series_list) == 0
    
    @pytest.mark.asyncio
    async def test_get_metric_series_time_range(self, metrics_collector, mock_metric_point):
        """Test metric series retrieval within time range."""
        # Collect metric
        await metrics_collector.collect_metric(mock_metric_point)
        
        # Process queue
        await metrics_collector._process_queue()
        
        # Test
        start_time = datetime.now() - timedelta(hours=1)
        end_time = datetime.now() + timedelta(hours=1)
        series_list = metrics_collector.get_metric_series_time_range(start_time, end_time)
        
        # Assertions
        assert len(series_list) == 1
        assert series_list[0].name == "test_metric"
    
    @pytest.mark.asyncio
    async def test_get_metric_series_time_range_no_match(self, metrics_collector, mock_metric_point):
        """Test metric series retrieval outside time range."""
        # Collect metric
        await metrics_collector.collect_metric(mock_metric_point)
        
        # Process queue
        await metrics_collector._process_queue()
        
        # Test
        start_time = datetime.now() + timedelta(hours=1)
        end_time = datetime.now() + timedelta(hours=2)
        series_list = metrics_collector.get_metric_series_time_range(start_time, end_time)
        
        # Assertions
        assert len(series_list) == 0
    
    @pytest.mark.asyncio
    async def test_delete_metric_series(self, metrics_collector, mock_metric_point):
        """Test metric series deletion."""
        # Collect metric
        await metrics_collector.collect_metric(mock_metric_point)
        
        # Process queue
        await metrics_collector._process_queue()
        
        # Test
        result = metrics_collector.delete_metric_series("test_metric")
        
        # Assertions
        assert result is True
        assert metrics_collector.get_metric_series("test_metric") is None
    
    @pytest.mark.asyncio
    async def test_delete_metric_series_not_found(self, metrics_collector):
        """Test metric series deletion for non-existent series."""
        # Test
        result = metrics_collector.delete_metric_series("nonexistent_metric")
        
        # Assertions
        assert result is False
    
    @pytest.mark.asyncio
    async def test_clear_all_metrics(self, metrics_collector, mock_metric_point):
        """Test clearing all metrics."""
        # Collect metric
        await metrics_collector.collect_metric(mock_metric_point)
        
        # Process queue
        await metrics_collector._process_queue()
        
        # Test
        metrics_collector.clear_all_metrics()
        
        # Assertions
        assert len(metrics_collector.get_all_metric_series()) == 0
    
    @pytest.mark.asyncio
    async def test_get_collector_stats(self, metrics_collector, mock_metric_point):
        """Test collector statistics retrieval."""
        # Collect metric
        await metrics_collector.collect_metric(mock_metric_point)
        
        # Process queue
        await metrics_collector._process_queue()
        
        # Test
        stats = metrics_collector.get_collector_stats()
        
        # Assertions
        assert stats["queue_size"] == 0
        assert stats["total_series"] == 1
        assert stats["total_points"] == 1
        assert stats["max_queue_size"] == 1000
        assert stats["batch_size"] == 100
        assert stats["running"] is False
    
    @pytest.mark.asyncio
    async def test_get_collector_stats_running(self, metrics_collector, mock_metric_point):
        """Test collector statistics retrieval when running."""
        # Start collector
        await metrics_collector.start()
        
        # Collect metric
        await metrics_collector.collect_metric(mock_metric_point)
        
        # Test
        stats = metrics_collector.get_collector_stats()
        
        # Assertions
        assert stats["running"] is True
        assert stats["queue_size"] == 1
        
        # Cleanup
        await metrics_collector.stop()
    
    @pytest.mark.asyncio
    async def test_process_queue_success(self, metrics_collector, mock_metric_point):
        """Test successful queue processing."""
        # Collect metric
        await metrics_collector.collect_metric(mock_metric_point)
        
        # Test
        await metrics_collector._process_queue()
        
        # Assertions
        assert metrics_collector.queue.qsize() == 0
        assert len(metrics_collector.get_all_metric_series()) == 1
    
    @pytest.mark.asyncio
    async def test_process_queue_empty(self, metrics_collector):
        """Test queue processing with empty queue."""
        # Test
        await metrics_collector._process_queue()
        
        # Assertions
        assert metrics_collector.queue.qsize() == 0
        assert len(metrics_collector.get_all_metric_series()) == 0
    
    @pytest.mark.asyncio
    async def test_process_queue_batch(self, metrics_collector, mock_metric_point):
        """Test queue processing with batch."""
        # Collect multiple metrics
        for _ in range(5):
            await metrics_collector.collect_metric(mock_metric_point)
        
        # Test
        await metrics_collector._process_queue()
        
        # Assertions
        assert metrics_collector.queue.qsize() == 0
        series = metrics_collector.get_metric_series("test_metric")
        assert len(series.points) == 5
    
    @pytest.mark.asyncio
    async def test_process_queue_error(self, metrics_collector, mock_metric_point):
        """Test queue processing with error."""
        # Mock _add_point_to_series to raise exception
        with patch.object(metrics_collector, '_add_point_to_series', side_effect=Exception("Processing error")):
            # Collect metric
            await metrics_collector.collect_metric(mock_metric_point)
            
            # Test
            await metrics_collector._process_queue()
            
            # Assertions
            assert metrics_collector.queue.qsize() == 0
            assert len(metrics_collector.get_all_metric_series()) == 0
    
    @pytest.mark.asyncio
    async def test_add_point_to_series_new_series(self, metrics_collector, mock_metric_point):
        """Test adding point to new series."""
        # Test
        metrics_collector._add_point_to_series(mock_metric_point)
        
        # Assertions
        series = metrics_collector.get_metric_series("test_metric")
        assert series is not None
        assert len(series.points) == 1
        assert series.points[0] == mock_metric_point
    
    @pytest.mark.asyncio
    async def test_add_point_to_series_existing_series(self, metrics_collector, mock_metric_point):
        """Test adding point to existing series."""
        # Add first point
        metrics_collector._add_point_to_series(mock_metric_point)
        
        # Create second point
        second_point = MetricPoint(
            name="test_metric",
            value=100.0,
            metric_type=MetricType.GAUGE,
            labels={"environment": "test", "service": "test-service"},
            timestamp=datetime.now(),
            service="test-service",
            tenant_id="tenant-1"
        )
        
        # Test
        metrics_collector._add_point_to_series(second_point)
        
        # Assertions
        series = metrics_collector.get_metric_series("test_metric")
        assert len(series.points) == 2
        assert series.points[1] == second_point
    
    @pytest.mark.asyncio
    async def test_add_point_to_series_different_labels(self, metrics_collector, mock_metric_point):
        """Test adding point with different labels creates new series."""
        # Add first point
        metrics_collector._add_point_to_series(mock_metric_point)
        
        # Create second point with different labels
        second_point = MetricPoint(
            name="test_metric",
            value=100.0,
            metric_type=MetricType.GAUGE,
            labels={"environment": "production", "service": "test-service"},
            timestamp=datetime.now(),
            service="test-service",
            tenant_id="tenant-1"
        )
        
        # Test
        metrics_collector._add_point_to_series(second_point)
        
        # Assertions
        series_list = metrics_collector.get_all_metric_series()
        assert len(series_list) == 2
    
    @pytest.mark.asyncio
    async def test_add_point_to_series_different_service(self, metrics_collector, mock_metric_point):
        """Test adding point with different service creates new series."""
        # Add first point
        metrics_collector._add_point_to_series(mock_metric_point)
        
        # Create second point with different service
        second_point = MetricPoint(
            name="test_metric",
            value=100.0,
            metric_type=MetricType.GAUGE,
            labels={"environment": "test", "service": "test-service"},
            timestamp=datetime.now(),
            service="other-service",
            tenant_id="tenant-1"
        )
        
        # Test
        metrics_collector._add_point_to_series(second_point)
        
        # Assertions
        series_list = metrics_collector.get_all_metric_series()
        assert len(series_list) == 2
    
    @pytest.mark.asyncio
    async def test_add_point_to_series_different_tenant(self, metrics_collector, mock_metric_point):
        """Test adding point with different tenant creates new series."""
        # Add first point
        metrics_collector._add_point_to_series(mock_metric_point)
        
        # Create second point with different tenant
        second_point = MetricPoint(
            name="test_metric",
            value=100.0,
            metric_type=MetricType.GAUGE,
            labels={"environment": "test", "service": "test-service"},
            timestamp=datetime.now(),
            service="test-service",
            tenant_id="tenant-2"
        )
        
        # Test
        metrics_collector._add_point_to_series(second_point)
        
        # Assertions
        series_list = metrics_collector.get_all_metric_series()
        assert len(series_list) == 2
    
    @pytest.mark.asyncio
    async def test_get_series_key(self, metrics_collector, mock_metric_point):
        """Test series key generation."""
        # Test
        key = metrics_collector._get_series_key(mock_metric_point)
        
        # Assertions
        expected_key = "test_metric:test-service:tenant-1:environment=test,service=test-service"
        assert key == expected_key
    
    @pytest.mark.asyncio
    async def test_get_series_key_no_labels(self, metrics_collector):
        """Test series key generation with no labels."""
        # Create point without labels
        point = MetricPoint(
            name="test_metric",
            value=42.5,
            metric_type=MetricType.GAUGE,
            labels={},
            timestamp=datetime.now(),
            service="test-service",
            tenant_id="tenant-1"
        )
        
        # Test
        key = metrics_collector._get_series_key(point)
        
        # Assertions
        expected_key = "test_metric:test-service:tenant-1:"
        assert key == expected_key
    
    @pytest.mark.asyncio
    async def test_get_series_key_no_service(self, metrics_collector):
        """Test series key generation with no service."""
        # Create point without service
        point = MetricPoint(
            name="test_metric",
            value=42.5,
            metric_type=MetricType.GAUGE,
            labels={"environment": "test"},
            timestamp=datetime.now(),
            service=None,
            tenant_id="tenant-1"
        )
        
        # Test
        key = metrics_collector._get_series_key(point)
        
        # Assertions
        expected_key = "test_metric:None:tenant-1:environment=test"
        assert key == expected_key
    
    @pytest.mark.asyncio
    async def test_get_series_key_no_tenant(self, metrics_collector):
        """Test series key generation with no tenant."""
        # Create point without tenant
        point = MetricPoint(
            name="test_metric",
            value=42.5,
            metric_type=MetricType.GAUGE,
            labels={"environment": "test"},
            timestamp=datetime.now(),
            service="test-service",
            tenant_id=None
        )
        
        # Test
        key = metrics_collector._get_series_key(point)
        
        # Assertions
        expected_key = "test_metric:test-service:None:environment=test"
        assert key == expected_key
