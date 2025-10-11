"""Tracing utilities with optional OpenTelemetry integration."""

from typing import Optional, Dict, Any
import os
import functools
import time
import asyncio
from contextlib import contextmanager

try:  # pragma: no cover - optional dependency
    from opentelemetry import trace  # type: ignore
    from opentelemetry.sdk.trace import TracerProvider  # type: ignore
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter  # type: ignore
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter  # type: ignore
    from opentelemetry.sdk.resources import Resource  # type: ignore
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor  # type: ignore
    from opentelemetry.instrumentation.redis import RedisInstrumentor  # type: ignore
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor  # type: ignore
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor  # type: ignore
    from opentelemetry.instrumentation.kafka import KafkaInstrumentor  # type: ignore
    from opentelemetry.instrumentation.asyncio import AsyncioInstrumentor  # type: ignore
    from opentelemetry.trace import Status, StatusCode  # type: ignore

    OTEL_AVAILABLE = True
except ModuleNotFoundError:  # pragma: no cover
    trace = None  # type: ignore
    TracerProvider = object  # type: ignore
    BatchSpanProcessor = ConsoleSpanExporter = OTLPSpanExporter = Resource = object  # type: ignore
    FastAPIInstrumentor = RedisInstrumentor = SQLAlchemyInstrumentor = HTTPXClientInstrumentor = KafkaInstrumentor = AsyncioInstrumentor = object  # type: ignore

    class StatusCode:  # type: ignore
        OK = "OK"
        ERROR = "ERROR"

    class Status:  # type: ignore
        def __init__(self, status_code: StatusCode, description: Optional[str] = None):
            self.status_code = status_code
            self.description = description

    OTEL_AVAILABLE = False


def _build_otlp_exporter_kwargs(endpoint_override: Optional[str] = None) -> Dict[str, Any]:
    endpoint = (
        endpoint_override
        or os.getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT")
        or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
        or "http://otel-collector:4317"
    )
    headers_env = os.getenv("OTEL_EXPORTER_OTLP_HEADERS")
    headers: Dict[str, str] = {}
    if headers_env:
        for segment in headers_env.split(","):
            if not segment or "=" not in segment:
                continue
            key, value = segment.split("=", 1)
            key = key.strip()
            value = value.strip()
            if key:
                headers[key] = value

    exporter_kwargs: Dict[str, Any] = {"endpoint": endpoint}
    if headers:
        exporter_kwargs["headers"] = headers

    if endpoint.startswith("http://"):
        exporter_kwargs["insecure"] = True
    else:
        certificate_path = os.getenv("OTEL_EXPORTER_OTLP_CERTIFICATE")
        if certificate_path:
            try:
                import grpc  # type: ignore

                with open(certificate_path, "rb") as cert_file:
                    exporter_kwargs["credentials"] = grpc.ssl_channel_credentials(cert_file.read())
            except (ImportError, OSError):
                pass

    return exporter_kwargs


if OTEL_AVAILABLE:

    def configure_tracing(service_name: str, otel_exporter: Optional[str] = None, enable_console: bool = False) -> None:
        """Configure OpenTelemetry tracing for a service."""

        resource = Resource.create({
            "service.name": service_name,
            "service.version": "1.0.0",
            "service.namespace": "254carbon",
            "service.instance.id": os.getenv("HOSTNAME", "unknown"),
            "deployment.environment": os.getenv("ACCESS_ENV", "development")
        })

        trace.set_tracer_provider(TracerProvider(resource=resource))

        otlp_exporter = OTLPSpanExporter(**_build_otlp_exporter_kwargs(otel_exporter))
        span_processor = BatchSpanProcessor(otlp_exporter)
        trace.get_tracer_provider().add_span_processor(span_processor)

        if enable_console or os.getenv("ACCESS_ENV") == "development":
            console_exporter = ConsoleSpanExporter()
            console_processor = BatchSpanProcessor(console_exporter)
            trace.get_tracer_provider().add_span_processor(console_processor)

        # FastAPI instrumentation requires an instance in recent releases.
        # Instantiating avoids TypeError when the class method signature changes.
        FastAPIInstrumentor().instrument()
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
            for key, value in attributes.items():
                span.set_attribute(key, value)

            try:
                yield span
            except Exception as exc:  # pragma: no cover - pass through
                span.set_status(Status(StatusCode.ERROR, str(exc)))
                span.set_attribute("error", True)
                span.set_attribute("error.message", str(exc))
                raise


    def trace_function(operation_name: Optional[str] = None, **attributes):
        """Decorator to trace a function."""

        def decorator(func):
            if asyncio.iscoroutinefunction(func):

                @functools.wraps(func)
                async def async_wrapper(*args, **kwargs):
                    name = operation_name or f"{func.__module__}.{func.__name__}"
                    tracer = get_tracer(__name__)

                    with tracer.start_as_current_span(name) as span:
                        span.set_attribute("function.name", func.__name__)
                        span.set_attribute("function.module", func.__module__)
                        for key, value in attributes.items():
                            span.set_attribute(key, value)

                        try:
                            result = await func(*args, **kwargs)
                            span.set_status(Status(StatusCode.OK))
                            return result
                        except Exception as exc:  # pragma: no cover - tracing path
                            span.set_status(Status(StatusCode.ERROR, str(exc)))
                            span.set_attribute("error", True)
                            span.set_attribute("error.message", str(exc))
                            raise

                return async_wrapper

            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                name = operation_name or f"{func.__module__}.{func.__name__}"
                tracer = get_tracer(__name__)

                with tracer.start_as_current_span(name) as span:
                    span.set_attribute("function.name", func.__name__)
                    span.set_attribute("function.module", func.__module__)
                    for key, value in attributes.items():
                        span.set_attribute(key, value)

                    try:
                        result = func(*args, **kwargs)
                        span.set_status(Status(StatusCode.OK))
                        return result
                    except Exception as exc:  # pragma: no cover - tracing path
                        span.set_status(Status(StatusCode.ERROR, str(exc)))
                        span.set_attribute("error", True)
                        span.set_attribute("error.message", str(exc))
                        raise

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


else:

    class _NoOpSpan:
        def set_attribute(self, *args, **kwargs):
            return None

        def set_status(self, *args, **kwargs):
            return None

        def add_event(self, *args, **kwargs):
            return None

        def is_recording(self) -> bool:
            return False


    class _NoOpTracer:
        @contextmanager
        def start_as_current_span(self, *args, **kwargs):  # pragma: no cover - noop
            yield _NoOpSpan()

        def start_span(self, *args, **kwargs):  # pragma: no cover - noop
            return _NoOpSpan()


    _GLOBAL_TRACER = _NoOpTracer()


    def configure_tracing(service_name: str, otel_exporter: Optional[str] = None, enable_console: bool = False) -> None:
        """No-op tracing configuration when OpenTelemetry is unavailable."""
        return None


    def get_tracer(name: str):
        """Return a no-op tracer."""
        return _GLOBAL_TRACER


    def get_current_span():
        """Return a no-op span."""
        return _NoOpSpan()


    def create_span(name: str, **kwargs):
        """Return a no-op span."""
        return _NoOpSpan()


    @contextmanager
    def trace_operation(operation_name: str, **attributes):
        """Context manager that yields a no-op span."""
        yield _NoOpSpan()


    def trace_function(operation_name: Optional[str] = None, **attributes):
        """Decorator that returns the original function unchanged."""

        def decorator(func):
            if asyncio.iscoroutinefunction(func):

                @functools.wraps(func)
                async def async_wrapper(*args, **kwargs):
                    return await func(*args, **kwargs)

                return async_wrapper

            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)

            return wrapper

        return decorator


    def add_span_attributes(**attributes):
        """No-op when OpenTelemetry is unavailable."""
        return None


    def add_span_event(name: str, **attributes):
        """No-op when OpenTelemetry is unavailable."""
        return None


    def set_span_status(status_code: StatusCode, description: Optional[str] = None):
        """No-op when OpenTelemetry is unavailable."""
        return None
