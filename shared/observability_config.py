"""
Observability configuration for 254Carbon Access Layer.
"""

import os
from typing import Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class ObservabilityConfig:
    """Configuration for observability features."""
    
    # Logging configuration
    log_level: str = "info"
    log_format: str = "json"
    enable_console_logging: bool = True
    
    # Metrics configuration
    enable_metrics: bool = True
    metrics_port: int = 9090
    metrics_path: str = "/metrics"
    
    # Tracing configuration
    enable_tracing: bool = True
    otel_exporter: Optional[str] = None
    enable_console_tracing: bool = False
    trace_sampling_rate: float = 1.0
    
    # Service-specific settings
    service_name: str = "unknown"
    service_version: str = "1.0.0"
    environment: str = "development"
    
    # Performance settings
    max_log_message_size: int = 8192
    batch_size: int = 100
    flush_interval_seconds: int = 5
    
    @classmethod
    def from_env(cls, service_name: str = "unknown") -> "ObservabilityConfig":
        """Create configuration from environment variables."""
        return cls(
            log_level=os.getenv("LOG_LEVEL", "info"),
            log_format=os.getenv("LOG_FORMAT", "json"),
            enable_console_logging=os.getenv("ENABLE_CONSOLE_LOGGING", "true").lower() == "true",
            
            enable_metrics=os.getenv("ENABLE_METRICS", "true").lower() == "true",
            metrics_port=int(os.getenv("METRICS_PORT", "9090")),
            metrics_path=os.getenv("METRICS_PATH", "/metrics"),
            
            enable_tracing=os.getenv("ENABLE_TRACING", "true").lower() == "true",
            otel_exporter=os.getenv("OTEL_EXPORTER"),
            enable_console_tracing=os.getenv("ENABLE_CONSOLE_TRACING", "false").lower() == "true",
            trace_sampling_rate=float(os.getenv("TRACE_SAMPLING_RATE", "1.0")),
            
            service_name=service_name,
            service_version=os.getenv("SERVICE_VERSION", "1.0.0"),
            environment=os.getenv("ACCESS_ENV", "development"),
            
            max_log_message_size=int(os.getenv("MAX_LOG_MESSAGE_SIZE", "8192")),
            batch_size=int(os.getenv("BATCH_SIZE", "100")),
            flush_interval_seconds=int(os.getenv("FLUSH_INTERVAL_SECONDS", "5"))
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            "log_level": self.log_level,
            "log_format": self.log_format,
            "enable_console_logging": self.enable_console_logging,
            "enable_metrics": self.enable_metrics,
            "metrics_port": self.metrics_port,
            "metrics_path": self.metrics_path,
            "enable_tracing": self.enable_tracing,
            "otel_exporter": self.otel_exporter,
            "enable_console_tracing": self.enable_console_tracing,
            "trace_sampling_rate": self.trace_sampling_rate,
            "service_name": self.service_name,
            "service_version": self.service_version,
            "environment": self.environment,
            "max_log_message_size": self.max_log_message_size,
            "batch_size": self.batch_size,
            "flush_interval_seconds": self.flush_interval_seconds
        }


def get_observability_config(service_name: str = "unknown") -> ObservabilityConfig:
    """Get observability configuration for a service."""
    return ObservabilityConfig.from_env(service_name)
