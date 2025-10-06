"""
Shared configuration management for 254Carbon Access Layer.
"""

import os
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings


class BaseConfig(BaseSettings):
    """Base configuration class with common settings."""
    
    # Environment
    env: str = Field(default="local", env="ACCESS_ENV")
    log_level: str = Field(default="info", env="ACCESS_LOG_LEVEL")
    
    # External services
    redis_url: str = Field(default="redis://localhost:6379/0", env="ACCESS_REDIS_URL")
    clickhouse_url: str = Field(default="http://localhost:8123", env="ACCESS_CLICKHOUSE_URL")
    postgres_dsn: str = Field(default="postgres://localhost:5432/access", env="ACCESS_POSTGRES_DSN")
    kafka_bootstrap: str = Field(default="localhost:9092", env="ACCESS_KAFKA_BOOTSTRAP")
    
    # Internal services
    auth_service_url: str = Field(default="http://localhost:8010", env="ACCESS_AUTH_SERVICE_URL")
    entitlements_service_url: str = Field(default="http://localhost:8011", env="ACCESS_ENTITLEMENTS_SERVICE_URL")
    metrics_service_url: str = Field(default="http://localhost:8012", env="ACCESS_METRICS_SERVICE_URL")
    
    # Observability
    enable_tracing: bool = Field(default=True, env="ACCESS_ENABLE_TRACING")
    otel_exporter: str = Field(default="http://localhost:4318", env="ACCESS_OTEL_EXPORTER")
    
    # Security
    jwks_url: str = Field(default="http://localhost:8080/realms/254carbon/protocol/openid-connect/certs", env="ACCESS_JWKS_URL")
    
    # Rate limiting
    rate_limits_file: Optional[str] = Field(default=None, env="ACCESS_RATE_LIMITS_FILE")
    
    # TLS (future)
    tls_enabled: bool = Field(default=False, env="ACCESS_TLS_ENABLED")
    
    class Config:
        env_file = ".env"
        case_sensitive = False


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
