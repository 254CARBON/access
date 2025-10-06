"""
Shared tracing configuration for 254Carbon Access Layer.
"""

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.kafka import KafkaInstrumentor
from opentelemetry.instrumentation.asyncio import AsyncioInstrumentor
from opentelemetry.trace import Status, StatusCode
from typing import Optional, Dict, Any
import os
import functools
import time
import asyncio
from contextlib import contextmanager


def configure_tracing(service_name: str, otel_exporter: Optional[str] = None, enable_console: bool = False) -> None:
    """Configure OpenTelemetry tracing for a service."""
    
    # Set up resource
    resource = Resource.create({
        "service.name": service_name,
        "service.version": "1.0.0",
        "service.namespace": "254carbon",
        "service.instance.id": os.getenv("HOSTNAME", "unknown"),
        "deployment.environment": os.getenv("ACCESS_ENV", "development")
    })
    
    # Set up tracer provider
    trace.set_tracer_provider(TracerProvider(resource=resource))
    tracer = trace.get_tracer(__name__)
    
    # Set up span exporters
    if otel_exporter:
        otlp_exporter = OTLPSpanExporter(endpoint=otel_exporter)
        span_processor = BatchSpanProcessor(otlp_exporter)
        trace.get_tracer_provider().add_span_processor(span_processor)
    
    if enable_console or os.getenv("ACCESS_ENV") == "development":
        console_exporter = ConsoleSpanExporter()
        console_processor = BatchSpanProcessor(console_exporter)
        trace.get_tracer_provider().add_span_processor(console_processor)
    
    # Instrument libraries
    FastAPIInstrumentor.instrument()
    RedisInstrumentor().instrument()
    SQLAlchemyInstrumentor().instrument()
    HTTPXClientInstrumentor().instrument()
    KafkaInstrumentor().instrument()
    AsyncioInstrumentor().instrument()


def get_tracer(name: str):
    """Get a tracer instance."""
    return trace.get_tracer(name)


def get_current_span():
    """Get the current active span."""
    return trace.get_current_span()


def create_span(name: str, **kwargs):
    """Create a new span."""
    tracer = get_tracer(__name__)
    return tracer.start_span(name, **kwargs)


@contextmanager
def trace_operation(operation_name: str, **attributes):
    """Context manager to trace an operation."""
    tracer = get_tracer(__name__)
    with tracer.start_as_current_span(operation_name) as span:
        # Add attributes to span
        for key, value in attributes.items():
            span.set_attribute(key, value)
        
        try:
            yield span
        except Exception as e:
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.set_attribute("error", True)
            span.set_attribute("error.message", str(e))
            raise


def trace_function(operation_name: Optional[str] = None, **attributes):
    """Decorator to trace a function."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            name = operation_name or f"{func.__module__}.{func.__name__}"
            tracer = get_tracer(__name__)
            
            with tracer.start_as_current_span(name) as span:
                # Add function attributes
                span.set_attribute("function.name", func.__name__)
                span.set_attribute("function.module", func.__module__)
                
                # Add custom attributes
                for key, value in attributes.items():
                    span.set_attribute(key, value)
                
                try:
                    result = func(*args, **kwargs)
                    span.set_status(Status(StatusCode.OK))
                    return result
                except Exception as e:
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    span.set_attribute("error", True)
                    span.set_attribute("error.message", str(e))
                    raise
        
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            name = operation_name or f"{func.__module__}.{func.__name__}"
            tracer = get_tracer(__name__)
            
            with tracer.start_as_current_span(name) as span:
                # Add function attributes
                span.set_attribute("function.name", func.__name__)
                span.set_attribute("function.module", func.__module__)
                
                # Add custom attributes
                for key, value in attributes.items():
                    span.set_attribute(key, value)
                
                try:
                    result = await func(*args, **kwargs)
                    span.set_status(Status(StatusCode.OK))
                    return result
                except Exception as e:
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    span.set_attribute("error", True)
                    span.set_attribute("error.message", str(e))
                    raise
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return wrapper
    return decorator


def add_span_attributes(**attributes):
    """Add attributes to the current span."""
    current_span = get_current_span()
    if current_span and current_span.is_recording():
        for key, value in attributes.items():
            current_span.set_attribute(key, value)


def add_span_event(name: str, **attributes):
    """Add an event to the current span."""
    current_span = get_current_span()
    if current_span and current_span.is_recording():
        current_span.add_event(name, attributes)


def set_span_status(status_code: StatusCode, description: Optional[str] = None):
    """Set the status of the current span."""
    current_span = get_current_span()
    if current_span and current_span.is_recording():
        current_span.set_status(Status(status_code, description))
