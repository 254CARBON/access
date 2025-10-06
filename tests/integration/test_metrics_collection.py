"""
Integration tests for Metrics service flow.
"""

import pytest
import httpx
import json
import time
from unittest.mock import patch, AsyncMock

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from shared.test_helpers import create_mock_jwt_token, create_mock_user


class TestMetricsCollection:
    """Integration tests for Metrics service flow."""
    
    @pytest.fixture
    def metrics_url(self):
        """Metrics service URL."""
        return "http://localhost:8004"
    
    @pytest.fixture
    def mock_user(self):
        """Create mock user."""
        return create_mock_user(
            user_id="test-user-1",
            tenant_id="tenant-1",
            roles=["user", "analyst"]
        )
    
    @pytest.fixture
    def mock_jwt_token(self, mock_user):
        """Create mock JWT token."""
        return create_mock_jwt_token(
            user_id=mock_user["user_id"],
            tenant_id=mock_user["tenant_id"],
            roles=mock_user["roles"],
            expires_in=3600
        )
    
    @pytest.mark.asyncio
    async def test_metrics_collection_flow(self, metrics_url, mock_jwt_token):
        """Test metrics collection flow."""
        async with httpx.AsyncClient() as client:
            headers = {"Authorization": f"Bearer {mock_jwt_token}"}
            
            # Track single metric
            metric_data = {
                "name": "test_metric",
                "value": 42.5,
                "metric_type": "gauge",
                "labels": {"environment": "test", "service": "test-service"},
                "service": "test-service",
                "tenant_id": "tenant-1"
            }
            
            track_response = await client.post(
                f"{metrics_url}/metrics/track",
                headers=headers,
                json=metric_data
            )
            assert track_response.status_code == 200
            result = track_response.json()
            assert result["tracked"] is True
            
            # Wait for processing
            await asyncio.sleep(0.1)
            
            # Get metric series
            series_response = await client.get(
                f"{metrics_url}/metrics/series",
                headers=headers
            )
            assert series_response.status_code == 200
            series_data = series_response.json()
            assert "series" in series_data
            assert len(series_data["series"]) > 0
            
            # Find our metric
            test_series = None
            for series in series_data["series"]:
                if series["name"] == "test_metric":
                    test_series = series
                    break
            
            assert test_series is not None
            assert test_series["metric_type"] == "gauge"
            assert len(test_series["points"]) > 0
            assert test_series["points"][-1]["value"] == 42.5
    
    @pytest.mark.asyncio
    async def test_metrics_batch_collection(self, metrics_url, mock_jwt_token):
        """Test metrics batch collection."""
        async with httpx.AsyncClient() as client:
            headers = {"Authorization": f"Bearer {mock_jwt_token}"}
            
            # Track multiple metrics in batch
            batch_data = {
                "metrics": [
                    {
                        "name": "batch_metric_1",
                        "value": 10,
                        "metric_type": "counter",
                        "labels": {"type": "request"},
                        "service": "test-service",
                        "tenant_id": "tenant-1"
                    },
                    {
                        "name": "batch_metric_2",
                        "value": 25.5,
                        "metric_type": "gauge",
                        "labels": {"type": "response_time"},
                        "service": "test-service",
                        "tenant_id": "tenant-1"
                    },
                    {
                        "name": "batch_metric_3",
                        "value": 100,
                        "metric_type": "histogram",
                        "labels": {"type": "latency"},
                        "service": "test-service",
                        "tenant_id": "tenant-1"
                    }
                ]
            }
            
            batch_response = await client.post(
                f"{metrics_url}/metrics/track/batch",
                headers=headers,
                json=batch_data
            )
            assert batch_response.status_code == 200
            result = batch_response.json()
            assert result["tracked"] is True
            assert result["count"] == 3
            
            # Wait for processing
            await asyncio.sleep(0.1)
            
            # Get metric series
            series_response = await client.get(
                f"{metrics_url}/metrics/series",
                headers=headers
            )
            assert series_response.status_code == 200
            series_data = series_response.json()
            
            # Check all metrics were collected
            metric_names = [series["name"] for series in series_data["series"]]
            assert "batch_metric_1" in metric_names
            assert "batch_metric_2" in metric_names
            assert "batch_metric_3" in metric_names
    
    @pytest.mark.asyncio
    async def test_metrics_prometheus_export(self, metrics_url, mock_jwt_token):
        """Test metrics Prometheus export."""
        async with httpx.AsyncClient() as client:
            headers = {"Authorization": f"Bearer {mock_jwt_token}"}
            
            # Track some metrics first
            metric_data = {
                "name": "prometheus_test_metric",
                "value": 99.9,
                "metric_type": "gauge",
                "labels": {"environment": "test"},
                "service": "test-service",
                "tenant_id": "tenant-1"
            }
            
            await client.post(
                f"{metrics_url}/metrics/track",
                headers=headers,
                json=metric_data
            )
            
            # Wait for processing
            await asyncio.sleep(0.1)
            
            # Export metrics in Prometheus format
            export_response = await client.get(
                f"{metrics_url}/metrics",
                headers=headers
            )
            assert export_response.status_code == 200
            assert "text/plain" in export_response.headers["content-type"]
            
            # Check Prometheus format
            prometheus_data = export_response.text
            assert "prometheus_test_metric" in prometheus_data
            assert "99.9" in prometheus_data
            assert "environment=test" in prometheus_data
    
    @pytest.mark.asyncio
    async def test_metrics_trends(self, metrics_url, mock_jwt_token):
        """Test metrics trends."""
        async with httpx.AsyncClient() as client:
            headers = {"Authorization": f"Bearer {mock_jwt_token}"}
            
            # Track multiple values over time
            base_time = time.time()
            for i in range(5):
                metric_data = {
                    "name": "trend_metric",
                    "value": 10 + i * 5,  # 10, 15, 20, 25, 30
                    "metric_type": "gauge",
                    "labels": {"test": "trend"},
                    "service": "test-service",
                    "tenant_id": "tenant-1"
                }
                
                await client.post(
                    f"{metrics_url}/metrics/track",
                    headers=headers,
                    json=metric_data
                )
                
                # Small delay between measurements
                await asyncio.sleep(0.05)
            
            # Wait for processing
            await asyncio.sleep(0.1)
            
            # Get trends
            trends_response = await client.get(
                f"{metrics_url}/metrics/trends/trend_metric",
                headers=headers
            )
            assert trends_response.status_code == 200
            trends_data = trends_response.json()
            assert "trends" in trends_data
            assert len(trends_data["trends"]) > 0
    
    @pytest.mark.asyncio
    async def test_metrics_filtering(self, metrics_url, mock_jwt_token):
        """Test metrics filtering."""
        async with httpx.AsyncClient() as client:
            headers = {"Authorization": f"Bearer {mock_jwt_token}"}
            
            # Track metrics with different labels
            metrics = [
                {
                    "name": "filter_test_metric",
                    "value": 1,
                    "metric_type": "gauge",
                    "labels": {"environment": "test", "service": "service1"},
                    "service": "service1",
                    "tenant_id": "tenant-1"
                },
                {
                    "name": "filter_test_metric",
                    "value": 2,
                    "metric_type": "gauge",
                    "labels": {"environment": "prod", "service": "service2"},
                    "service": "service2",
                    "tenant_id": "tenant-1"
                },
                {
                    "name": "filter_test_metric",
                    "value": 3,
                    "metric_type": "gauge",
                    "labels": {"environment": "test", "service": "service3"},
                    "service": "service3",
                    "tenant_id": "tenant-2"
                }
            ]
            
            for metric in metrics:
                await client.post(
                    f"{metrics_url}/metrics/track",
                    headers=headers,
                    json=metric
                )
            
            # Wait for processing
            await asyncio.sleep(0.1)
            
            # Filter by service
            filter_response = await client.get(
                f"{metrics_url}/metrics/series?service=service1",
                headers=headers
            )
            assert filter_response.status_code == 200
            filter_data = filter_response.json()
            assert len(filter_data["series"]) > 0
            
            # Filter by tenant
            filter_response = await client.get(
                f"{metrics_url}/metrics/series?tenant_id=tenant-1",
                headers=headers
            )
            assert filter_response.status_code == 200
            filter_data = filter_response.json()
            assert len(filter_data["series"]) > 0
    
    @pytest.mark.asyncio
    async def test_metrics_aggregation(self, metrics_url, mock_jwt_token):
        """Test metrics aggregation."""
        async with httpx.AsyncClient() as client:
            headers = {"Authorization": f"Bearer {mock_jwt_token}"}
            
            # Track histogram metrics
            histogram_values = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
            for value in histogram_values:
                metric_data = {
                    "name": "histogram_test",
                    "value": value,
                    "metric_type": "histogram",
                    "labels": {"test": "aggregation"},
                    "service": "test-service",
                    "tenant_id": "tenant-1"
                }
                
                await client.post(
                    f"{metrics_url}/metrics/track",
                    headers=headers,
                    json=metric_data
                )
            
            # Wait for processing
            await asyncio.sleep(0.1)
            
            # Get aggregated metrics
            series_response = await client.get(
                f"{metrics_url}/metrics/series",
                headers=headers
            )
            assert series_response.status_code == 200
            series_data = series_response.json()
            
            # Find histogram series
            histogram_series = None
            for series in series_data["series"]:
                if series["name"] == "histogram_test":
                    histogram_series = series
                    break
            
            assert histogram_series is not None
            assert histogram_series["metric_type"] == "histogram"
            assert len(histogram_series["points"]) == len(histogram_values)
    
    @pytest.mark.asyncio
    async def test_metrics_error_handling(self, metrics_url, mock_jwt_token):
        """Test metrics error handling."""
        async with httpx.AsyncClient() as client:
            headers = {"Authorization": f"Bearer {mock_jwt_token}"}
            
            # Test invalid metric data
            invalid_metric = {
                "name": "invalid_metric",
                "value": "not_a_number",  # Invalid value
                "metric_type": "gauge"
            }
            
            track_response = await client.post(
                f"{metrics_url}/metrics/track",
                headers=headers,
                json=invalid_metric
            )
            assert track_response.status_code == 400
            
            # Test missing required fields
            incomplete_metric = {
                "name": "incomplete_metric"
                # Missing value and metric_type
            }
            
            track_response = await client.post(
                f"{metrics_url}/metrics/track",
                headers=headers,
                json=incomplete_metric
            )
            assert track_response.status_code == 400
            
            # Test invalid metric type
            invalid_type_metric = {
                "name": "invalid_type_metric",
                "value": 42,
                "metric_type": "invalid_type"
            }
            
            track_response = await client.post(
                f"{metrics_url}/metrics/track",
                headers=headers,
                json=invalid_type_metric
            )
            assert track_response.status_code == 400
    
    @pytest.mark.asyncio
    async def test_metrics_performance(self, metrics_url, mock_jwt_token):
        """Test metrics performance."""
        async with httpx.AsyncClient() as client:
            headers = {"Authorization": f"Bearer {mock_jwt_token}"}
            
            # Track many metrics quickly
            start_time = time.time()
            
            tasks = []
            for i in range(100):
                metric_data = {
                    "name": f"perf_metric_{i}",
                    "value": i,
                    "metric_type": "gauge",
                    "labels": {"test": "performance"},
                    "service": "test-service",
                    "tenant_id": "tenant-1"
                }
                
                task = client.post(
                    f"{metrics_url}/metrics/track",
                    headers=headers,
                    json=metric_data
                )
                tasks.append(task)
            
            # Wait for all requests to complete
            responses = await asyncio.gather(*tasks)
            
            end_time = time.time()
            duration = end_time - start_time
            
            # All requests should succeed
            success_count = sum(1 for r in responses if r.status_code == 200)
            assert success_count == 100
            
            # Should complete within reasonable time
            assert duration < 10.0  # 10 seconds for 100 requests
    
    @pytest.mark.asyncio
    async def test_metrics_concurrent_collection(self, metrics_url, mock_jwt_token):
        """Test metrics concurrent collection."""
        async with httpx.AsyncClient() as client:
            headers = {"Authorization": f"Bearer {mock_jwt_token}"}
            
            # Concurrent metric collection
            async def collect_metric(metric_id):
                metric_data = {
                    "name": f"concurrent_metric_{metric_id}",
                    "value": metric_id * 10,
                    "metric_type": "gauge",
                    "labels": {"test": "concurrent"},
                    "service": "test-service",
                    "tenant_id": "tenant-1"
                }
                
                response = await client.post(
                    f"{metrics_url}/metrics/track",
                    headers=headers,
                    json=metric_data
                )
                return response.status_code == 200
            
            # Collect 50 metrics concurrently
            tasks = [collect_metric(i) for i in range(50)]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # All should succeed
            success_count = sum(1 for r in results if r is True)
            assert success_count == 50
    
    @pytest.mark.asyncio
    async def test_metrics_retention(self, metrics_url, mock_jwt_token):
        """Test metrics retention policies."""
        async with httpx.AsyncClient() as client:
            headers = {"Authorization": f"Bearer {mock_jwt_token}"}
            
            # Track metric
            metric_data = {
                "name": "retention_test_metric",
                "value": 42,
                "metric_type": "gauge",
                "labels": {"test": "retention"},
                "service": "test-service",
                "tenant_id": "tenant-1"
            }
            
            track_response = await client.post(
                f"{metrics_url}/metrics/track",
                headers=headers,
                json=metric_data
            )
            assert track_response.status_code == 200
            
            # Wait for processing
            await asyncio.sleep(0.1)
            
            # Get metric series
            series_response = await client.get(
                f"{metrics_url}/metrics/series",
                headers=headers
            )
            assert series_response.status_code == 200
            series_data = series_response.json()
            
            # Find our metric
            retention_series = None
            for series in series_data["series"]:
                if series["name"] == "retention_test_metric":
                    retention_series = series
                    break
            
            assert retention_series is not None
            assert len(retention_series["points"]) > 0
            
            # Test cleanup (if implemented)
            # This would test automatic cleanup of old metrics
            # Implementation depends on retention policies
    
    @pytest.mark.asyncio
    async def test_metrics_statistics(self, metrics_url, mock_jwt_token):
        """Test metrics statistics."""
        async with httpx.AsyncClient() as client:
            headers = {"Authorization": f"Bearer {mock_jwt_token}"}
            
            # Track some metrics
            for i in range(10):
                metric_data = {
                    "name": f"stats_metric_{i}",
                    "value": i * 10,
                    "metric_type": "gauge",
                    "labels": {"test": "statistics"},
                    "service": "test-service",
                    "tenant_id": "tenant-1"
                }
                
                await client.post(
                    f"{metrics_url}/metrics/track",
                    headers=headers,
                    json=metric_data
                )
            
            # Wait for processing
            await asyncio.sleep(0.1)
            
            # Get statistics
            stats_response = await client.get(
                f"{metrics_url}/metrics/stats",
                headers=headers
            )
            assert stats_response.status_code == 200
            stats_data = stats_response.json()
            
            # Check statistics structure
            assert "total_series" in stats_data
            assert "total_points" in stats_data
            assert "services" in stats_data
            assert "tenants" in stats_data
            assert "metric_types" in stats_data
            
            # Verify counts
            assert stats_data["total_series"] > 0
            assert stats_data["total_points"] > 0