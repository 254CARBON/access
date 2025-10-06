"""
Shared logging configuration for 254Carbon Access Layer.
"""

import sys
import structlog
import logging
import uuid
import time
from typing import Any, Dict, Optional
from contextvars import ContextVar

try:
    from opentelemetry import trace
    HAS_OPENTELEMETRY = True
except ImportError:
    HAS_OPENTELEMETRY = False

# Context variables for correlation IDs
request_id_var: ContextVar[Optional[str]] = ContextVar('request_id', default=None)
user_id_var: ContextVar[Optional[str]] = ContextVar('user_id', default=None)
tenant_id_var: ContextVar[Optional[str]] = ContextVar('tenant_id', default=None)


def configure_logging(service_name: str, log_level: str = "info") -> None:
    """Configure structured logging for a service."""
    
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            add_service_context,
            add_trace_context,
            add_correlation_context,
            add_timestamp,
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper()),
    )


def add_service_context(logger: Any, method_name: str, event_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Add service context to log events."""
    # Extract service name from logger name
    logger_name = event_dict.get("logger", "")
    if "." in logger_name:
        service_name = logger_name.split(".")[0]
        event_dict["service"] = service_name
    
    return event_dict


def add_trace_context(logger: Any, method_name: str, event_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Add trace context to log events."""
    if HAS_OPENTELEMETRY:
        # Get current trace context
        current_span = trace.get_current_span()
        if current_span and current_span.is_recording():
            span_context = current_span.get_span_context()
            if span_context.trace_id != 0:
                event_dict["trace_id"] = f"{span_context.trace_id:032x}"
            if span_context.span_id != 0:
                event_dict["span_id"] = f"{span_context.span_id:016x}"
    
    return event_dict


def add_correlation_context(logger: Any, method_name: str, event_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Add correlation context to log events."""
    # Add request ID
    request_id = request_id_var.get()
    if request_id:
        event_dict["request_id"] = request_id
    
    # Add user context
    user_id = user_id_var.get()
    if user_id:
        event_dict["user_id"] = user_id
    
    tenant_id = tenant_id_var.get()
    if tenant_id:
        event_dict["tenant_id"] = tenant_id
    
    return event_dict


def add_timestamp(logger: Any, method_name: str, event_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Add high-precision timestamp to log events."""
    event_dict["timestamp"] = time.time()
    return event_dict


def set_request_id(request_id: Optional[str] = None) -> str:
    """Set request ID in context."""
    if request_id is None:
        request_id = str(uuid.uuid4())
    request_id_var.set(request_id)
    return request_id


def set_user_context(user_id: Optional[str] = None, tenant_id: Optional[str] = None):
    """Set user context in logging."""
    if user_id:
        user_id_var.set(user_id)
    if tenant_id:
        tenant_id_var.set(tenant_id)


def clear_context():
    """Clear all context variables."""
    request_id_var.set(None)
    user_id_var.set(None)
    tenant_id_var.set(None)


def get_logger(name: str) -> structlog.BoundLogger:
    """Get a structured logger instance."""
    return structlog.get_logger(name)
