"""
Unit tests for Metrics Collector.
"""

import pytest
import asyncio
import time
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
from typing import Dict, Any, List

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from service_metrics.app.ingestion.collector import MetricsCollector, MetricType, MetricPoint, MetricSeries


class TestMetricsCollector:
    """Test cases for MetricsCollector."""

    @pytest.fixture
    def collector(self):
        """Create MetricsCollector instance."""
        return MetricsCollector(max_series=1000, max_points_per_series=100)

    @pytest.fixture
    def sample_metric_point(self):
        """Create sample metric point."""
        return MetricPoint(
            name="test_metric",
            value=42.5,
            timestamp=datetime.now(),
            labels={"service": "test", "tenant_id": "tenant-1"}
        )

    @pytest.fixture
    def sample_metric_series(self):
        """Create sample metric series."""
        points = [
            MetricPoint(
                name="test_metric",
                value=42.5,
                timestamp=datetime.now(),
                labels={"service": "test", "tenant_id": "tenant-1"}
            ),
            MetricPoint(
                name="test_metric",
                value=43.0,
                timestamp=datetime.now(),
                labels={"service": "test", "tenant_id": "tenant-1"}
            )
        ]

        return MetricSeries(
            name="test_metric",
            metric_type=MetricType.GAUGE,
            labels={"service": "test", "tenant_id": "tenant-1"},
            points=points,
            service="test-service",
            tenant_id="tenant-1"
        )

    @pytest.mark.asyncio
    async def test_start_success(self, collector):
        """Test successful collector start."""
        await collector.start()

        assert collector.running is True
        assert collector.processing_task is not None

    @pytest.mark.asyncio
    async def test_stop_success(self, collector):
        """Test successful collector stop."""
        await collector.start()
        await collector.stop()

        assert collector.running is False
        assert collector.processing_task is None

    @pytest.mark.asyncio
    async def test_collect_metric_success(self, collector, sample_metric_point):
        """Test successful metric collection."""
        await collector.start()

        success = await collector.collect_metric(
            name="test_metric",
            value=42.5,
            metric_type=MetricType.GAUGE,
            labels={"service": "test", "tenant_id": "tenant-1"},
            service="test-service",
            tenant_id="tenant-1"
        )

        assert success is True

        # Wait for processing
        await asyncio.sleep(0.1)

        # Check if series was created
        series = collector.get_series("test_metric")
        assert len(series) == 1
        assert series[0].name == "test_metric"
        assert series[0].metric_type == MetricType.GAUGE
        assert len(series[0].points) == 1
        assert series[0].points[0].value == 42.5

    @pytest.mark.asyncio
    async def test_collect_metric_different_types(self, collector):
        """Test collecting different metric types."""
        await collector.start()

        # Test counter
        success = await collector.collect_metric(
            name="counter_metric",
            value=100,
            metric_type=MetricType.COUNTER,
            labels={"service": "test"},
            service="test-service"
        )
        assert success is True

        # Test gauge
        success = await collector.collect_metric(
            name="gauge_metric",
            value=50.5,
            metric_type=MetricType.GAUGE,
            labels={"service": "test"},
            service="test-service"
        )
        assert success is True

        # Test histogram
        success = await collector.collect_metric(
            name="histogram_metric",
            value=75.0,
            metric_type=MetricType.HISTOGRAM,
            labels={"service": "test"},
            service="test-service"
        )
        assert success is True

        # Wait for processing
        await asyncio.sleep(0.1)

        # Verify all series were created
        series = collector.get_series()
        assert len(series) == 3

        series_names = [s.name for s in series]
        assert "counter_metric" in series_names
        assert "gauge_metric" in series_names
        assert "histogram_metric" in series_names

    @pytest.mark.asyncio
    async def test_collect_metric_max_series_limit(self, collector):
        """Test metric collection with max series limit."""
        await collector.start()

        # Fill up to max series limit
        for i in range(1000):
            success = await collector.collect_metric(
                name=f"metric_{i}",
                value=1.0,
                metric_type=MetricType.GAUGE,
                labels={"service": "test"},
                service="test-service"
            )
            assert success is True

        # Wait for processing
        await asyncio.sleep(0.1)

        # Try to add one more series
        success = await collector.collect_metric(
            name="overflow_metric",
            value=1.0,
            metric_type=MetricType.GAUGE,
            labels={"service": "test"},
            service="test-service"
        )

        # Should still succeed but may drop oldest series
        assert success is True

    @pytest.mark.asyncio
    async def test_collect_metric_max_points_limit(self, collector):
        """Test metric collection with max points per series limit."""
        await collector.start()

        # Add points to exceed max_points_per_series
        for i in range(150):  # More than max_points_per_series (100)
            success = await collector.collect_metric(
                name="test_metric",
                value=float(i),
                metric_type=MetricType.GAUGE,
                labels={"service": "test"},
                service="test-service"
            )
            assert success is True

        # Wait for processing
        await asyncio.sleep(0.1)

        # Check that series exists but points are limited
        series = collector.get_series("test_metric")
        assert len(series) == 1
        assert len(series[0].points) <= 100  # Should be limited

    @pytest.mark.asyncio
    async def test_collect_metric_with_labels(self, collector):
        """Test metric collection with different labels."""
        await collector.start()

        # Collect metrics with different label combinations
        await collector.collect_metric(
            name="test_metric",
            value=1.0,
            metric_type=MetricType.GAUGE,
            labels={"service": "service1", "tenant_id": "tenant-1"},
            service="service1",
            tenant_id="tenant-1"
        )

        await collector.collect_metric(
            name="test_metric",
            value=2.0,
            metric_type=MetricType.GAUGE,
            labels={"service": "service2", "tenant_id": "tenant-1"},
            service="service2",
            tenant_id="tenant-1"
        )

        await collector.collect_metric(
            name="test_metric",
            value=3.0,
            metric_type=MetricType.GAUGE,
            labels={"service": "service1", "tenant_id": "tenant-2"},
            service="service1",
            tenant_id="tenant-2"
        )

        # Wait for processing
        await asyncio.sleep(0.1)

        # Should create separate series for each label combination
        series = collector.get_series("test_metric")
        assert len(series) == 3

        # Verify each series has correct labels
        for s in series:
            assert s.name == "test_metric"
            assert s.metric_type == MetricType.GAUGE
            assert len(s.points) == 1

    def test_get_series_by_name(self, collector, sample_metric_series):
        """Test getting series by name."""
        # Add series manually
        collector.series["test_metric"] = sample_metric_series

        series = collector.get_series("test_metric")
        assert len(series) == 1
        assert series[0].name == "test_metric"

    def test_get_series_by_service(self, collector, sample_metric_series):
        """Test getting series by service."""
        # Add series manually
        collector.series["test_metric"] = sample_metric_series

        series = collector.get_series_by_service("test-service")
        assert len(series) == 1
        assert series[0].service == "test-service"

    def test_get_series_by_tenant(self, collector, sample_metric_series):
        """Test getting series by tenant."""
        # Add series manually
        collector.series["test_metric"] = sample_metric_series

        series = collector.get_series_by_tenant("tenant-1")
        assert len(series) == 1
        assert series[0].tenant_id == "tenant-1"

    def test_get_collection_stats(self, collector, sample_metric_series):
        """Test getting collection statistics."""
        # Add series manually
        collector.series["test_metric"] = sample_metric_series
        collector.collection_stats["total_points"] = 2
        collector.collection_stats["total_series"] = 1

        stats = collector.get_collection_stats()

        assert "total_points" in stats
        assert "total_series" in stats
        assert "dropped_points" in stats
        assert "last_collection" in stats

        assert stats["total_points"] == 2
        assert stats["total_series"] == 1

    @pytest.mark.asyncio
    async def test_process_queue_success(self, collector):
        """Test successful queue processing."""
        await collector.start()

        # Add metric to queue
        await collector.collection_queue.put({
            "name": "test_metric",
            "value": 42.5,
            "metric_type": MetricType.GAUGE,
            "labels": {"service": "test"},
            "service": "test-service",
            "tenant_id": "tenant-1"
        })

        # Wait for processing
        await asyncio.sleep(0.1)

        # Check if series was created
        series = collector.get_series("test_metric")
        assert len(series) == 1
        assert series[0].points[0].value == 42.5

    @pytest.mark.asyncio
    async def test_process_queue_error_handling(self, collector):
        """Test queue processing error handling."""
        await collector.start()

        # Add invalid metric to queue
        await collector.collection_queue.put({
            "name": "test_metric",
            "value": "invalid_value",  # Invalid value type
            "metric_type": MetricType.GAUGE,
            "labels": {"service": "test"},
            "service": "test-service"
        })

        # Wait for processing
        await asyncio.sleep(0.1)

        # Should handle error gracefully
        assert collector.running is True

    def test_metric_point_creation(self, sample_metric_point):
        """Test MetricPoint creation."""
        assert sample_metric_point.name == "test_metric"
        assert sample_metric_point.value == 42.5
        assert isinstance(sample_metric_point.timestamp, datetime)
        assert sample_metric_point.labels == {"service": "test", "tenant_id": "tenant-1"}

    def test_metric_series_creation(self, sample_metric_series):
        """Test MetricSeries creation."""
        assert sample_metric_series.name == "test_metric"
        assert sample_metric_series.metric_type == MetricType.GAUGE
        assert sample_metric_series.labels == {"service": "test", "tenant_id": "tenant-1"}
        assert len(sample_metric_series.points) == 2
        assert sample_metric_series.service == "test-service"
        assert sample_metric_series.tenant_id == "tenant-1"

    def test_metric_type_enum(self):
        """Test MetricType enum values."""
        assert MetricType.COUNTER == "counter"
        assert MetricType.GAUGE == "gauge"
        assert MetricType.HISTOGRAM == "histogram"
        assert MetricType.SUMMARY == "summary"

    @pytest.mark.asyncio
    async def test_concurrent_metric_collection(self, collector):
        """Test concurrent metric collection."""
        await collector.start()

        # Create multiple concurrent collection tasks
        tasks = []
        for i in range(10):
            task = collector.collect_metric(
                name=f"concurrent_metric_{i}",
                value=float(i),
                metric_type=MetricType.GAUGE,
                labels={"service": "test"},
                service="test-service"
            )
            tasks.append(task)

        # Wait for all tasks to complete
        results = await asyncio.gather(*tasks)

        # All should succeed
        assert all(results)

        # Wait for processing
        await asyncio.sleep(0.1)

        # Check that all series were created
        series = collector.get_series()
        assert len(series) == 10

    @pytest.mark.asyncio
    async def test_series_key_generation(self, collector):
        """Test series key generation for different label combinations."""
        await collector.start()

        # Collect metrics with same name but different labels
        await collector.collect_metric(
            name="test_metric",
            value=1.0,
            metric_type=MetricType.GAUGE,
            labels={"service": "service1"},
            service="service1"
        )

        await collector.collect_metric(
            name="test_metric",
            value=2.0,
            metric_type=MetricType.GAUGE,
            labels={"service": "service2"},
            service="service2"
        )

        # Wait for processing
        await asyncio.sleep(0.1)

        # Should create separate series
        series = collector.get_series("test_metric")
        assert len(series) == 2

        # Verify each series has different labels
        services = [s.labels.get("service") for s in series]
        assert "service1" in services
        assert "service2" in services

    @pytest.mark.asyncio
    async def test_collection_stats_update(self, collector):
        """Test collection statistics update."""
        await collector.start()

        initial_stats = collector.get_collection_stats()
        initial_points = initial_stats["total_points"]

        # Collect some metrics
        for i in range(5):
            await collector.collect_metric(
                name=f"stats_metric_{i}",
                value=float(i),
                metric_type=MetricType.GAUGE,
                labels={"service": "test"},
                service="test-service"
            )

        # Wait for processing
        await asyncio.sleep(0.1)

        # Check stats were updated
        updated_stats = collector.get_collection_stats()
        assert updated_stats["total_points"] > initial_points
        assert updated_stats["total_series"] > 0
        assert updated_stats["last_collection"] is not None
