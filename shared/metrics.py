"""
Shared metrics configuration for 254Carbon Access Layer.
"""

try:  # pragma: no cover - allow running without prometheus_client locally/tests
    from prometheus_client import Counter, Histogram, Gauge, Info, Summary, start_http_server, CollectorRegistry  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    class _DummyMetric:
        def __init__(self, *args, **kwargs):
            pass

        def labels(self, *args, **kwargs):
            return self

        def info(self, *args, **kwargs):
            return None

        def observe(self, *args, **kwargs):
            return None

        def inc(self, *args, **kwargs):
            return None

        def set(self, *args, **kwargs):
            return None

    def Counter(*args, **kwargs):  # type: ignore
        return _DummyMetric()

    def Histogram(*args, **kwargs):  # type: ignore
        return _DummyMetric()

    def Gauge(*args, **kwargs):  # type: ignore
        return _DummyMetric()

    def Info(*args, **kwargs):  # type: ignore
        metric = _DummyMetric()

        def _info(values):
            return None

        metric.info = _info  # type: ignore
        return metric

    def Summary(*args, **kwargs):  # type: ignore
        return _DummyMetric()

    class CollectorRegistry:  # type: ignore
        pass

    def start_http_server(*args, **kwargs):  # type: ignore
        return None
from typing import Dict, Any, Optional, Callable
import time
import functools
import threading
import asyncio
from contextlib import contextmanager


class MetricsCollector:
    """Centralized metrics collector for services."""
    
    def __init__(self, service_name: str, registry: Optional[CollectorRegistry] = None):
        self.service_name = service_name
        self.registry = registry
        self._metrics: Dict[str, Any] = {}
        self._lock = threading.Lock()
        self._setup_metrics()
    
    def _setup_metrics(self):
        """Set up common metrics for the service."""
        
        # Service info
        self._metrics["service_info"] = Info(
            "service_info",
            "Service information",
            registry=self.registry
        )
        self._metrics["service_info"].info({
            "service": self.service_name,
            "version": "1.0.0"
        })
        
        # HTTP metrics
        self._metrics["http_requests_total"] = Counter(
            "http_requests_total",
            "Total HTTP requests",
            ["method", "endpoint", "status_code"],
            registry=self.registry
        )
        
        self._metrics["http_request_duration_seconds"] = Histogram(
            "http_request_duration_seconds",
            "HTTP request duration in seconds",
            ["method", "endpoint"],
            registry=self.registry
        )
        
        # Health check metrics
        self._metrics["health_check_total"] = Counter(
            "health_check_total",
            "Total health check requests",
            ["status"],
            registry=self.registry
        )
        
        # Error metrics
        self._metrics["errors_total"] = Counter(
            "errors_total",
            "Total errors",
            ["error_type", "service"],
            registry=self.registry
        )
        
        # Business metrics
        self._metrics["business_events_total"] = Counter(
            "business_events_total",
            "Total business events",
            ["event_type", "service"],
            registry=self.registry
        )
        
        # Service-specific metrics
        if self.service_name == "gateway":
            self._setup_gateway_metrics()
        elif self.service_name == "streaming":
            self._setup_streaming_metrics()
        elif self.service_name == "auth":
            self._setup_auth_metrics()
        elif self.service_name == "entitlements":
            self._setup_entitlements_metrics()
        elif self.service_name == "metrics":
            self._setup_metrics_service_metrics()
    
    def _setup_gateway_metrics(self):
        """Set up gateway-specific metrics."""
        self._metrics["rate_limit_hits_total"] = Counter(
            "rate_limit_hits_total",
            "Total rate limit hits",
            ["endpoint", "client_id"],
            registry=None
        )
        
        self._metrics["cache_hits_total"] = Counter(
            "cache_hits_total",
            "Total cache hits",
            ["cache_type"],
            registry=None
        )
        
        self._metrics["cache_misses_total"] = Counter(
            "cache_misses_total",
            "Total cache misses",
            ["cache_type"],
            registry=None
        )
    
    def _setup_streaming_metrics(self):
        """Set up streaming-specific metrics."""
        self._metrics["active_connections"] = Gauge(
            "active_connections",
            "Number of active connections",
            registry=None
        )
        
        self._metrics["messages_sent_total"] = Counter(
            "messages_sent_total",
            "Total messages sent",
            ["topic"],
            registry=None
        )
        
        self._metrics["connection_duration_seconds"] = Histogram(
            "connection_duration_seconds",
            "Connection duration in seconds",
            registry=None
        )
    
    def _setup_auth_metrics(self):
        """Set up auth-specific metrics."""
        self._metrics["token_validations_total"] = Counter(
            "token_validations_total",
            "Total token validations",
            ["status"],
            registry=None
        )
        
        self._metrics["jwks_refresh_total"] = Counter(
            "jwks_refresh_total",
            "Total JWKS refreshes",
            ["status"],
            registry=None
        )
        
        self._metrics["jwks_refresh_duration_seconds"] = Histogram(
            "jwks_refresh_duration_seconds",
            "JWKS refresh duration in seconds",
            registry=None
        )
    
    def _setup_entitlements_metrics(self):
        """Set up entitlements-specific metrics."""
        self._metrics["entitlement_checks_total"] = Counter(
            "entitlement_checks_total",
            "Total entitlement checks",
            ["decision"],
            registry=None
        )
        
        self._metrics["entitlement_check_duration_seconds"] = Histogram(
            "entitlement_check_duration_seconds",
            "Entitlement check duration in seconds",
            registry=None
        )
        
        self._metrics["cache_hit_ratio"] = Gauge(
            "cache_hit_ratio",
            "Cache hit ratio",
            registry=None
        )
    
    def _setup_metrics_service_metrics(self):
        """Set up metrics service-specific metrics."""
        self._metrics["metrics_ingested_total"] = Counter(
            "metrics_ingested_total",
            "Total metrics ingested",
            ["metric_type"],
            registry=None
        )
        
        self._metrics["metrics_exported_total"] = Counter(
            "metrics_exported_total",
            "Total metrics exported",
            registry=None
        )
    
    def get_metric(self, name: str):
        """Get a metric by name."""
        return self._metrics.get(name)
    
    def start_metrics_server(self, port: int = 9090):
        """Start the Prometheus metrics server."""
        start_http_server(port)
    
    def record_http_request(self, method: str, endpoint: str, status_code: int, duration: float):
        """Record HTTP request metrics."""
        self._metrics["http_requests_total"].labels(
            method=method,
            endpoint=endpoint,
            status_code=str(status_code)
        ).inc()
        
        self._metrics["http_request_duration_seconds"].labels(
            method=method,
            endpoint=endpoint
        ).observe(duration)
    
    def record_health_check(self, status: str):
        """Record health check metrics."""
        self._metrics["health_check_total"].labels(status=status).inc()
    
    def record_error(self, error_type: str, service: Optional[str] = None):
        """Record error metrics."""
        service_name = service or self.service_name
        self._metrics["errors_total"].labels(error_type=error_type, service=service_name).inc()
    
    def record_business_event(self, event_type: str, service: Optional[str] = None):
        """Record business event metrics."""
        service_name = service or self.service_name
        self._metrics["business_events_total"].labels(event_type=event_type, service=service_name).inc()
    
    @contextmanager
    def time_operation(self, operation_name: str, **labels):
        """Context manager to time an operation."""
        start_time = time.time()
        try:
            yield
        finally:
            duration = time.time() - start_time
            if operation_name in self._metrics:
                self._metrics[operation_name].labels(**labels).observe(duration)
    
    def increment_counter(self, metric_name: str, **labels):
        """Increment a counter metric."""
        if metric_name in self._metrics:
            self._metrics[metric_name].labels(**labels).inc()
    
    def set_gauge(self, metric_name: str, value: float, **labels):
        """Set a gauge metric value."""
        if metric_name in self._metrics:
            self._metrics[metric_name].labels(**labels).set(value)
    
    def observe_histogram(self, metric_name: str, value: float, **labels):
        """Observe a histogram metric."""
        if metric_name in self._metrics:
            self._metrics[metric_name].labels(**labels).observe(value)


def get_metrics_collector(service_name: str, registry: Optional[CollectorRegistry] = None) -> MetricsCollector:
    """Get a metrics collector for a service."""
    return MetricsCollector(service_name, registry)


def measure_time(metric_name: str, collector: Optional[MetricsCollector] = None, **labels):
    """Decorator to measure function execution time."""
    def decorator(func: Callable) -> Callable:
        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                start_time = time.time()
                try:
                    return await func(*args, **kwargs)
                finally:
                    duration = time.time() - start_time
                    if collector and metric_name in collector._metrics:
                        collector._metrics[metric_name].labels(**labels).observe(duration)

            return async_wrapper

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                return func(*args, **kwargs)
            finally:
                duration = time.time() - start_time
                if collector and metric_name in collector._metrics:
                    collector._metrics[metric_name].labels(**labels).observe(duration)

        return sync_wrapper
    return decorator


def count_calls(metric_name: str, collector: Optional[MetricsCollector] = None, **labels):
    """Decorator to count function calls."""
    def decorator(func: Callable) -> Callable:
        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                if collector and metric_name in collector._metrics:
                    collector._metrics[metric_name].labels(**labels).inc()
                return await func(*args, **kwargs)

            return async_wrapper

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            if collector and metric_name in collector._metrics:
                collector._metrics[metric_name].labels(**labels).inc()
            return func(*args, **kwargs)

        return sync_wrapper
    return decorator
