"""
Shared error handling for 254Carbon Access Layer.
"""

from typing import Dict, Any, Optional
from pydantic import BaseModel

try:
    from opentelemetry import trace
    HAS_OPENTELEMETRY = True
except ImportError:
    HAS_OPENTELEMETRY = False


class ErrorResponse(BaseModel):
    """Standard error response format."""
    
    trace_id: Optional[str] = None
    code: str
    message: str
    details: Dict[str, Any] = {}


class AccessLayerException(Exception):
    """Base exception for Access Layer services."""
    
    def __init__(self, code: str, message: str, details: Optional[Dict[str, Any]] = None):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(message)
    
    def to_response(self) -> ErrorResponse:
        """Convert to error response."""
        # Get trace ID from current span
        trace_id = None
        if HAS_OPENTELEMETRY:
            current_span = trace.get_current_span()
            if current_span and current_span.is_recording():
                span_context = current_span.get_span_context()
                if span_context.trace_id != 0:
                    trace_id = f"{span_context.trace_id:032x}"
        
        return ErrorResponse(
            trace_id=trace_id,
            code=self.code,
            message=self.message,
            details=self.details
        )


class AuthenticationError(AccessLayerException):
    """Authentication-related errors."""
    
    def __init__(self, message: str = "Authentication failed", details: Optional[Dict[str, Any]] = None):
        super().__init__("AUTHENTICATION_ERROR", message, details)


class AuthorizationError(AccessLayerException):
    """Authorization-related errors."""
    
    def __init__(self, message: str = "Authorization failed", details: Optional[Dict[str, Any]] = None):
        super().__init__("AUTHORIZATION_ERROR", message, details)


class ValidationError(AccessLayerException):
    """Validation-related errors."""
    
    def __init__(self, message: str = "Validation failed", details: Optional[Dict[str, Any]] = None):
        super().__init__("VALIDATION_ERROR", message, details)


class ServiceError(AccessLayerException):
    """Service-related errors."""
    
    def __init__(self, message: str = "Service error", details: Optional[Dict[str, Any]] = None):
        super().__init__("SERVICE_ERROR", message, details)


class ExternalServiceError(AccessLayerException):
    """External service errors."""
    
    def __init__(self, service: str, message: str = "External service error", details: Optional[Dict[str, Any]] = None):
        super().__init__("EXTERNAL_SERVICE_ERROR", f"{service}: {message}", details)


class RateLimitError(AccessLayerException):
    """Rate limiting errors."""
    
    def __init__(self, message: str = "Rate limit exceeded", details: Optional[Dict[str, Any]] = None):
        super().__init__("RATE_LIMIT_ERROR", message, details)
