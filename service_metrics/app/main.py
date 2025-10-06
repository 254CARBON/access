"""
Metrics service for 254Carbon Access Layer.
"""

import asyncio
import json
import sys
import os
import time
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

# Add shared directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from fastapi import HTTPException, Query, Body
from shared.base_service import BaseService
from shared.logging import get_logger
from shared.errors import AccessLayerException
from shared.observability import get_observability_manager, observe_function, observe_operation

from .ingestion.collector import MetricsCollector, MetricType
from .ingestion.aggregator import MetricsAggregator
from .exporters.prometheus import PrometheusExporter


class MetricsService(BaseService):
    """Metrics service implementation."""
    
    def __init__(self):
        super().__init__("metrics", 8012)
        
        # Initialize observability
        self.observability = get_observability_manager(
            "metrics",
            log_level=self.config.log_level,
            otel_exporter=self.config.otel_exporter,
            enable_console=self.config.enable_console_tracing
        )
        
        # Initialize components
        self.collector = MetricsCollector(
            max_series=self.config.max_metric_series,
            max_points_per_series=self.config.max_points_per_series
        )
        self.aggregator = MetricsAggregator(
            window_size_seconds=self.config.aggregation_window_seconds
        )
        self.exporter = PrometheusExporter()
        
        self._setup_metrics_routes()
    
    def _setup_metrics_routes(self):
        """Set up metrics-specific routes."""
        
        @self.app.get("/")
        async def root():
            """Root endpoint."""
            return {
                "service": "metrics",
                "message": "254Carbon Access Layer - Metrics Service",
                "version": "1.0.0",
                "capabilities": ["collection", "aggregation", "export"]
            }
        
        @self.app.post("/metrics/track")
        @observe_function("metrics_track")
        async def track_metric(metric_data: Dict[str, Any] = Body(...)):
            """Track a metric."""
            start_time = time.time()
            
            try:
                # Set context for logging
                tenant_id = metric_data.get("tenant_id")
                service = metric_data.get("service")
                if tenant_id:
                    self.observability.trace_request(tenant_id=tenant_id)
                # Validate required fields
                name = metric_data.get("name")
                value = metric_data.get("value")
                metric_type = metric_data.get("type", "gauge")
                
                if not name or value is None:
                    raise HTTPException(
                        status_code=400,
                        detail="Missing required fields: name, value"
                    )
                
                # Validate metric type
                try:
                    metric_type_enum = MetricType(metric_type)
                except ValueError:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid metric type: {metric_type}"
                    )
                
                # Extract optional fields
                labels = metric_data.get("labels", {})
                service = metric_data.get("service")
                tenant_id = metric_data.get("tenant_id")
                
                # Collect metric
                success = await self.collector.collect_metric(
                    name=name,
                    value=value,
                    metric_type=metric_type_enum,
                    labels=labels,
                    service=service,
                    tenant_id=tenant_id
                )
                
                if success:
                    # Log successful metric tracking
                    self.observability.log_business_event(
                        "metric_tracked",
                        metric_name=name,
                        metric_type=metric_type,
                        service=service,
                        tenant_id=tenant_id
                    )
                    return {"success": True, "message": "Metric tracked successfully"}
                else:
                    # Log failed metric tracking
                    self.observability.log_error(
                        "metric_tracking_failed",
                        f"Failed to track metric {name}",
                        metric_name=name,
                        service=service,
                        tenant_id=tenant_id
                    )
                    raise HTTPException(
                        status_code=500,
                        detail="Failed to track metric"
                    )
                    
            except HTTPException:
                raise
            except Exception as e:
                self.logger.error("Error tracking metric", error=str(e))
                raise HTTPException(status_code=500, detail="Internal server error")
        
        @self.app.post("/metrics/track/batch")
        async def track_metrics_batch(metrics_data: List[Dict[str, Any]] = Body(...)):
            """Track multiple metrics in batch."""
            try:
                results = []
                
                for metric_data in metrics_data:
                    try:
                        # Validate required fields
                        name = metric_data.get("name")
                        value = metric_data.get("value")
                        metric_type = metric_data.get("type", "gauge")
                        
                        if not name or value is None:
                            results.append({
                                "name": name,
                                "success": False,
                                "error": "Missing required fields: name, value"
                            })
                            continue
                        
                        # Validate metric type
                        try:
                            metric_type_enum = MetricType(metric_type)
                        except ValueError:
                            results.append({
                                "name": name,
                                "success": False,
                                "error": f"Invalid metric type: {metric_type}"
                            })
                            continue
                        
                        # Extract optional fields
                        labels = metric_data.get("labels", {})
                        service = metric_data.get("service")
                        tenant_id = metric_data.get("tenant_id")
                        
                        # Collect metric
                        success = await self.collector.collect_metric(
                            name=name,
                            value=value,
                            metric_type=metric_type_enum,
                            labels=labels,
                            service=service,
                            tenant_id=tenant_id
                        )
                        
                        results.append({
                            "name": name,
                            "success": success,
                            "error": None if success else "Failed to track metric"
                        })
                        
                    except Exception as e:
                        results.append({
                            "name": metric_data.get("name", "unknown"),
                            "success": False,
                            "error": str(e)
                        })
                
                return {
                    "success": True,
                    "results": results,
                    "total": len(metrics_data),
                    "successful": len([r for r in results if r["success"]])
                }
                
            except Exception as e:
                self.logger.error("Error tracking metrics batch", error=str(e))
                raise HTTPException(status_code=500, detail="Internal server error")
        
        @self.app.get("/metrics")
        async def export_metrics(
            format: str = Query("prometheus", description="Export format"),
            service: Optional[str] = Query(None, description="Filter by service"),
            tenant_id: Optional[str] = Query(None, description="Filter by tenant"),
            aggregated: bool = Query(False, description="Export aggregated metrics")
        ):
            """Export metrics in Prometheus format."""
            try:
                if format != "prometheus":
                    raise HTTPException(
                        status_code=400,
                        detail="Only 'prometheus' format is supported"
                    )
                
                # Get metrics
                if aggregated:
                    # Get aggregated metrics
                    end_time = datetime.now()
                    start_time = end_time - timedelta(hours=24)  # Last 24 hours
                    
                    aggregated_metrics = self.aggregator.get_aggregated_metrics(
                        service=service,
                        tenant_id=tenant_id,
                        start_time=start_time,
                        end_time=end_time
                    )
                    
                    exported = self.exporter.export_aggregated_metrics(aggregated_metrics)
                else:
                    # Get raw metrics
                    series_list = self.collector.get_series()
                    
                    if service:
                        series_list = self.collector.get_series_by_service(service)
                    elif tenant_id:
                        series_list = self.collector.get_series_by_tenant(tenant_id)
                    
                    exported = self.exporter.export_metrics(series_list)
                
                return {
                    "format": format,
                    "data": exported,
                    "timestamp": datetime.now().isoformat()
                }
                
            except HTTPException:
                raise
            except Exception as e:
                self.logger.error("Error exporting metrics", error=str(e))
                raise HTTPException(status_code=500, detail="Internal server error")
        
        @self.app.get("/metrics/series")
        async def get_metric_series(
            name: Optional[str] = Query(None, description="Filter by metric name"),
            service: Optional[str] = Query(None, description="Filter by service"),
            tenant_id: Optional[str] = Query(None, description="Filter by tenant")
        ):
            """Get metric series information."""
            try:
                series_list = self.collector.get_series(name)
                
                if service:
                    series_list = self.collector.get_series_by_service(service)
                elif tenant_id:
                    series_list = self.collector.get_series_by_tenant(tenant_id)
                
                # Convert to response format
                series_info = []
                for series in series_list:
                    series_info.append({
                        "name": series.name,
                        "type": series.metric_type.value,
                        "labels": series.labels,
                        "service": series.service,
                        "tenant_id": series.tenant_id,
                        "point_count": len(series.points),
                        "latest_value": series.points[-1].value if series.points else None,
                        "latest_timestamp": series.points[-1].timestamp.isoformat() if series.points else None
                    })
                
                return {
                    "series": series_info,
                    "total": len(series_info),
                    "timestamp": datetime.now().isoformat()
                }
                
            except Exception as e:
                self.logger.error("Error getting metric series", error=str(e))
                raise HTTPException(status_code=500, detail="Internal server error")
        
        @self.app.get("/metrics/stats")
        async def get_metrics_stats():
            """Get metrics service statistics."""
            try:
                collector_stats = self.collector.get_collection_stats()
                aggregator_stats = self.aggregator.get_aggregation_stats()
                exporter_stats = self.exporter.get_export_stats()
                
                return {
                    "collector": collector_stats,
                    "aggregator": aggregator_stats,
                    "exporter": exporter_stats,
                    "timestamp": datetime.now().isoformat()
                }
                
            except Exception as e:
                self.logger.error("Error getting metrics stats", error=str(e))
                raise HTTPException(status_code=500, detail="Internal server error")
        
        @self.app.get("/metrics/trends/{metric_name}")
        async def get_metric_trends(
            metric_name: str,
            hours: int = Query(24, description="Time period in hours")
        ):
            """Get trend analysis for a metric."""
            try:
                trends = self.aggregator.get_metric_trends(metric_name, hours)
                return trends
                
            except Exception as e:
                self.logger.error("Error getting metric trends", error=str(e))
                raise HTTPException(status_code=500, detail="Internal server error")
    
    async def _check_dependencies(self):
        """Check metrics service dependencies."""
        return {
            "collector": "ok" if self.collector.running else "error",
            "aggregator": "ok" if self.aggregator.running else "error"
        }
    
    async def start(self):
        """Start metrics service components."""
        await self.collector.start()
        await self.aggregator.start()
        
        self.logger.info("Metrics service components started")
    
    async def stop(self):
        """Stop metrics service components."""
        await self.collector.stop()
        await self.aggregator.stop()
        
        self.logger.info("Metrics service components stopped")


def create_app():
    """Create metrics service application."""
    service = MetricsService()
    return service.app


if __name__ == "__main__":
    service = MetricsService()
    service.run()