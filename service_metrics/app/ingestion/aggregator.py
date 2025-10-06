"""
Time-window aggregation for Metrics Service.
"""

import asyncio
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict
import sys
import os

# Add shared directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from shared.logging import get_logger
from .collector import MetricPoint, MetricSeries, MetricType


@dataclass
class AggregatedMetric:
    """Aggregated metric data."""
    name: str
    metric_type: MetricType
    labels: Dict[str, str]
    value: float
    count: int
    min_value: float
    max_value: float
    sum_value: float
    timestamp: datetime
    window_start: datetime
    window_end: datetime
    service: Optional[str] = None
    tenant_id: Optional[str] = None


class MetricsAggregator:
    """Aggregates metrics over time windows."""
    
    def __init__(self, window_size_seconds: int = 60):
        self.window_size_seconds = window_size_seconds
        self.logger = get_logger("metrics.aggregator")
        
        # Aggregation storage
        self.aggregated_metrics: Dict[str, List[AggregatedMetric]] = {}
        self.current_window: Dict[str, Dict[str, Any]] = defaultdict(dict)
        
        # Aggregation task
        self.aggregation_task: Optional[asyncio.Task] = None
        self.running = False
    
    async def start(self):
        """Start the aggregator."""
        self.running = True
        self.aggregation_task = asyncio.create_task(self._aggregation_loop())
        self.logger.info("Metrics aggregator started", window_size=self.window_size_seconds)
    
    async def stop(self):
        """Stop the aggregator."""
        self.running = False
        if self.aggregation_task:
            self.aggregation_task.cancel()
            try:
                await self.aggregation_task
            except asyncio.CancelledError:
                pass
        
        self.logger.info("Metrics aggregator stopped")
    
    async def aggregate_series(self, series: MetricSeries) -> List[AggregatedMetric]:
        """Aggregate a metric series over time windows."""
        if not series.points:
            return []
        
        # Group points by time window
        window_groups = defaultdict(list)
        
        for point in series.points:
            window_start = self._get_window_start(point.timestamp)
            window_key = f"{window_start.isoformat()}"
            window_groups[window_key].append(point)
        
        # Aggregate each window
        aggregated = []
        for window_key, points in window_groups.items():
            if points:
                aggregated_metric = self._aggregate_points(
                    series, points, window_key
                )
                if aggregated_metric:
                    aggregated.append(aggregated_metric)
        
        return aggregated
    
    def _get_window_start(self, timestamp: datetime) -> datetime:
        """Get the start of the time window for a timestamp."""
        # Round down to the nearest window boundary
        seconds_since_epoch = int(timestamp.timestamp())
        window_start_seconds = (seconds_since_epoch // self.window_size_seconds) * self.window_size_seconds
        return datetime.fromtimestamp(window_start_seconds)
    
    def _aggregate_points(
        self,
        series: MetricSeries,
        points: List[MetricPoint],
        window_key: str
    ) -> Optional[AggregatedMetric]:
        """Aggregate a list of points into a single metric."""
        if not points:
            return None
        
        # Sort points by timestamp
        points.sort(key=lambda p: p.timestamp)
        
        # Calculate aggregation
        values = [p.value for p in points]
        min_value = min(values)
        max_value = max(values)
        sum_value = sum(values)
        count = len(values)
        
        # Calculate aggregated value based on metric type
        if series.metric_type == MetricType.COUNTER:
            # For counters, use the last value (cumulative)
            aggregated_value = values[-1]
        elif series.metric_type == MetricType.GAUGE:
            # For gauges, use the last value
            aggregated_value = values[-1]
        elif series.metric_type == MetricType.HISTOGRAM:
            # For histograms, use the average
            aggregated_value = sum_value / count
        else:
            # Default to average
            aggregated_value = sum_value / count
        
        # Parse window start time
        window_start = datetime.fromisoformat(window_key)
        window_end = window_start + timedelta(seconds=self.window_size_seconds)
        
        return AggregatedMetric(
            name=series.name,
            metric_type=series.metric_type,
            labels=series.labels,
            value=aggregated_value,
            count=count,
            min_value=min_value,
            max_value=max_value,
            sum_value=sum_value,
            timestamp=points[-1].timestamp,
            window_start=window_start,
            window_end=window_end,
            service=series.service,
            tenant_id=series.tenant_id
        )
    
    async def _aggregation_loop(self):
        """Main aggregation loop."""
        while self.running:
            try:
                # Wait for window boundary
                await asyncio.sleep(self.window_size_seconds)
                
                # Perform aggregation
                await self._perform_aggregation()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error("Error in aggregation loop", error=str(e))
                await asyncio.sleep(1)
    
    async def _perform_aggregation(self):
        """Perform aggregation for the current window."""
        try:
            current_time = datetime.now()
            window_start = self._get_window_start(current_time)
            
            self.logger.debug("Performing aggregation", window_start=window_start.isoformat())
            
            # This would typically be called by the collector
            # For now, we'll just log that aggregation would happen
            
        except Exception as e:
            self.logger.error("Error performing aggregation", error=str(e))
    
    def get_aggregated_metrics(
        self,
        name: Optional[str] = None,
        service: Optional[str] = None,
        tenant_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[AggregatedMetric]:
        """Get aggregated metrics with filters."""
        all_metrics = []
        
        for series_name, metrics in self.aggregated_metrics.items():
            if name and series_name != name:
                continue
            
            for metric in metrics:
                # Apply filters
                if service and metric.service != service:
                    continue
                
                if tenant_id and metric.tenant_id != tenant_id:
                    continue
                
                if start_time and metric.window_start < start_time:
                    continue
                
                if end_time and metric.window_end > end_time:
                    continue
                
                all_metrics.append(metric)
        
        # Sort by timestamp
        all_metrics.sort(key=lambda m: m.timestamp)
        
        return all_metrics
    
    def get_aggregation_stats(self) -> Dict[str, Any]:
        """Get aggregation statistics."""
        total_metrics = sum(len(metrics) for metrics in self.aggregated_metrics.values())
        
        return {
            "window_size_seconds": self.window_size_seconds,
            "total_aggregated_series": len(self.aggregated_metrics),
            "total_aggregated_metrics": total_metrics,
            "running": self.running
        }
    
    def get_metric_trends(
        self,
        name: str,
        hours: int = 24
    ) -> Dict[str, Any]:
        """Get trend analysis for a metric."""
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=hours)
        
        metrics = self.get_aggregated_metrics(
            name=name,
            start_time=start_time,
            end_time=end_time
        )
        
        if not metrics:
            return {"error": "No metrics found"}
        
        # Calculate trends
        values = [m.value for m in metrics]
        
        if len(values) < 2:
            return {"error": "Insufficient data for trend analysis"}
        
        # Simple linear trend
        first_value = values[0]
        last_value = values[-1]
        trend_direction = "increasing" if last_value > first_value else "decreasing"
        trend_magnitude = abs(last_value - first_value) / first_value if first_value != 0 else 0
        
        return {
            "metric_name": name,
            "period_hours": hours,
            "data_points": len(metrics),
            "first_value": first_value,
            "last_value": last_value,
            "min_value": min(values),
            "max_value": max(values),
            "avg_value": sum(values) / len(values),
            "trend_direction": trend_direction,
            "trend_magnitude": trend_magnitude,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat()
        }
    
    async def cleanup_old_aggregations(self, max_age_hours: int = 168):  # 7 days
        """Clean up old aggregated metrics."""
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        cleaned_count = 0
        
        for series_name, metrics in self.aggregated_metrics.items():
            original_count = len(metrics)
            self.aggregated_metrics[series_name] = [
                m for m in metrics if m.timestamp > cutoff_time
            ]
            cleaned_count += original_count - len(self.aggregated_metrics[series_name])
        
        if cleaned_count > 0:
            self.logger.info("Cleaned up old aggregations", metrics_removed=cleaned_count)
        
        return cleaned_count
