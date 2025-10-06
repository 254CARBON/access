"""
Metrics collection logic for Metrics Service.
"""

import asyncio
import time
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import sys
import os

# Add shared directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from shared.logging import get_logger
from shared.errors import AccessLayerException


class MetricType(str, Enum):
    """Metric types."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


@dataclass
class MetricPoint:
    """A single metric data point."""
    name: str
    value: Union[int, float]
    metric_type: MetricType
    labels: Dict[str, str] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    service: Optional[str] = None
    tenant_id: Optional[str] = None


@dataclass
class MetricSeries:
    """A series of metric points."""
    name: str
    metric_type: MetricType
    labels: Dict[str, str]
    points: List[MetricPoint] = field(default_factory=list)
    service: Optional[str] = None
    tenant_id: Optional[str] = None


class MetricsCollector:
    """Collects and manages metrics."""
    
    def __init__(self, max_series: int = 10000, max_points_per_series: int = 1000):
        self.max_series = max_series
        self.max_points_per_series = max_points_per_series
        self.logger = get_logger("metrics.collector")
        
        # Storage
        self.series: Dict[str, MetricSeries] = {}
        self.collection_stats = {
            "total_points": 0,
            "total_series": 0,
            "dropped_points": 0,
            "last_collection": None
        }
        
        # Collection queue
        self.collection_queue = asyncio.Queue(maxsize=10000)
        self.processing_task: Optional[asyncio.Task] = None
        self.running = False
    
    async def start(self):
        """Start the metrics collector."""
        self.running = True
        self.processing_task = asyncio.create_task(self._process_queue())
        self.logger.info("Metrics collector started")
    
    async def stop(self):
        """Stop the metrics collector."""
        self.running = False
        if self.processing_task:
            self.processing_task.cancel()
            try:
                await self.processing_task
            except asyncio.CancelledError:
                pass
        
        self.logger.info("Metrics collector stopped")
    
    async def collect_metric(
        self,
        name: str,
        value: Union[int, float],
        metric_type: MetricType,
        labels: Optional[Dict[str, str]] = None,
        service: Optional[str] = None,
        tenant_id: Optional[str] = None
    ) -> bool:
        """Collect a metric point."""
        try:
            # Create metric point
            point = MetricPoint(
                name=name,
                value=value,
                metric_type=metric_type,
                labels=labels or {},
                service=service,
                tenant_id=tenant_id
            )
            
            # Add to queue
            try:
                self.collection_queue.put_nowait(point)
                return True
            except asyncio.QueueFull:
                self.logger.warning("Collection queue full, dropping metric", name=name)
                self.collection_stats["dropped_points"] += 1
                return False
                
        except Exception as e:
            self.logger.error("Error collecting metric", name=name, error=str(e))
            return False
    
    async def collect_counter(
        self,
        name: str,
        value: Union[int, float],
        labels: Optional[Dict[str, str]] = None,
        service: Optional[str] = None,
        tenant_id: Optional[str] = None
    ) -> bool:
        """Collect a counter metric."""
        return await self.collect_metric(
            name, value, MetricType.COUNTER, labels, service, tenant_id
        )
    
    async def collect_gauge(
        self,
        name: str,
        value: Union[int, float],
        labels: Optional[Dict[str, str]] = None,
        service: Optional[str] = None,
        tenant_id: Optional[str] = None
    ) -> bool:
        """Collect a gauge metric."""
        return await self.collect_metric(
            name, value, MetricType.GAUGE, labels, service, tenant_id
        )
    
    async def collect_histogram(
        self,
        name: str,
        value: Union[int, float],
        labels: Optional[Dict[str, str]] = None,
        service: Optional[str] = None,
        tenant_id: Optional[str] = None
    ) -> bool:
        """Collect a histogram metric."""
        return await self.collect_metric(
            name, value, MetricType.HISTOGRAM, labels, service, tenant_id
        )
    
    async def _process_queue(self):
        """Process the collection queue."""
        while self.running:
            try:
                # Get metric point from queue
                point = await asyncio.wait_for(self.collection_queue.get(), timeout=1.0)
                
                # Process the point
                await self._process_metric_point(point)
                
                # Mark task as done
                self.collection_queue.task_done()
                
            except asyncio.TimeoutError:
                # No metrics to process, continue
                continue
            except Exception as e:
                self.logger.error("Error processing metric queue", error=str(e))
                await asyncio.sleep(0.1)
    
    async def _process_metric_point(self, point: MetricPoint):
        """Process a single metric point."""
        try:
            # Generate series key
            series_key = self._generate_series_key(point)
            
            # Get or create series
            if series_key not in self.series:
                if len(self.series) >= self.max_series:
                    # Remove oldest series
                    await self._evict_oldest_series()
                
                self.series[series_key] = MetricSeries(
                    name=point.name,
                    metric_type=point.metric_type,
                    labels=point.labels,
                    service=point.service,
                    tenant_id=point.tenant_id
                )
                self.collection_stats["total_series"] += 1
            
            # Add point to series
            series = self.series[series_key]
            
            if len(series.points) >= self.max_points_per_series:
                # Remove oldest point
                series.points.pop(0)
            
            series.points.append(point)
            self.collection_stats["total_points"] += 1
            self.collection_stats["last_collection"] = datetime.now()
            
            self.logger.debug(
                "Metric point processed",
                name=point.name,
                value=point.value,
                series_key=series_key
            )
            
        except Exception as e:
            self.logger.error("Error processing metric point", error=str(e))
    
    def _generate_series_key(self, point: MetricPoint) -> str:
        """Generate a unique key for a metric series."""
        # Sort labels for consistent key generation
        sorted_labels = sorted(point.labels.items())
        label_str = ",".join(f"{k}={v}" for k, v in sorted_labels)
        
        return f"{point.name}:{point.metric_type.value}:{point.service or 'unknown'}:{point.tenant_id or 'default'}:{label_str}"
    
    async def _evict_oldest_series(self):
        """Evict the oldest series to make room for new ones."""
        if not self.series:
            return
        
        # Find series with oldest last point
        oldest_series = None
        oldest_time = datetime.now()
        
        for series in self.series.values():
            if series.points:
                last_point_time = series.points[-1].timestamp
                if last_point_time < oldest_time:
                    oldest_time = last_point_time
                    oldest_series = series
        
        if oldest_series:
            # Remove the oldest series
            for key, series in self.series.items():
                if series == oldest_series:
                    del self.series[key]
                    self.collection_stats["total_series"] -= 1
                    self.logger.debug("Evicted oldest series", name=series.name)
                    break
    
    def get_series(self, name: Optional[str] = None) -> List[MetricSeries]:
        """Get metric series."""
        if name:
            return [series for series in self.series.values() if series.name == name]
        return list(self.series.values())
    
    def get_series_by_service(self, service: str) -> List[MetricSeries]:
        """Get metric series for a specific service."""
        return [series for series in self.series.values() if series.service == service]
    
    def get_series_by_tenant(self, tenant_id: str) -> List[MetricSeries]:
        """Get metric series for a specific tenant."""
        return [series for series in self.series.values() if series.tenant_id == tenant_id]
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """Get collection statistics."""
        return {
            **self.collection_stats,
            "active_series": len(self.series),
            "queue_size": self.collection_queue.qsize(),
            "running": self.running
        }
    
    def get_metric_summary(self) -> Dict[str, Any]:
        """Get summary of all metrics."""
        summary = {
            "total_series": len(self.series),
            "total_points": sum(len(series.points) for series in self.series.values()),
            "services": {},
            "tenants": {},
            "metric_types": {}
        }
        
        # Count by service
        for series in self.series.values():
            service = series.service or "unknown"
            summary["services"][service] = summary["services"].get(service, 0) + 1
        
        # Count by tenant
        for series in self.series.values():
            tenant = series.tenant_id or "default"
            summary["tenants"][tenant] = summary["tenants"].get(tenant, 0) + 1
        
        # Count by metric type
        for series in self.series.values():
            metric_type = series.metric_type.value
            summary["metric_types"][metric_type] = summary["metric_types"].get(metric_type, 0) + 1
        
        return summary
    
    async def cleanup_old_metrics(self, max_age_hours: int = 24):
        """Clean up old metric points."""
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        cleaned_points = 0
        
        for series in self.series.values():
            original_count = len(series.points)
            series.points = [p for p in series.points if p.timestamp > cutoff_time]
            cleaned_points += original_count - len(series.points)
        
        if cleaned_points > 0:
            self.logger.info("Cleaned up old metrics", points_removed=cleaned_points)
        
        return cleaned_points
