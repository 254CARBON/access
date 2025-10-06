"""
Comprehensive observability module for 254Carbon Access Layer.
Integrates logging, metrics, and tracing.
"""

import os
import time
from typing import Optional, Dict, Any, Callable
from contextlib import contextmanager
from functools import wraps

from .logging import configure_logging, get_logger, set_request_id, set_user_context, clear_context
from .metrics import get_metrics_collector, measure_time, count_calls
from .tracing import configure_tracing, trace_function, add_span_attributes, add_span_event


class ObservabilityManager:
    """Centralized observability manager for services."""
    
    def __init__(self, service_name: str, log_level: str = "info", 
                 otel_exporter: Optional[str] = None, enable_console: bool = False):
        self.service_name = service_name
        self.log_level = log_level
        self.otel_exporter = otel_exporter
        self.enable_console = enable_console
        
        # Initialize components
        self._setup_logging()
        self._setup_tracing()
        self._setup_metrics()
        
        # Get logger
        self.logger = get_logger(f"{service_name}.observability")
        
        self.logger.info("Observability initialized", 
                        service=service_name, 
                        log_level=log_level,
                        tracing_enabled=bool(otel_exporter))
    
    def _setup_logging(self):
        """Set up structured logging."""
        configure_logging(self.service_name, self.log_level)
    
    def _setup_tracing(self):
        """Set up distributed tracing."""
        if self.otel_exporter or self.enable_console:
            configure_tracing(
                self.service_name, 
                self.otel_exporter, 
                self.enable_console
            )
    
    def _setup_metrics(self):
        """Set up metrics collection."""
        self.metrics = get_metrics_collector(self.service_name)
    
    def trace_request(self, request_id: Optional[str] = None, 
                     user_id: Optional[str] = None, 
                     tenant_id: Optional[str] = None):
        """Set up request context for tracing."""
        if request_id:
            set_request_id(request_id)
        if user_id or tenant_id:
            set_user_context(user_id, tenant_id)
        
        # Add span attributes
        add_span_attributes(
            request_id=request_id,
            user_id=user_id,
            tenant_id=tenant_id
        )
    
    def clear_request_context(self):
        """Clear request context."""
        clear_context()
    
    def log_request(self, method: str, endpoint: str, status_code: int, 
                   duration: float, **kwargs):
        """Log HTTP request with full context."""
        self.logger.info(
            "HTTP request completed",
            method=method,
            endpoint=endpoint,
            status_code=status_code,
            duration=duration,
            **kwargs
        )
        
        # Record metrics
        self.metrics.record_http_request(method, endpoint, status_code, duration)
    
    def log_error(self, error_type: str, error_message: str, **kwargs):
        """Log error with full context."""
        self.logger.error(
            "Error occurred",
            error_type=error_type,
            error_message=error_message,
            **kwargs
        )
        
        # Record metrics
        self.metrics.record_error(error_type)
        
        # Add span event
        add_span_event("error", 
                      error_type=error_type, 
                      error_message=error_message)
    
    def log_business_event(self, event_type: str, **kwargs):
        """Log business event with full context."""
        self.logger.info(
            "Business event",
            event_type=event_type,
            **kwargs
        )
        
        # Record metrics
        self.metrics.record_business_event(event_type)
        
        # Add span event
        add_span_event("business_event", event_type=event_type, **kwargs)
    
    def measure_operation(self, operation_name: str, **labels):
        """Context manager to measure operation performance."""
        return self.metrics.time_operation(operation_name, **labels)
    
    def instrument_function(self, func: Callable, 
                           operation_name: Optional[str] = None,
                           measure_time: bool = True,
                           count_calls: bool = True,
                           **attributes):
        """Instrument a function with logging, metrics, and tracing."""
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            name = operation_name or f"{func.__module__}.{func.__name__}"
            
            # Start timing
            start_time = time.time()
            
            # Log function start
            self.logger.debug(f"Function {name} started")
            
            try:
                # Execute function
                result = func(*args, **kwargs)
                
                # Calculate duration
                duration = time.time() - start_time
                
                # Log success
                self.logger.debug(f"Function {name} completed", duration=duration)
                
                # Record metrics
                if measure_time:
                    self.metrics.observe_histogram(
                        f"{name}_duration_seconds", duration, **labels
                    )
                if count_calls:
                    self.metrics.increment_counter(
                        f"{name}_calls_total", **labels
                    )
                
                return result
                
            except Exception as e:
                # Calculate duration
                duration = time.time() - start_time
                
                # Log error
                self.logger.error(
                    f"Function {name} failed",
                    error=str(e),
                    duration=duration
                )
                
                # Record error metrics
                self.metrics.record_error("function_error", self.service_name)
                
                raise
        
        # Handle async functions
        if asyncio.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                name = operation_name or f"{func.__module__}.{func.__name__}"
                
                # Start timing
                start_time = time.time()
                
                # Log function start
                self.logger.debug(f"Async function {name} started")
                
                try:
                    # Execute function
                    result = await func(*args, **kwargs)
                    
                    # Calculate duration
                    duration = time.time() - start_time
                    
                    # Log success
                    self.logger.debug(f"Async function {name} completed", duration=duration)
                    
                    # Record metrics
                    if measure_time:
                        self.metrics.observe_histogram(
                            f"{name}_duration_seconds", duration, **labels
                        )
                    if count_calls:
                        self.metrics.increment_counter(
                            f"{name}_calls_total", **labels
                        )
                    
                    return result
                    
                except Exception as e:
                    # Calculate duration
                    duration = time.time() - start_time
                    
                    # Log error
                    self.logger.error(
                        f"Async function {name} failed",
                        error=str(e),
                        duration=duration
                    )
                    
                    # Record error metrics
                    self.metrics.record_error("function_error", self.service_name)
                    
                    raise
            
            return async_wrapper
        
        return wrapper


def get_observability_manager(service_name: str, **kwargs) -> ObservabilityManager:
    """Get an observability manager for a service."""
    return ObservabilityManager(service_name, **kwargs)


# Decorators for easy instrumentation
def observe_function(operation_name: Optional[str] = None, **attributes):
    """Decorator to observe a function with logging, metrics, and tracing."""
    def decorator(func: Callable) -> Callable:
        # Apply tracing decorator
        traced_func = trace_function(operation_name, **attributes)(func)
        
        # Apply metrics decorator
        if operation_name:
            metrics_func = measure_time(f"{operation_name}_duration_seconds")(traced_func)
            return count_calls(f"{operation_name}_calls_total")(metrics_func)
        
        return traced_func
    return decorator


@contextmanager
def observe_operation(operation_name: str, **attributes):
    """Context manager to observe an operation."""
    with trace_function(operation_name, **attributes):
        start_time = time.time()
        try:
            yield
        finally:
            duration = time.time() - start_time
            # Log operation completion
            logger = get_logger("observability")
            logger.info(f"Operation {operation_name} completed", duration=duration)


# Health check utilities
def create_health_check(service_name: str, dependencies: Optional[Dict[str, Callable]] = None):
    """Create a health check function for a service."""
    logger = get_logger(f"{service_name}.health")
    
    async def health_check():
        """Health check endpoint."""
        health_status = {
            "status": "healthy",
            "service": service_name,
            "timestamp": time.time(),
            "dependencies": {}
        }
        
        if dependencies:
            for dep_name, dep_check in dependencies.items():
                try:
                    if asyncio.iscoroutinefunction(dep_check):
                        await dep_check()
                    else:
                        dep_check()
                    health_status["dependencies"][dep_name] = "healthy"
                except Exception as e:
                    health_status["dependencies"][dep_name] = f"unhealthy: {str(e)}"
                    health_status["status"] = "unhealthy"
                    logger.error(f"Dependency {dep_name} is unhealthy", error=str(e))
        
        return health_status
    
    return health_check
