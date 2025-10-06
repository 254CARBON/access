# Metrics Service

The Metrics Service provides comprehensive metrics collection, aggregation, and export capabilities for the 254Carbon Access Layer, supporting Prometheus-compatible metrics and custom business metrics.

## Overview

The Metrics Service handles:
- **Metrics Collection** - Ingestion of custom metrics from services
- **Metrics Aggregation** - Time-series aggregation and rollup
- **Metrics Export** - Prometheus-compatible metrics export
- **Trend Analysis** - Metric trend calculation and analysis
- **Performance Monitoring** - Service performance metrics
- **Custom Metrics** - Business-specific metric collection
- **Observability** - Comprehensive monitoring and alerting

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Gateway       │───▶│   Metrics       │───▶│   Prometheus    │
│   Service       │    │   Service       │    │   (Export)      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌─────────────────┐
                       │   Aggregator    │
                       │   (Time Series) │
                       └─────────────────┘
```

## Features

### Metrics Collection
- High-throughput metric ingestion
- Multiple metric types (counter, gauge, histogram, summary)
- Label-based metric organization
- Batch metric collection
- Real-time metric processing

### Metrics Aggregation
- Time-series aggregation
- Rollup calculations
- Trend analysis
- Statistical calculations
- Configurable aggregation windows

### Metrics Export
- Prometheus-compatible export
- Multiple export formats
- Real-time and aggregated exports
- Custom metric formatting
- Export optimization

### Trend Analysis
- Metric trend calculation
- Change percentage analysis
- Anomaly detection
- Forecasting capabilities
- Trend visualization data

### Performance Monitoring
- Service performance metrics
- Resource utilization tracking
- Latency and throughput monitoring
- Error rate tracking
- Capacity planning metrics

### Custom Metrics
- Business-specific metrics
- Domain-specific measurements
- Custom aggregation functions
- Flexible metric schemas
- Multi-tenant metric isolation

### Observability
- Comprehensive monitoring
- Performance metrics
- Health checks
- Alerting support
- Dashboard integration

## API Endpoints

### Metrics Collection Endpoints

#### Track Single Metric
```http
POST /metrics/track
Content-Type: application/json

{
  "name": "api_requests_total",
  "value": 1,
  "type": "counter",
  "labels": {
    "service": "gateway",
    "endpoint": "/api/v1/instruments",
    "method": "GET",
    "status_code": "200"
  },
  "service": "gateway-service",
  "tenant_id": "tenant-1"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Metric tracked successfully"
}
```

#### Track Batch Metrics
```http
POST /metrics/track/batch
Content-Type: application/json

[
  {
    "name": "api_requests_total",
    "value": 1,
    "type": "counter",
    "labels": {
      "service": "gateway",
      "endpoint": "/api/v1/instruments"
    },
    "service": "gateway-service"
  },
  {
    "name": "response_time_seconds",
    "value": 0.042,
    "type": "histogram",
    "labels": {
      "service": "gateway",
      "endpoint": "/api/v1/instruments"
    },
    "service": "gateway-service"
  }
]
```

**Response:**
```json
{
  "success": true,
  "total": 2,
  "successful": 2,
  "failed": 0
}
```

### Metrics Export Endpoints

#### Export Metrics (Prometheus)
```http
GET /metrics?format=prometheus
```

**Response:**
```text
# HELP api_requests_total Total API requests
# TYPE api_requests_total counter
api_requests_total{service="gateway",endpoint="/api/v1/instruments",method="GET",status_code="200"} 100

# HELP response_time_seconds Response time in seconds
# TYPE response_time_seconds histogram
response_time_seconds_bucket{service="gateway",endpoint="/api/v1/instruments",le="0.005"} 0
response_time_seconds_bucket{service="gateway",endpoint="/api/v1/instruments",le="0.01"} 0
response_time_seconds_bucket{service="gateway",endpoint="/api/v1/instruments",le="0.025"} 0
response_time_seconds_bucket{service="gateway",endpoint="/api/v1/instruments",le="0.05"} 0
response_time_seconds_bucket{service="gateway",endpoint="/api/v1/instruments",le="0.1"} 0
response_time_seconds_bucket{service="gateway",endpoint="/api/v1/instruments",le="0.25"} 0
response_time_seconds_bucket{service="gateway",endpoint="/api/v1/instruments",le="0.5"} 0
response_time_seconds_bucket{service="gateway",endpoint="/api/v1/instruments",le="1"} 0
response_time_seconds_bucket{service="gateway",endpoint="/api/v1/instruments",le="2.5"} 0
response_time_seconds_bucket{service="gateway",endpoint="/api/v1/instruments",le="5"} 0
response_time_seconds_bucket{service="gateway",endpoint="/api/v1/instruments",le="10"} 0
response_time_seconds_bucket{service="gateway",endpoint="/api/v1/instruments",le="+Inf"} 100
response_time_seconds_sum{service="gateway",endpoint="/api/v1/instruments"} 4.2
response_time_seconds_count{service="gateway",endpoint="/api/v1/instruments"} 100
```

#### Export Aggregated Metrics
```http
GET /metrics?format=prometheus&aggregated=true
```

**Response:**
```text
# HELP api_requests_total_avg Average API requests per minute
# TYPE api_requests_total_avg gauge
api_requests_total_avg{service="gateway",endpoint="/api/v1/instruments"} 1.67

# HELP response_time_seconds_avg Average response time in seconds
# TYPE response_time_seconds_avg gauge
response_time_seconds_avg{service="gateway",endpoint="/api/v1/instruments"} 0.042
```

### Metrics Query Endpoints

#### Get Metric Series
```http
GET /metrics/series?service=gateway-service&limit=10
```

**Response:**
```json
{
  "series": [
    {
      "name": "api_requests_total",
      "type": "counter",
      "labels": {
        "service": "gateway",
        "endpoint": "/api/v1/instruments"
      },
      "service": "gateway-service",
      "tenant_id": "tenant-1",
      "points": [
        {
          "value": 1,
          "timestamp": "2024-01-15T10:30:00Z"
        }
      ]
    }
  ],
  "total": 1,
  "timestamp": "2024-01-15T10:30:00Z"
}
```

#### Get Metric Trends
```http
GET /metrics/trends/api_requests_total?hours=24
```

**Response:**
```json
{
  "metric_name": "api_requests_total",
  "trend": "increasing",
  "change_percent": 15.5,
  "data_points": [
    {
      "timestamp": "2024-01-14T10:30:00Z",
      "value": 85
    },
    {
      "timestamp": "2024-01-14T11:30:00Z",
      "value": 92
    },
    {
      "timestamp": "2024-01-14T12:30:00Z",
      "value": 98
    }
  ]
}
```

### Administrative Endpoints

#### Health Check
```http
GET /health
```

**Response:**
```json
{
  "service": "metrics",
  "status": "ok",
  "uptime_seconds": 5231,
  "dependencies": {
    "collector": "ok",
    "aggregator": "ok"
  },
  "version": "1.0.0",
  "commit": "abc1234"
}
```

#### Service Statistics
```http
GET /metrics/stats
```

**Response:**
```json
{
  "collector": {
    "total_points": 10000,
    "total_series": 150,
    "dropped_points": 0
  },
  "aggregator": {
    "total_windows": 24,
    "aggregated_series": 145
  },
  "exporter": {
    "total_exports": 100,
    "last_export": "2024-01-15T10:30:00Z"
  },
  "timestamp": "2024-01-15T10:30:00Z"
}
```

## Configuration

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `ACCESS_ENV` | Environment name | `local` | No |
| `ACCESS_LOG_LEVEL` | Log verbosity | `info` | No |
| `ACCESS_METRICS_ENDPOINT` | Metrics service URL | `http://localhost:8012` | Yes |
| `ACCESS_MAX_METRIC_SERIES` | Maximum metric series | `10000` | No |
| `ACCESS_MAX_POINTS_PER_SERIES` | Maximum points per series | `1000` | No |
| `ACCESS_AGGREGATION_WINDOW_SECONDS` | Aggregation window | `300` | No |
| `ACCESS_ENABLE_TRACING` | Enable distributed tracing | `false` | No |

### Collection Configuration

| Setting | Description | Default |
|---------|-------------|---------|
| `max_series` | Maximum metric series | `10000` |
| `max_points_per_series` | Maximum points per series | `1000` |
| `collection_interval` | Collection interval (seconds) | `60` |
| `batch_size` | Batch collection size | `100` |
| `timeout` | Collection timeout (seconds) | `30` |

### Aggregation Configuration

| Setting | Description | Default |
|---------|-------------|---------|
| `window_seconds` | Aggregation window | `300` |
| `retention_hours` | Data retention | `24` |
| `aggregation_types` | Aggregation types | `["avg", "sum", "min", "max"]` |
| `trend_hours` | Trend analysis window | `24` |

## Development

### Local Development

1. **Install dependencies:**
   ```bash
   pip install -r requirements-dev.txt
   ```

2. **Start the service:**
   ```bash
   cd service_metrics
   uvicorn app.main:app --reload --port 8012
   ```

3. **Run tests:**
   ```bash
   pytest tests/ -v
   ```

### Docker Development

1. **Build the image:**
   ```bash
   docker build -t metrics-service .
   ```

2. **Run the container:**
   ```bash
   docker run -p 8012:8012 \
     -e ACCESS_METRICS_ENDPOINT=http://localhost:8012 \
     metrics-service
   ```

### Testing

#### Unit Tests
```bash
pytest tests/test_collector.py -v
pytest tests/test_main.py -v
```

#### Integration Tests
```bash
pytest tests/integration/ -v
```

#### Metrics Testing
```bash
# Test metric collection
curl -X POST http://localhost:8012/metrics/track \
  -H "Content-Type: application/json" \
  -d '{
    "name": "test_metric",
    "value": 42.5,
    "type": "gauge",
    "labels": {"service": "test"},
    "service": "test-service"
  }'

# Test batch collection
curl -X POST http://localhost:8012/metrics/track/batch \
  -H "Content-Type: application/json" \
  -d '[
    {"name": "metric1", "value": 1, "type": "counter", "labels": {"service": "test"}, "service": "test-service"},
    {"name": "metric2", "value": 2.5, "type": "gauge", "labels": {"service": "test"}, "service": "test-service"}
  ]'

# Test metrics export
curl http://localhost:8012/metrics?format=prometheus
```

## Monitoring

### Metrics

The Metrics Service exposes Prometheus metrics at `/metrics`:

- `metrics_collected_total` - Total metrics collected
- `metrics_collection_duration_seconds` - Collection duration
- `metrics_series_total` - Total metric series
- `metrics_points_total` - Total metric points
- `metrics_exported_total` - Total metrics exported
- `metrics_errors_total` - Total collection errors

### Logging

Structured JSON logging with correlation IDs:

```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "level": "INFO",
  "service": "metrics",
  "trace_id": "abc123",
  "request_id": "req-456",
  "message": "Metric collected successfully",
  "metric_name": "api_requests_total",
  "service": "gateway-service"
}
```

### Health Checks

Health check endpoint provides service status:

```bash
curl http://localhost:8012/health
```

## Deployment

### Kubernetes

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: metrics-service
spec:
  replicas: 3
  selector:
    matchLabels:
      app: metrics-service
  template:
    metadata:
      labels:
        app: metrics-service
    spec:
      containers:
      - name: metrics-service
        image: ghcr.io/254carbon/access-layer-metrics:latest
        ports:
        - containerPort: 8012
        env:
        - name: ACCESS_METRICS_ENDPOINT
          value: "http://localhost:8012"
        livenessProbe:
          httpGet:
            path: /health
            port: 8012
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8012
          initialDelaySeconds: 5
          periodSeconds: 5
```

### Docker Compose

```yaml
version: '3.8'
services:
  metrics-service:
    build:
      context: .
      dockerfile: service_metrics/Dockerfile
    ports:
      - "8012:8012"
    environment:
      - ACCESS_METRICS_ENDPOINT=http://localhost:8012
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8012/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

## Troubleshooting

### Common Issues

1. **Metric Collection Failures**
   - Check metric format and validation
   - Verify service connectivity
   - Check collection limits
   - Monitor collection performance

2. **Aggregation Issues**
   - Check aggregation configuration
   - Verify time window settings
   - Monitor aggregation performance
   - Check data retention policies

3. **Export Issues**
   - Check export format compatibility
   - Verify Prometheus compatibility
   - Monitor export performance
   - Check export configuration

4. **Performance Issues**
   - Monitor collection throughput
   - Check aggregation performance
   - Monitor memory usage
   - Verify resource limits

### Debug Commands

```bash
# Check service health
curl http://localhost:8012/health

# Check service statistics
curl http://localhost:8012/metrics/stats

# Test metric collection
curl -X POST http://localhost:8012/metrics/track \
  -H "Content-Type: application/json" \
  -d '{"name": "test", "value": 1, "type": "counter", "service": "test"}'

# Test metrics export
curl http://localhost:8012/metrics?format=prometheus
```

### Log Analysis

```bash
# Filter for metric collection events
docker logs metrics-service 2>&1 | grep "metric_collected"

# Filter for aggregation events
docker logs metrics-service 2>&1 | grep "aggregation"

# Filter for export events
docker logs metrics-service 2>&1 | grep "export"

# Filter for errors
docker logs metrics-service 2>&1 | grep ERROR
```

## Performance Tuning

### Optimization Tips

1. **Collection Optimization**
   - Use batch collection
   - Implement collection batching
   - Monitor collection throughput
   - Optimize collection intervals

2. **Aggregation Optimization**
   - Use appropriate aggregation windows
   - Implement efficient aggregation
   - Monitor aggregation performance
   - Optimize aggregation algorithms

3. **Export Optimization**
   - Use efficient export formats
   - Implement export caching
   - Monitor export performance
   - Optimize export queries

4. **Memory Management**
   - Monitor memory usage
   - Implement data retention
   - Use appropriate buffer sizes
   - Monitor garbage collection

### Scaling Considerations

1. **Horizontal Scaling**
   - Deploy multiple instances
   - Use load balancer for distribution
   - Ensure stateless design
   - Share data across instances

2. **Data Management**
   - Implement data retention
   - Use efficient storage
   - Monitor storage usage
   - Implement data archiving

3. **Performance Monitoring**
   - Monitor collection performance
   - Track aggregation performance
   - Monitor export performance
   - Implement performance alerts

## Security

### Security Features

1. **Data Protection**
   - Encrypted storage
   - Secure communication
   - Access control
   - Data isolation

2. **Input Validation**
   - Metric validation
   - Label validation
   - Parameter validation
   - Format validation

3. **Access Control**
   - Service authentication
   - Tenant isolation
   - Role-based access
   - API key authentication

4. **Monitoring**
   - Security event logging
   - Access monitoring
   - Anomaly detection
   - Audit trails

### Security Best Practices

1. **Data Security**
   - Use encrypted storage
   - Implement secure communication
   - Monitor data access
   - Regular security audits

2. **Access Control**
   - Implement service authentication
   - Use tenant isolation
   - Monitor access patterns
   - Implement audit logging

3. **Monitoring**
   - Monitor security events
   - Implement alerting
   - Regular security audits
   - Monitor access patterns

## Contributing

### Development Guidelines

1. **Code Style**
   - Follow PEP 8
   - Use type hints
   - Write comprehensive tests

2. **Testing**
   - Write unit tests
   - Include integration tests
   - Maintain test coverage
   - Test performance scenarios

3. **Documentation**
   - Update API documentation
   - Include code comments
   - Update README files
   - Document performance considerations

### Pull Request Process

1. **Create Feature Branch**
   ```bash
   git checkout -b feature/new-feature
   ```

2. **Make Changes**
   - Implement feature
   - Add tests
   - Update documentation

3. **Submit Pull Request**
   - Include description
   - Reference issues
   - Request review

## License

This project is licensed under the MIT License - see the LICENSE file for details.
