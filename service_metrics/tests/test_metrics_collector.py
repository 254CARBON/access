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
        return MetricsCollector(max_series=1000, max_points_per_series=100)
    
    @pytest.mark.asyncio
    async def test_start(self, metrics_collector):
        """Test starting the collector."""
        # Test
        await metrics_collector.start()
        
        # Assertions
        assert metrics_collector.running is True
        assert metrics_collector.processing_task is not None
    
    @pytest.mark.asyncio
    async def test_stop(self, metrics_collector):
        """Test stopping the collector."""
        # Start collector
        await metrics_collector.start()
        
        # Test
        await metrics_collector.stop()
        
        # Assertions
        assert metrics_collector.running is False
        # Note: processing_task may still exist but be cancelled
    
    @pytest.mark.asyncio
    async def test_collect_metric_success(self, metrics_collector):
        """Test successful metric collection."""
        # Test
        result = await metrics_collector.collect_metric(
            name="test_metric",
            value=42.5,
            metric_type=MetricType.GAUGE,
            labels={"environment": "test"},
            service="test-service",
            tenant_id="tenant-1"
        )
        
        # Assertions
        assert result is True
        assert metrics_collector.collection_queue.qsize() == 1
    
    @pytest.mark.asyncio
    async def test_collect_metric_queue_full(self, metrics_collector):
        """Test metric collection with full queue."""
        # Fill queue
        for _ in range(10000):
            await metrics_collector.collect_metric(
                name="test_metric",
                value=42.5,
                metric_type=MetricType.GAUGE
            )
        
        # Test
        result = await metrics_collector.collect_metric(
            name="test_metric",
            value=42.5,
            metric_type=MetricType.GAUGE
        )
        
        # Assertions
        assert result is False
        assert metrics_collector.collection_queue.qsize() == 10000
    
    @pytest.mark.asyncio
    async def test_collect_counter(self, metrics_collector):
        """Test counter metric collection."""
        # Test
        result = await metrics_collector.collect_counter(
            name="test_counter",
            value=10,
            labels={"environment": "test"}
        )
        
        # Assertions
        assert result is True
        assert metrics_collector.collection_queue.qsize() == 1
    
    @pytest.mark.asyncio
    async def test_collect_gauge(self, metrics_collector):
        """Test gauge metric collection."""
        # Test
        result = await metrics_collector.collect_gauge(
            name="test_gauge",
            value=42.5,
            labels={"environment": "test"}
        )
        
        # Assertions
        assert result is True
        assert metrics_collector.collection_queue.qsize() == 1
    
    @pytest.mark.asyncio
    async def test_collect_histogram(self, metrics_collector):
        """Test histogram metric collection."""
        # Test
        result = await metrics_collector.collect_histogram(
            name="test_histogram",
            value=100.0,
            labels={"environment": "test"}
        )
        
        # Assertions
        assert result is True
        assert metrics_collector.collection_queue.qsize() == 1
    
    @pytest.mark.asyncio
    async def test_get_metric_series(self, metrics_collector):
        """Test metric series retrieval."""
        # Start collector and collect metric
        await metrics_collector.start()
        await metrics_collector.collect_metric(
            name="test_metric",
            value=42.5,
            metric_type=MetricType.GAUGE,
            labels={"environment": "test"}
        )
        
        # Wait for processing
        await asyncio.sleep(0.1)
        
        # Test
        series_list = metrics_collector.get_series("test_metric")
        
        # Assertions
        assert len(series_list) == 1
        series = series_list[0]
        assert series.name == "test_metric"
        assert len(series.points) == 1
        assert series.points[0].value == 42.5
        
        # Cleanup
        await metrics_collector.stop()
    
    @pytest.mark.asyncio
    async def test_get_metric_series_not_found(self, metrics_collector):
        """Test metric series retrieval for non-existent series."""
        # Test
        series_list = metrics_collector.get_series("nonexistent_metric")
        
        # Assertions
        assert len(series_list) == 0
    
    @pytest.mark.asyncio
    async def test_get_all_metric_series(self, metrics_collector):
        """Test retrieval of all metric series."""
        # Start collector and collect metrics
        await metrics_collector.start()
        await metrics_collector.collect_metric("metric1", 10, MetricType.COUNTER)
        await metrics_collector.collect_metric("metric2", 20, MetricType.GAUGE)
        
        # Wait for processing
        await asyncio.sleep(0.1)
        
        # Test
        series_list = metrics_collector.get_series()
        
        # Assertions
        assert len(series_list) == 2
        
        # Cleanup
        await metrics_collector.stop()
    
    @pytest.mark.asyncio
    async def test_get_collector_stats(self, metrics_collector):
        """Test collector statistics retrieval."""
        # Test
        stats = metrics_collector.get_collection_stats()
        
        # Assertions
        assert "total_points" in stats
        assert "total_series" in stats
        assert "dropped_points" in stats
        assert "last_collection" in stats
        assert "active_series" in stats
        assert "queue_size" in stats
        assert "running" in stats
    
    @pytest.mark.asyncio
    async def test_clear_all_metrics(self, metrics_collector):
        """Test clearing all metrics."""
        # Start collector and collect metrics
        await metrics_collector.start()
        await metrics_collector.collect_metric("metric1", 10, MetricType.COUNTER)
        
        # Wait for processing
        await asyncio.sleep(0.1)
        
        # Test
        cleaned_points = await metrics_collector.cleanup_old_metrics(max_age_hours=0)
        
        # Assertions
        assert cleaned_points > 0
        series_list = metrics_collector.get_series()
        assert len(series_list) == 1
        assert len(series_list[0].points) == 0  # Points are removed but series remains
        
        # Cleanup
        await metrics_collector.stop()
    
    @pytest.mark.asyncio
    async def test_process_queue_success(self, metrics_collector):
        """Test successful queue processing."""
        # Start collector
        await metrics_collector.start()
        
        # Collect metric
        await metrics_collector.collect_metric(
            name="test_metric",
            value=42.5,
            metric_type=MetricType.GAUGE
        )
        
        # Wait for processing
        await asyncio.sleep(0.1)
        
        # Assertions
        assert metrics_collector.collection_queue.qsize() == 0
        series_list = metrics_collector.get_series("test_metric")
        assert len(series_list) == 1
        series = series_list[0]
        assert len(series.points) == 1
        
        # Cleanup
        await metrics_collector.stop()
    
    def test_metric_point_creation(self):
        """Test MetricPoint creation."""
        # Test
        point = MetricPoint(
            name="test_metric",
            value=42.5,
            metric_type=MetricType.GAUGE,
            labels={"environment": "test"},
            service="test-service",
            tenant_id="tenant-1"
        )
        
        # Assertions
        assert point.name == "test_metric"
        assert point.value == 42.5
        assert point.metric_type == MetricType.GAUGE
        assert point.labels == {"environment": "test"}
        assert point.service == "test-service"
        assert point.tenant_id == "tenant-1"
    
    def test_metric_series_creation(self):
        """Test MetricSeries creation."""
        # Test
        series = MetricSeries(
            name="test_metric",
            metric_type=MetricType.GAUGE,
            labels={"environment": "test"},
            service="test-service",
            tenant_id="tenant-1"
        )
        
        # Assertions
        assert series.name == "test_metric"
        assert series.metric_type == MetricType.GAUGE
        assert series.labels == {"environment": "test"}
        assert series.service == "test-service"
        assert series.tenant_id == "tenant-1"
        assert len(series.points) == 0
    
    def test_metric_type_enum(self):
        """Test MetricType enum values."""
        # Assertions
        assert MetricType.COUNTER == "counter"
        assert MetricType.GAUGE == "gauge"
        assert MetricType.HISTOGRAM == "histogram"
        assert MetricType.SUMMARY == "summary"