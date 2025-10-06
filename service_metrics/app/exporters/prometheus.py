"""
Prometheus exporter for Metrics Service.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import sys
import os

# Add shared directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from shared.logging import get_logger
from ..ingestion.collector import MetricSeries, MetricType, MetricPoint
from ..ingestion.aggregator import AggregatedMetric


class PrometheusExporter:
    """Exports metrics in Prometheus format."""
    
    def __init__(self):
        self.logger = get_logger("metrics.exporter.prometheus")
    
    def export_metrics(self, series_list: List[MetricSeries]) -> str:
        """Export metrics in Prometheus format."""
        try:
            lines = []
            
            for series in series_list:
                if not series.points:
                    continue
                
                # Get the latest point for each series
                latest_point = series.points[-1]
                
                # Format metric name
                metric_name = self._sanitize_metric_name(series.name)
                
                # Format labels
                labels = self._format_labels(series.labels, series.service, series.tenant_id)
                
                # Format value based on metric type
                if series.metric_type == MetricType.COUNTER:
                    # For counters, use the last value
                    value = latest_point.value
                elif series.metric_type == MetricType.GAUGE:
                    # For gauges, use the last value
                    value = latest_point.value
                elif series.metric_type == MetricType.HISTOGRAM:
                    # For histograms, calculate basic stats
                    values = [p.value for p in series.points]
                    if values:
                        # Export count, sum, and a sample
                        count = len(values)
                        sum_value = sum(values)
                        avg_value = sum_value / count
                        
                        # Export count
                        lines.append(f"{metric_name}_count{{{labels}}} {count}")
                        # Export sum
                        lines.append(f"{metric_name}_sum{{{labels}}} {sum_value}")
                        # Export average as a gauge
                        lines.append(f"{metric_name}_avg{{{labels}}} {avg_value}")
                        
                        # Export min/max if available
                        if len(values) > 1:
                            lines.append(f"{metric_name}_min{{{labels}}} {min(values)}")
                            lines.append(f"{metric_name}_max{{{labels}}} {max(values)}")
                        
                        continue
                else:
                    # Default to gauge behavior
                    value = latest_point.value
                
                # Add metric line
                lines.append(f"{metric_name}{{{labels}}} {value}")
            
            # Add timestamp comment
            timestamp = int(datetime.now().timestamp() * 1000)
            lines.insert(0, f"# Generated at {datetime.now().isoformat()}")
            lines.insert(1, f"# Timestamp: {timestamp}")
            
            return "\n".join(lines)
            
        except Exception as e:
            self.logger.error("Error exporting metrics", error=str(e))
            return f"# Error exporting metrics: {str(e)}"
    
    def export_aggregated_metrics(self, aggregated_metrics: List[AggregatedMetric]) -> str:
        """Export aggregated metrics in Prometheus format."""
        try:
            lines = []
            
            for metric in aggregated_metrics:
                # Format metric name
                metric_name = self._sanitize_metric_name(metric.name)
                
                # Format labels
                labels = self._format_labels(metric.labels, metric.service, metric.tenant_id)
                
                # Add window information to labels
                window_labels = f"{labels},window_start=\"{metric.window_start.isoformat()}\",window_end=\"{metric.window_end.isoformat()}\""
                
                # Export based on metric type
                if metric.metric_type == MetricType.COUNTER:
                    lines.append(f"{metric_name}{{{window_labels}}} {metric.value}")
                elif metric.metric_type == MetricType.GAUGE:
                    lines.append(f"{metric_name}{{{window_labels}}} {metric.value}")
                elif metric.metric_type == MetricType.HISTOGRAM:
                    # Export histogram components
                    lines.append(f"{metric_name}_count{{{window_labels}}} {metric.count}")
                    lines.append(f"{metric_name}_sum{{{window_labels}}} {metric.sum_value}")
                    lines.append(f"{metric_name}_avg{{{window_labels}}} {metric.value}")
                    lines.append(f"{metric_name}_min{{{window_labels}}} {metric.min_value}")
                    lines.append(f"{metric_name}_max{{{window_labels}}} {metric.max_value}")
                else:
                    lines.append(f"{metric_name}{{{window_labels}}} {metric.value}")
            
            # Add timestamp comment
            timestamp = int(datetime.now().timestamp() * 1000)
            lines.insert(0, f"# Generated at {datetime.now().isoformat()}")
            lines.insert(1, f"# Timestamp: {timestamp}")
            lines.insert(2, f"# Aggregated metrics: {len(aggregated_metrics)}")
            
            return "\n".join(lines)
            
        except Exception as e:
            self.logger.error("Error exporting aggregated metrics", error=str(e))
            return f"# Error exporting aggregated metrics: {str(e)}"
    
    def export_service_metrics(self, service_name: str, series_list: List[MetricSeries]) -> str:
        """Export metrics for a specific service."""
        service_series = [s for s in series_list if s.service == service_name]
        return self.export_metrics(service_series)
    
    def export_tenant_metrics(self, tenant_id: str, series_list: List[MetricSeries]) -> str:
        """Export metrics for a specific tenant."""
        tenant_series = [s for s in series_list if s.tenant_id == tenant_id]
        return self.export_metrics(tenant_series)
    
    def _sanitize_metric_name(self, name: str) -> str:
        """Sanitize metric name for Prometheus format."""
        # Replace invalid characters with underscores
        sanitized = ""
        for char in name:
            if char.isalnum() or char == '_':
                sanitized += char
            else:
                sanitized += '_'
        
        # Ensure it starts with a letter
        if sanitized and not sanitized[0].isalpha():
            sanitized = "metric_" + sanitized
        
        return sanitized or "unknown_metric"
    
    def _format_labels(self, labels: Dict[str, str], service: Optional[str], tenant_id: Optional[str]) -> str:
        """Format labels for Prometheus format."""
        formatted_labels = []
        
        # Add service label
        if service:
            formatted_labels.append(f'service="{self._sanitize_label_value(service)}"')
        
        # Add tenant label
        if tenant_id:
            formatted_labels.append(f'tenant_id="{self._sanitize_label_value(tenant_id)}"')
        
        # Add custom labels
        for key, value in labels.items():
            sanitized_key = self._sanitize_label_key(key)
            sanitized_value = self._sanitize_label_value(str(value))
            formatted_labels.append(f'{sanitized_key}="{sanitized_value}"')
        
        return ",".join(formatted_labels)
    
    def _sanitize_label_key(self, key: str) -> str:
        """Sanitize label key for Prometheus format."""
        # Replace invalid characters with underscores
        sanitized = ""
        for char in key:
            if char.isalnum() or char == '_':
                sanitized += char
            else:
                sanitized += '_'
        
        # Ensure it starts with a letter
        if sanitized and not sanitized[0].isalpha():
            sanitized = "label_" + sanitized
        
        return sanitized or "unknown_label"
    
    def _sanitize_label_value(self, value: str) -> str:
        """Sanitize label value for Prometheus format."""
        # Escape quotes and backslashes
        sanitized = value.replace('\\', '\\\\').replace('"', '\\"')
        
        # Replace newlines with spaces
        sanitized = sanitized.replace('\n', ' ').replace('\r', ' ')
        
        return sanitized
    
    def get_export_stats(self) -> Dict[str, Any]:
        """Get export statistics."""
        return {
            "exporter_type": "prometheus",
            "supported_formats": ["prometheus", "aggregated"],
            "timestamp": datetime.now().isoformat()
        }
