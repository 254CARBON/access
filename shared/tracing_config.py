"""
OpenTelemetry tracing configuration for the access layer services.
"""

import os
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor
from opentelemetry.instrumentation.kafka import KafkaInstrumentor


def setup_tracing(service_name: str, service_version: str = "1.0.0"):
    """
    Set up OpenTelemetry tracing for a service.
    
    Args:
        service_name: Name of the service
        service_version: Version of the service
    """
    # Create resource
    resource = Resource.create({
        "service.name": service_name,
        "service.version": service_version,
        "service.namespace": "254carbon",
        "deployment.environment": os.getenv("ENVIRONMENT", "development"),
    })
    
    # Set up tracer provider
    tracer_provider = TracerProvider(resource=resource)
    trace.set_tracer_provider(tracer_provider)
    
    # Configure exporters based on environment
    environment = os.getenv("ENVIRONMENT", "development")
    
    if environment == "production":
        # Use OTLP exporter for production
        otlp_endpoint = os.getenv("OTLP_ENDPOINT", "http://jaeger-collector:14250")
        otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
        span_processor = BatchSpanProcessor(otlp_exporter)
    else:
        # Use Jaeger exporter for development
        jaeger_endpoint = os.getenv("JAEGER_ENDPOINT", "http://localhost:14268/api/traces")
        jaeger_exporter = JaegerExporter(
            agent_host_name=os.getenv("JAEGER_AGENT_HOST", "localhost"),
            agent_port=int(os.getenv("JAEGER_AGENT_PORT", "6831")),
        )
        span_processor = BatchSpanProcessor(jaeger_exporter)
    
    # Add span processor to tracer provider
    tracer_provider.add_span_processor(span_processor)
    
    # Instrument libraries
    FastAPIInstrumentor().instrument()
    RequestsInstrumentor().instrument()
    RedisInstrumentor().instrument()
    Psycopg2Instrumentor().instrument()
    KafkaInstrumentor().instrument()
    
    return tracer_provider


def get_tracer(service_name: str):
    """
    Get a tracer instance for a service.
    
    Args:
        service_name: Name of the service
        
    Returns:
        Tracer instance
    """
    return trace.get_tracer(service_name)


def create_span(tracer, operation_name: str, **attributes):
    """
    Create a span for an operation.
    
    Args:
        tracer: Tracer instance
        operation_name: Name of the operation
        **attributes: Additional attributes for the span
        
    Returns:
        Span context manager
    """
    return tracer.start_as_current_span(operation_name, attributes=attributes)


def add_span_attributes(span, **attributes):
    """
    Add attributes to the current span.
    
    Args:
        span: Current span
        **attributes: Attributes to add
    """
    for key, value in attributes.items():
        span.set_attribute(key, value)


def add_span_event(span, event_name: str, **attributes):
    """
    Add an event to the current span.
    
    Args:
        span: Current span
        event_name: Name of the event
        **attributes: Event attributes
    """
    span.add_event(event_name, attributes=attributes)


def set_span_status(span, status_code: str, description: str = None):
    """
    Set the status of a span.
    
    Args:
        span: Current span
        status_code: Status code (OK, ERROR, etc.)
        description: Optional description
    """
    from opentelemetry.trace import Status, StatusCode
    
    if status_code == "OK":
        span.set_status(Status(StatusCode.OK))
    elif status_code == "ERROR":
        span.set_status(Status(StatusCode.ERROR, description))
    else:
        span.set_status(Status(StatusCode.UNSET, description))


def trace_async_function(func):
    """
    Decorator to trace async functions.
    
    Args:
        func: Async function to trace
        
    Returns:
        Wrapped function
    """
    import functools
    import asyncio
    
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        tracer = get_tracer(func.__module__)
        with tracer.start_as_current_span(func.__name__) as span:
            try:
                result = await func(*args, **kwargs)
                set_span_status(span, "OK")
                return result
            except Exception as e:
                set_span_status(span, "ERROR", str(e))
                raise
    
    return wrapper


def trace_sync_function(func):
    """
    Decorator to trace synchronous functions.
    
    Args:
        func: Synchronous function to trace
        
    Returns:
        Wrapped function
    """
    import functools
    
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        tracer = get_tracer(func.__module__)
        with tracer.start_as_current_span(func.__name__) as span:
            try:
                result = func(*args, **kwargs)
                set_span_status(span, "OK")
                return result
            except Exception as e:
                set_span_status(span, "ERROR", str(e))
                raise
    
    return wrapper


def trace_database_operation(operation: str, table: str = None, query: str = None):
    """
    Create a span for a database operation.
    
    Args:
        operation: Type of operation (SELECT, INSERT, UPDATE, DELETE)
        table: Table name
        query: SQL query
        
    Returns:
        Span context manager
    """
    tracer = get_tracer("database")
    attributes = {
        "db.operation": operation,
    }
    
    if table:
        attributes["db.table"] = table
    if query:
        attributes["db.statement"] = query
    
    return tracer.start_as_current_span(f"db.{operation.lower()}", attributes=attributes)


def trace_redis_operation(operation: str, key: str = None):
    """
    Create a span for a Redis operation.
    
    Args:
        operation: Type of operation (GET, SET, DEL, etc.)
        key: Redis key
        
    Returns:
        Span context manager
    """
    tracer = get_tracer("redis")
    attributes = {
        "redis.operation": operation,
    }
    
    if key:
        attributes["redis.key"] = key
    
    return tracer.start_as_current_span(f"redis.{operation.lower()}", attributes=attributes)


def trace_kafka_operation(operation: str, topic: str = None, partition: int = None):
    """
    Create a span for a Kafka operation.
    
    Args:
        operation: Type of operation (produce, consume)
        topic: Kafka topic
        partition: Kafka partition
        
    Returns:
        Span context manager
    """
    tracer = get_tracer("kafka")
    attributes = {
        "messaging.system": "kafka",
        "messaging.operation": operation,
    }
    
    if topic:
        attributes["messaging.destination"] = topic
    if partition is not None:
        attributes["messaging.kafka.partition"] = partition
    
    return tracer.start_as_current_span(f"kafka.{operation}", attributes=attributes)


def trace_http_request(method: str, url: str, status_code: int = None):
    """
    Create a span for an HTTP request.
    
    Args:
        method: HTTP method
        url: Request URL
        status_code: Response status code
        
    Returns:
        Span context manager
    """
    tracer = get_tracer("http")
    attributes = {
        "http.method": method,
        "http.url": url,
    }
    
    if status_code:
        attributes["http.status_code"] = status_code
    
    return tracer.start_as_current_span(f"http.{method.lower()}", attributes=attributes)
