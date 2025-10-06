"""
Unit tests for Metrics main service.
"""

import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from fastapi import FastAPI

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from service_metrics.app.main import MetricsService, create_app
from service_metrics.app.ingestion.collector import MetricType


class TestMetricsService:
    """Test cases for MetricsService."""

    @pytest.fixture
    def metrics_service(self):
        """Create MetricsService instance."""
        return MetricsService()

    @pytest.fixture
    def app(self):
        """Create FastAPI app instance."""
        return create_app()

    @pytest.fixture
    def client(self, app):
        """Create test client."""
        return TestClient(app)

    @pytest.fixture
    def mock_metric_data(self):
        """Mock metric data."""
        return {
            "name": "test_metric",
            "value": 42.5,
            "type": "gauge",
            "labels": {"service": "test", "tenant_id": "tenant-1"},
            "service": "test-service",
            "tenant_id": "tenant-1"
        }

    @pytest.fixture
    def mock_batch_metrics(self):
        """Mock batch metrics data."""
        return [
            {
                "name": "metric_1",
                "value": 10.0,
                "type": "counter",
                "labels": {"service": "test"},
                "service": "test-service"
            },
            {
                "name": "metric_2",
                "value": 20.0,
                "type": "gauge",
                "labels": {"service": "test"},
                "service": "test-service"
            },
            {
                "name": "metric_3",
                "value": 30.0,
                "type": "histogram",
                "labels": {"service": "test"},
                "service": "test-service"
            }
        ]

    def test_root_endpoint(self, client):
        """Test root endpoint."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "metrics"
        assert data["message"] == "254Carbon Access Layer - Metrics Service"
        assert "collection" in data["capabilities"]
        assert "aggregation" in data["capabilities"]
        assert "export" in data["capabilities"]

    def test_health_endpoint(self, client):
        """Test health endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "metrics"
        assert data["status"] == "ok"

    @patch('service_metrics.app.main.MetricsService._check_dependencies')
    def test_health_with_dependencies(self, mock_check_deps, client):
        """Test health endpoint with dependency checks."""
        mock_check_deps.return_value = {
            "collector": "ok",
            "aggregator": "ok"
        }

        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["dependencies"]["collector"] == "ok"
        assert data["dependencies"]["aggregator"] == "ok"

    def test_service_initialization(self, metrics_service):
        """Test service initialization."""
        assert metrics_service.name == "metrics"
        assert metrics_service.port == 8012
        assert metrics_service.collector is not None
        assert metrics_service.aggregator is not None
        assert metrics_service.exporter is not None

    def test_observability_setup(self, metrics_service):
        """Test observability setup."""
        assert metrics_service.observability is not None
        assert hasattr(metrics_service.observability, 'log_request')
        assert hasattr(metrics_service.observability, 'log_error')
        assert hasattr(metrics_service.observability, 'log_business_event')

    @patch('service_metrics.app.main.MetricsCollector.collect_metric')
    def test_track_metric_success(self, mock_collect, client, mock_metric_data):
        """Test successful metric tracking."""
        mock_collect.return_value = True

        response = client.post("/metrics/track", json=mock_metric_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "Metric tracked successfully"

        # Verify collector was called
        mock_collect.assert_called_once()

    @patch('service_metrics.app.main.MetricsCollector.collect_metric')
    def test_track_metric_failure(self, mock_collect, client, mock_metric_data):
        """Test metric tracking failure."""
        mock_collect.return_value = False

        response = client.post("/metrics/track", json=mock_metric_data)

        assert response.status_code == 500
        data = response.json()
        assert data["detail"] == "Failed to track metric"

    def test_track_metric_missing_fields(self, client):
        """Test metric tracking with missing required fields."""
        invalid_data = {
            "name": "test_metric",
            # Missing value field
            "type": "gauge"
        }

        response = client.post("/metrics/track", json=invalid_data)

        assert response.status_code == 400
        data = response.json()
        assert "Missing required fields" in data["detail"]

    def test_track_metric_invalid_type(self, client):
        """Test metric tracking with invalid metric type."""
        invalid_data = {
            "name": "test_metric",
            "value": 42.5,
            "type": "invalid_type"
        }

        response = client.post("/metrics/track", json=invalid_data)

        assert response.status_code == 400
        data = response.json()
        assert "Invalid metric type" in data["detail"]

    @patch('service_metrics.app.main.MetricsCollector.collect_metric')
    def test_track_metrics_batch_success(self, mock_collect, client, mock_batch_metrics):
        """Test successful batch metric tracking."""
        mock_collect.return_value = True

        response = client.post("/metrics/track/batch", json=mock_batch_metrics)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["total"] == 3
        assert data["successful"] == 3

        # Verify collector was called for each metric
        assert mock_collect.call_count == 3

    @patch('service_metrics.app.main.MetricsCollector.collect_metric')
    def test_track_metrics_batch_partial_failure(self, mock_collect, client, mock_batch_metrics):
        """Test batch metric tracking with partial failures."""
        # Mock collector to fail for some metrics
        def mock_collect_side_effect(*args, **kwargs):
            metric_name = kwargs.get('name', args[0] if args else '')
            return metric_name != 'metric_2'  # Fail for metric_2

        mock_collect.side_effect = mock_collect_side_effect

        response = client.post("/metrics/track/batch", json=mock_batch_metrics)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["total"] == 3
        assert data["successful"] == 2

    def test_track_metrics_batch_invalid_data(self, client):
        """Test batch metric tracking with invalid data."""
        invalid_batch = [
            {
                "name": "valid_metric",
                "value": 10.0,
                "type": "gauge"
            },
            {
                "name": "invalid_metric",
                # Missing value field
                "type": "gauge"
            }
        ]

        response = client.post("/metrics/track/batch", json=invalid_batch)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["total"] == 2
        assert data["successful"] == 1

    @patch('service_metrics.app.main.MetricsCollector.get_series')
    @patch('service_metrics.app.main.PrometheusExporter.export_metrics')
    def test_export_metrics_success(self, mock_export, mock_get_series, client):
        """Test successful metrics export."""
        # Mock series data
        mock_series = [MagicMock()]
        mock_get_series.return_value = mock_series
        mock_export.return_value = "# HELP test_metric Test metric\n# TYPE test_metric gauge\ntest_metric 42.5"

        response = client.get("/metrics?format=prometheus")

        assert response.status_code == 200
        data = response.json()
        assert data["format"] == "prometheus"
        assert "data" in data
        assert "timestamp" in data

        # Verify exporter was called
        mock_export.assert_called_once()

    def test_export_metrics_invalid_format(self, client):
        """Test metrics export with invalid format."""
        response = client.get("/metrics?format=invalid")

        assert response.status_code == 400
        data = response.json()
        assert "Only 'prometheus' format is supported" in data["detail"]

    @patch('service_metrics.app.main.MetricsAggregator.get_aggregated_metrics')
    @patch('service_metrics.app.main.PrometheusExporter.export_aggregated_metrics')
    def test_export_metrics_aggregated(self, mock_export_agg, mock_get_agg, client):
        """Test aggregated metrics export."""
        # Mock aggregated metrics
        mock_agg_metrics = [MagicMock()]
        mock_get_agg.return_value = mock_agg_metrics
        mock_export_agg.return_value = "# HELP test_metric_avg Test metric average\ntest_metric_avg 42.5"

        response = client.get("/metrics?format=prometheus&aggregated=true")

        assert response.status_code == 200
        data = response.json()
        assert data["format"] == "prometheus"
        assert "data" in data

        # Verify aggregator was called
        mock_get_agg.assert_called_once()
        mock_export_agg.assert_called_once()

    @patch('service_metrics.app.main.MetricsCollector.get_series')
    def test_get_metric_series_success(self, mock_get_series, client):
        """Test successful metric series retrieval."""
        # Mock series data
        mock_series = [
            MagicMock(
                name="test_metric",
                metric_type=MetricType.GAUGE,
                labels={"service": "test"},
                service="test-service",
                tenant_id="tenant-1",
                points=[MagicMock(value=42.5, timestamp="2024-01-01T00:00:00Z")]
            )
        ]
        mock_get_series.return_value = mock_series

        response = client.get("/metrics/series")

        assert response.status_code == 200
        data = response.json()
        assert "series" in data
        assert "total" in data
        assert "timestamp" in data
        assert data["total"] == 1
        assert len(data["series"]) == 1

    @patch('service_metrics.app.main.MetricsCollector.get_series_by_service')
    def test_get_metric_series_by_service(self, mock_get_series, client):
        """Test getting metric series by service."""
        mock_series = []
        mock_get_series.return_value = mock_series

        response = client.get("/metrics/series?service=test-service")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0

        # Verify service filter was applied
        mock_get_series.assert_called_once()

    @patch('service_metrics.app.main.MetricsCollector.get_series_by_tenant')
    def test_get_metric_series_by_tenant(self, mock_get_series, client):
        """Test getting metric series by tenant."""
        mock_series = []
        mock_get_series.return_value = mock_series

        response = client.get("/metrics/series?tenant_id=tenant-1")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0

        # Verify tenant filter was applied
        mock_get_series.assert_called_once()

    @patch('service_metrics.app.main.MetricsCollector.get_collection_stats')
    @patch('service_metrics.app.main.MetricsAggregator.get_aggregation_stats')
    @patch('service_metrics.app.main.PrometheusExporter.get_export_stats')
    def test_get_metrics_stats_success(self, mock_export_stats, mock_agg_stats, mock_collector_stats, client):
        """Test successful metrics statistics retrieval."""
        # Mock stats data
        mock_collector_stats.return_value = {
            "total_points": 1000,
            "total_series": 50,
            "dropped_points": 10
        }

        mock_agg_stats.return_value = {
            "total_windows": 24,
            "aggregated_series": 45
        }

        mock_export_stats.return_value = {
            "total_exports": 100,
            "last_export": "2024-01-01T00:00:00Z"
        }

        response = client.get("/metrics/stats")

        assert response.status_code == 200
        data = response.json()
        assert "collector" in data
        assert "aggregator" in data
        assert "exporter" in data
        assert "timestamp" in data

        assert data["collector"]["total_points"] == 1000
        assert data["aggregator"]["total_windows"] == 24
        assert data["exporter"]["total_exports"] == 100

    @patch('service_metrics.app.main.MetricsAggregator.get_metric_trends')
    def test_get_metric_trends_success(self, mock_get_trends, client):
        """Test successful metric trends retrieval."""
        mock_trends = {
            "metric_name": "test_metric",
            "trend": "increasing",
            "change_percent": 15.5,
            "data_points": [
                {"timestamp": "2024-01-01T00:00:00Z", "value": 40.0},
                {"timestamp": "2024-01-01T01:00:00Z", "value": 42.0},
                {"timestamp": "2024-01-01T02:00:00Z", "value": 44.0}
            ]
        }
        mock_get_trends.return_value = mock_trends

        response = client.get("/metrics/trends/test_metric?hours=24")

        assert response.status_code == 200
        data = response.json()
        assert data["metric_name"] == "test_metric"
        assert data["trend"] == "increasing"
        assert data["change_percent"] == 15.5
        assert len(data["data_points"]) == 3

    @patch('service_metrics.app.main.MetricsAggregator.get_metric_trends')
    def test_get_metric_trends_error(self, mock_get_trends, client):
        """Test metric trends retrieval with error."""
        mock_get_trends.side_effect = Exception("Trend analysis failed")

        response = client.get("/metrics/trends/nonexistent_metric?hours=24")

        assert response.status_code == 500
        data = response.json()
        assert data["detail"] == "Internal server error"

    async def test_check_dependencies(self, metrics_service):
        """Test dependency checks."""
        # Mock collector and aggregator running state
        with patch.object(metrics_service.collector, 'running', True), \
             patch.object(metrics_service.aggregator, 'running', True):

            dependencies = await metrics_service._check_dependencies()

            assert dependencies["collector"] == "ok"
            assert dependencies["aggregator"] == "ok"

    async def test_check_dependencies_collector_error(self, metrics_service):
        """Test dependency checks with collector error."""
        # Mock collector not running
        with patch.object(metrics_service.collector, 'running', False), \
             patch.object(metrics_service.aggregator, 'running', True):

            dependencies = await metrics_service._check_dependencies()

            assert dependencies["collector"] == "error"
            assert dependencies["aggregator"] == "ok"

    @patch('service_metrics.app.main.MetricsCollector.start')
    @patch('service_metrics.app.main.MetricsAggregator.start')
    async def test_start_service(self, mock_agg_start, mock_collector_start, metrics_service):
        """Test service start."""
        await metrics_service.start()

        # Verify components started
        mock_collector_start.assert_called_once()
        mock_agg_start.assert_called_once()

    @patch('service_metrics.app.main.MetricsCollector.stop')
    @patch('service_metrics.app.main.MetricsAggregator.stop')
    async def test_stop_service(self, mock_agg_stop, mock_collector_stop, metrics_service):
        """Test service stop."""
        await metrics_service.stop()

        # Verify components stopped
        mock_collector_stop.assert_called_once()
        mock_agg_stop.assert_called_once()

    def test_service_configuration(self, metrics_service):
        """Test service configuration."""
        assert metrics_service.config.max_metric_series > 0
        assert metrics_service.config.max_points_per_series > 0
        assert metrics_service.config.aggregation_window_seconds > 0

    @patch('service_metrics.app.main.MetricsCollector.collect_metric')
    def test_different_metric_types(self, mock_collect, client):
        """Test tracking different metric types."""
        mock_collect.return_value = True

        metric_types = ["counter", "gauge", "histogram", "summary"]

        for metric_type in metric_types:
            metric_data = {
                "name": f"test_{metric_type}",
                "value": 42.5,
                "type": metric_type,
                "labels": {"service": "test"},
                "service": "test-service"
            }

            response = client.post("/metrics/track", json=metric_data)
            assert response.status_code == 200

        # Verify collector was called for each type
        assert mock_collect.call_count == len(metric_types)

    def test_metric_validation_edge_cases(self, client):
        """Test metric validation with edge cases."""
        # Test with zero value
        zero_metric = {
            "name": "zero_metric",
            "value": 0,
            "type": "gauge",
            "labels": {"service": "test"},
            "service": "test-service"
        }

        response = client.post("/metrics/track", json=zero_metric)
        assert response.status_code == 200

        # Test with negative value
        negative_metric = {
            "name": "negative_metric",
            "value": -10.5,
            "type": "gauge",
            "labels": {"service": "test"},
            "service": "test-service"
        }

        response = client.post("/metrics/track", json=negative_metric)
        assert response.status_code == 200

        # Test with very large value
        large_metric = {
            "name": "large_metric",
            "value": 1e10,
            "type": "gauge",
            "labels": {"service": "test"},
            "service": "test-service"
        }

        response = client.post("/metrics/track", json=large_metric)
        assert response.status_code == 200

    @patch('service_metrics.app.main.MetricsCollector.collect_metric')
    def test_metric_labels_handling(self, mock_collect, client):
        """Test metric labels handling."""
        mock_collect.return_value = True

        # Test with empty labels
        empty_labels_metric = {
            "name": "empty_labels_metric",
            "value": 42.5,
            "type": "gauge",
            "labels": {},
            "service": "test-service"
        }

        response = client.post("/metrics/track", json=empty_labels_metric)
        assert response.status_code == 200

        # Test with None labels
        none_labels_metric = {
            "name": "none_labels_metric",
            "value": 42.5,
            "type": "gauge",
            "service": "test-service"
        }

        response = client.post("/metrics/track", json=none_labels_metric)
        assert response.status_code == 200

        # Test with complex labels
        complex_labels_metric = {
            "name": "complex_labels_metric",
            "value": 42.5,
            "type": "gauge",
            "labels": {
                "service": "test-service",
                "tenant_id": "tenant-1",
                "environment": "production",
                "version": "1.0.0"
            },
            "service": "test-service",
            "tenant_id": "tenant-1"
        }

        response = client.post("/metrics/track", json=complex_labels_metric)
        assert response.status_code == 200