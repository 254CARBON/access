"""
Shared configuration management for 254Carbon Access Layer.
"""

import os
from typing import Optional

try:
    from pydantic import Field  # type: ignore
    from pydantic_settings import BaseSettings, SettingsConfigDict  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - lightweight fallback for tests
    class BaseSettings:  # type: ignore
        """Minimal BaseSettings fallback when pydantic is unavailable."""

        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

        class Config:  # noqa: D401
            env_file = ".env"
            case_sensitive = False
            extra = "allow"

    def Field(default=None, **kwargs):  # type: ignore
        return default


class BaseConfig(BaseSettings):
    """Base configuration class with common settings."""

    if 'SettingsConfigDict' in globals():  # pragma: no branch
        model_config = SettingsConfigDict(
            env_file=".env",
            case_sensitive=False,
            extra="allow"
        )
    
    # Environment
    env: str = Field(default="local", env="ACCESS_ENV")
    log_level: str = Field(default="info", env="ACCESS_LOG_LEVEL")
    
    # External services
    redis_url: str = Field(default="redis://localhost:6379/0", env="ACCESS_REDIS_URL")
    clickhouse_url: str = Field(default="http://localhost:8123", env="ACCESS_CLICKHOUSE_URL")
    postgres_dsn: str = Field(default="postgres://localhost:5432/access", env="ACCESS_POSTGRES_DSN")
    kafka_bootstrap: str = Field(default="localhost:9092", env="ACCESS_KAFKA_BOOTSTRAP")
    cache_warm_concurrency: int = Field(default=5, env="ACCESS_CACHE_WARM_CONCURRENCY")
    
    # Internal services
    auth_service_url: str = Field(default="http://localhost:8010", env="ACCESS_AUTH_SERVICE_URL")
    entitlements_service_url: str = Field(default="http://localhost:8011", env="ACCESS_ENTITLEMENTS_SERVICE_URL")
    metrics_service_url: str = Field(default="http://localhost:8012", env="ACCESS_METRICS_SERVICE_URL")
    projection_service_url: str = Field(default="http://localhost:8085", env="ACCESS_PROJECTION_SERVICE_URL")

    # North America market services
    irp_service_url: str = Field(default="http://service-irpcore:8000", env="ACCESS_IRP_SERVICE_URL")
    rps_service_url: str = Field(default="http://service-rps:8000", env="ACCESS_RPS_SERVICE_URL")
    ghg_service_url: str = Field(default="http://service-ghg:8000", env="ACCESS_GHG_SERVICE_URL")
    der_service_url: str = Field(default="http://service-der:8000", env="ACCESS_DER_SERVICE_URL")
    ra_service_url: str = Field(default="http://service-ra:8000", env="ACCESS_RA_SERVICE_URL")
    rights_service_url: str = Field(default="http://service-rights:8000", env="ACCESS_RIGHTS_SERVICE_URL")
    reports_service_url: str = Field(default="http://service-reports:8000", env="ACCESS_REPORTS_SERVICE_URL")
    tasks_service_url: str = Field(default="http://service-tasks:8000", env="ACCESS_TASKS_SERVICE_URL")
    
    # Observability
    enable_tracing: bool = Field(default=False, env="ACCESS_ENABLE_TRACING")
    otel_exporter: str = Field(default="http://localhost:4318", env="ACCESS_OTEL_EXPORTER")
    enable_console_tracing: bool = Field(default=False, env="ACCESS_ENABLE_CONSOLE_TRACING")

    # Streaming service
    max_ws_connections: int = Field(default=1000, env="ACCESS_MAX_WS_CONNECTIONS")
    max_sse_connections: int = Field(default=500, env="ACCESS_MAX_SSE_CONNECTIONS")
    heartbeat_timeout: int = Field(default=30, env="ACCESS_HEARTBEAT_TIMEOUT")

    # Metrics service
    max_metric_series: int = Field(default=10000, env="ACCESS_MAX_METRIC_SERIES")
    max_points_per_series: int = Field(default=1000, env="ACCESS_MAX_POINTS_PER_SERIES")
    aggregation_window_seconds: int = Field(default=300, env="ACCESS_AGGREGATION_WINDOW_SECONDS")
    enable_console_tracing: bool = Field(default=False, env="ACCESS_ENABLE_CONSOLE_TRACING")
    
    # Security
    jwks_url: str = Field(default="http://localhost:8080/realms/254carbon/protocol/openid-connect/certs", env="ACCESS_JWKS_URL")
    
    # Rate limiting
    rate_limits_file: Optional[str] = Field(default=None, env="ACCESS_RATE_LIMITS_FILE")
    
    # TLS (future)
    tls_enabled: bool = Field(default=False, env="ACCESS_TLS_ENABLED")
    if 'SettingsConfigDict' not in globals():  # pragma: no cover - legacy pydantic v1 path
        class Config:
            env_file = ".env"
            case_sensitive = False
            extra = "allow"


class ServiceConfig(BaseConfig):
    """Service-specific configuration."""
    
    service_name: str
    port: int
    host: str = "0.0.0.0"
    
    def __init__(self, service_name: str, port: int, **kwargs):
        super().__init__(service_name=service_name, port=port, **kwargs)


def get_config(service_name: str, port: int) -> ServiceConfig:
    """Get configuration for a specific service."""
    return ServiceConfig(service_name=service_name, port=port)
