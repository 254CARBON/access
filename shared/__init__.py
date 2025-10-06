"""
Shared utilities for the 254Carbon Access Layer.

This package aggregates common building blocks consumed by all services:

- config: Service configuration via pydantic-settings
- logging: Structured logging with trace correlation
- metrics: Prometheus metrics helpers
- tracing: OpenTelemetry tracing config
- errors: Canonical error types and responses
- retry: Retry decorators and management
- circuit_breaker: Resilient external call protection

Any cross-service logic should live here to avoid import cycles across
service packages. Do not import from service-* packages into shared/.
"""
