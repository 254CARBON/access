# Observability Guide for 254Carbon Access Layer

This document provides comprehensive guidance on the observability features implemented in the 254Carbon Access Layer.

## Overview

The Access Layer implements a comprehensive observability stack including:

- **Structured Logging**: JSON-formatted logs with correlation IDs
- **Metrics Collection**: Prometheus-compatible metrics with business event tracking
- **Distributed Tracing**: OpenTelemetry-based tracing with Jaeger integration
- **Health Monitoring**: Service health checks and dependency monitoring

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Application   │    │   Observability │    │   Monitoring    │
│     Services    │───▶│     Manager     │───▶│     Stack       │
│                 │    │                 │    │                 │
│ • Gateway       │    │ • Logging       │    │ • Prometheus    │
│ • Auth          │    │ • Metrics       │    │ • Grafana       │
│ • Streaming     │    │ • Tracing      │    │ • Jaeger        │
│ • Entitlements  │    │                 │    │                 │
│ • Metrics       │    │                 │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## Components

### 1. Structured Logging

**Features:**
- JSON-formatted logs for easy parsing
- Correlation IDs (request_id, user_id, tenant_id)
- Trace context injection
- High-precision timestamps
- Service context

**Configuration:**
```python
from shared.observability import get_observability_manager

observability = get_observability_manager(
    "service-name",
    log_level="info",
    otel_exporter="http://jaeger:14268/api/traces",
    enable_console=True
)
```

**Usage:**
```python
# Business event logging
observability.log_business_event(
    "user_authenticated",
    user_id="user123",
    tenant_id="tenant456"
)

# Error logging
observability.log_error(
    "authentication_failed",
    "Invalid token",
    user_id="user123"
)
```

### 2. Metrics Collection

**Features:**
- Prometheus-compatible metrics
- HTTP request metrics (rate, duration, status codes)
- Business event counters
- Error tracking
- Custom metrics support

**Available Metrics:**
- `http_requests_total`: Total HTTP requests by method, endpoint, status
- `http_request_duration_seconds`: Request duration histogram
- `errors_total`: Error counts by type and service
- `business_events_total`: Business event counts
- `health_check_total`: Health check requests
- `service_info`: Service metadata

**Usage:**
```python
# Record business event
observability.log_business_event("cache_hit", cache_type="instruments")

# Record error
observability.log_error("validation_error", "Invalid input")

# Measure operation
with observability.measure_operation("database_query"):
    result = await database.query()
```

### 3. Distributed Tracing

**Features:**
- OpenTelemetry integration
- Automatic instrumentation for FastAPI, Redis, SQLAlchemy, HTTPX, Kafka
- Custom span creation
- Trace context propagation
- Jaeger visualization

**Configuration:**
```python
# Environment variables
OTEL_EXPORTER=http://jaeger:14268/api/traces
ENABLE_CONSOLE_TRACING=true
TRACE_SAMPLING_RATE=1.0
```

**Usage:**
```python
# Function decoration
@observe_function("operation_name")
async def my_function():
    pass

# Context manager
with observe_operation("database_query", query="SELECT * FROM users"):
    result = await database.execute()
```

## Service Integration

### Gateway Service

**Observability Features:**
- Request/response logging with correlation IDs
- Rate limiting metrics
- Cache hit/miss tracking
- Authentication event logging
- Error tracking with context

**Key Metrics:**
- `gateway_requests_total`
- `gateway_cache_hits_total`
- `gateway_rate_limit_violations_total`
- `gateway_auth_events_total`

### Auth Service

**Observability Features:**
- Token verification tracking
- User authentication events
- JWKS cache performance
- Error logging with user context

**Key Metrics:**
- `auth_token_verifications_total`
- `auth_jwks_cache_hits_total`
- `auth_errors_total`
- `auth_user_events_total`

### Streaming Service

**Observability Features:**
- WebSocket connection tracking
- Message processing metrics
- Kafka integration monitoring
- Subscription management events

**Key Metrics:**
- `streaming_websocket_connections_active`
- `streaming_messages_processed_total`
- `streaming_kafka_events_total`
- `streaming_subscriptions_total`

### Entitlements Service

**Observability Features:**
- Rule evaluation tracking
- Cache performance monitoring
- Access decision logging
- Performance metrics

**Key Metrics:**
- `entitlements_checks_total`
- `entitlements_cache_hits_total`
- `entitlements_rule_evaluations_total`
- `entitlements_access_decisions_total`

### Metrics Service

**Observability Features:**
- Metric ingestion tracking
- Aggregation performance
- Export monitoring
- Storage metrics

**Key Metrics:**
- `metrics_ingested_total`
- `metrics_aggregated_total`
- `metrics_exported_total`
- `metrics_storage_usage_bytes`

## Monitoring Stack

### Prometheus

**Configuration:**
```yaml
# monitoring/prometheus.yml
scrape_configs:
  - job_name: 'gateway'
    static_configs:
      - targets: ['gateway:8000']
    metrics_path: '/metrics'
    scrape_interval: 10s
```

**Access:** http://localhost:9090

### Grafana

**Dashboards:**
- Access Layer Overview
- Service Health Monitoring
- Performance Metrics
- Error Rate Tracking
- Business Event Analytics

**Access:** http://localhost:3000
**Default Credentials:** admin/admin

### Jaeger

**Features:**
- Distributed trace visualization
- Service dependency mapping
- Performance analysis
- Error tracking

**Access:** http://localhost:16686

## Configuration

### Environment Variables

```bash
# Logging
LOG_LEVEL=info
LOG_FORMAT=json
ENABLE_CONSOLE_LOGGING=true

# Metrics
ENABLE_METRICS=true
METRICS_PORT=9090
METRICS_PATH=/metrics

# Tracing
ENABLE_TRACING=true
OTEL_EXPORTER=http://jaeger:14268/api/traces
ENABLE_CONSOLE_TRACING=false
TRACE_SAMPLING_RATE=1.0

# Service
SERVICE_NAME=gateway
SERVICE_VERSION=1.0.0
ACCESS_ENV=production
```

### Docker Compose

```yaml
services:
  gateway-service:
    environment:
      - OTEL_EXPORTER=http://jaeger:14268/api/traces
      - ENABLE_CONSOLE_TRACING=false
      - LOG_LEVEL=info
      - ENABLE_METRICS=true
      - METRICS_PORT=9090
```

## Best Practices

### 1. Logging

- Use structured logging with consistent field names
- Include correlation IDs in all log entries
- Log business events for audit trails
- Use appropriate log levels (DEBUG, INFO, WARN, ERROR)

### 2. Metrics

- Define meaningful metric names
- Use consistent label names across services
- Monitor business KPIs, not just technical metrics
- Set up alerts for critical metrics

### 3. Tracing

- Use descriptive operation names
- Add relevant attributes to spans
- Trace critical business operations
- Monitor trace sampling rates

### 4. Health Checks

- Implement comprehensive health checks
- Monitor external dependencies
- Provide detailed health status
- Set up alerting for health failures

## Troubleshooting

### Common Issues

1. **Missing Traces**
   - Check OTEL_EXPORTER configuration
   - Verify Jaeger is running and accessible
   - Check trace sampling rate

2. **Missing Metrics**
   - Verify Prometheus configuration
   - Check service metrics endpoints
   - Ensure metrics are being collected

3. **Log Parsing Issues**
   - Verify JSON format consistency
   - Check log level configuration
   - Ensure proper field naming

### Debug Commands

```bash
# Check service health
curl http://localhost:8000/health

# View metrics
curl http://localhost:8000/metrics

# Check Prometheus targets
curl http://localhost:9090/api/v1/targets

# View Jaeger services
curl http://localhost:16686/api/services
```

## Performance Considerations

- **Logging**: Use async logging to avoid blocking
- **Metrics**: Batch metric updates when possible
- **Tracing**: Adjust sampling rates based on load
- **Storage**: Configure retention policies appropriately

## Security

- **Logs**: Avoid logging sensitive data (passwords, tokens)
- **Metrics**: Sanitize metric labels
- **Traces**: Filter sensitive information from spans
- **Access**: Secure monitoring endpoints

## Future Enhancements

- **Log Aggregation**: ELK stack integration
- **Advanced Metrics**: Custom business metrics
- **Trace Analysis**: Automated anomaly detection
- **Alerting**: Intelligent alerting rules
- **Dashboards**: Custom service-specific dashboards
