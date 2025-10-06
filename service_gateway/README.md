# Gateway Service

The API Gateway service is the main entry point for the 254Carbon Access Layer, providing unified access to all platform services through a single REST API.

## Overview

The Gateway Service acts as a reverse proxy, handling:
- **Authentication** - JWT token validation and user context extraction
- **Authorization** - Entitlement checks for resource access
- **Rate Limiting** - Request throttling and abuse prevention
- **Caching** - Response caching for improved performance
- **Circuit Breaking** - Fault tolerance for downstream services
- **Request Routing** - Intelligent routing to appropriate services
- **API Versioning** - Support for multiple API versions

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Client Apps   │───▶│  Gateway Service │───▶│  Domain Services │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌─────────────────┐
                       │  Auth Service   │
                       └─────────────────┘
                              │
                              ▼
                       ┌─────────────────┐
                       │Entitlements Svc │
                       └─────────────────┘
```

## Features

### Authentication & Authorization
- JWT token validation via Auth Service
- User context extraction and propagation
- Entitlement checks for resource access
- API key authentication fallback
- Multi-tenant support

### Rate Limiting
- Token bucket algorithm implementation
- Configurable rate limits per endpoint type
- Redis-backed distributed rate limiting
- Automatic rate limit headers in responses

### Caching
- Adaptive TTL caching strategy
- Redis-backed distributed cache
- Cache warming capabilities
- Cache invalidation on data changes

### Circuit Breaking
- Hystrix-style circuit breaker pattern
- Configurable failure thresholds
- Automatic recovery testing
- Fallback responses for failed services

### Observability
- Request/response logging with correlation IDs
- Prometheus metrics collection
- Distributed tracing support
- Performance monitoring

## API Endpoints

### Core Endpoints

#### Health Check
```http
GET /health
```

**Response:**
```json
{
  "service": "gateway",
  "status": "ok",
  "uptime_seconds": 5231,
  "dependencies": {
    "redis": "ok",
    "auth": "ok",
    "entitlements": "ok"
  },
  "version": "1.0.0",
  "commit": "abc1234"
}
```

#### API Status
```http
GET /api/v1/status
```

**Response:**
```json
{
  "status": "operational",
  "version": "1.0.0",
  "services": {
    "gateway": "ok",
    "auth": "ok",
    "entitlements": "ok",
    "streaming": "ok",
    "metrics": "ok"
  }
}
```

### Data Endpoints

#### Instruments
```http
GET /api/v1/instruments
Authorization: Bearer <jwt-token>
```

**Response:**
```json
{
  "instruments": [
    {
      "id": "EURUSD",
      "name": "Euro/US Dollar",
      "type": "forex"
    },
    {
      "id": "GBPUSD",
      "name": "British Pound/US Dollar",
      "type": "forex"
    }
  ],
  "cached": false,
  "user": "user-123",
  "tenant": "tenant-1"
}
```

#### Curves
```http
GET /api/v1/curves
Authorization: Bearer <jwt-token>
```

**Response:**
```json
{
  "curves": [
    {
      "id": "USD_CURVE",
      "name": "USD Yield Curve",
      "currency": "USD"
    },
    {
      "id": "EUR_CURVE",
      "name": "EUR Yield Curve",
      "currency": "EUR"
    }
  ],
  "cached": false,
  "user": "user-123",
  "tenant": "tenant-1"
}
```

#### Products
```http
GET /api/v1/products
Authorization: Bearer <jwt-token>
```

**Response:**
```json
{
  "products": [
    {
      "id": "PROD001",
      "name": "Oil Futures",
      "type": "commodity",
      "commodity": "oil"
    },
    {
      "id": "PROD002",
      "name": "Gas Futures",
      "type": "commodity",
      "commodity": "gas"
    }
  ],
  "cached": false,
  "user": "user-123",
  "tenant": "tenant-1"
}
```

#### Pricing Data
```http
GET /api/v1/pricing
Authorization: Bearer <jwt-token>
```

**Response:**
```json
{
  "pricing": [
    {
      "instrument_id": "INST001",
      "price": 52.50,
      "volume": 1000,
      "timestamp": "2024-01-01T12:00:00Z"
    },
    {
      "instrument_id": "INST002",
      "price": 45.20,
      "volume": 1500,
      "timestamp": "2024-01-01T12:00:00Z"
    }
  ],
  "cached": false,
  "user": "user-123",
  "tenant": "tenant-1"
}
```

#### Historical Data
```http
GET /api/v1/historical
Authorization: Bearer <jwt-token>
```

**Response:**
```json
{
  "historical": [
    {
      "instrument_id": "INST001",
      "price": 52.50,
      "volume": 1000,
      "timestamp": "2024-01-01T12:00:00Z"
    },
    {
      "instrument_id": "INST001",
      "price": 52.45,
      "volume": 1200,
      "timestamp": "2024-01-01T11:00:00Z"
    }
  ],
  "cached": false,
  "user": "user-123",
  "tenant": "tenant-1"
}
```

### Administrative Endpoints

#### Cache Management
```http
POST /api/v1/cache/warm
Authorization: Bearer <jwt-token>
```

**Response:**
```json
{
  "message": "Cache warmed successfully",
  "user": "user-123",
  "tenant": "tenant-1"
}
```

#### Cache Statistics
```http
GET /api/v1/cache/stats
```

**Response:**
```json
{
  "hit_ratio": 0.85,
  "total_requests": 1000,
  "cache_hits": 850,
  "cache_misses": 150,
  "memory_usage": "50MB"
}
```

#### Rate Limit Status
```http
GET /api/v1/rate-limits
```

**Response:**
```json
{
  "rate_limits": {
    "total_clients": 10,
    "total_requests": 1000,
    "blocked_requests": 50
  },
  "configured_limits": {
    "public": 100,
    "authenticated": 1000,
    "heavy": 10,
    "admin": 5
  }
}
```

#### Circuit Breaker Status
```http
GET /api/v1/circuit-breakers
```

**Response:**
```json
{
  "circuit_breakers": {
    "auth_service": {
      "state": "closed",
      "failure_count": 0,
      "success_count": 100
    },
    "entitlements_service": {
      "state": "closed",
      "failure_count": 0,
      "success_count": 100
    }
  },
  "count": 2
}
```

### Authentication Endpoints

#### API Key Authentication
```http
GET /api/v1/auth/api-key
X-API-Key: <api-key>
```

**Response:**
```json
{
  "authenticated": true,
  "user_info": {
    "user_id": "api-key-dev-key-123",
    "tenant_id": "tenant-1",
    "roles": ["user"],
    "auth_method": "api_key"
  },
  "expires_in": 3600
}
```

### Fallback Endpoints

#### Fallback Instruments
```http
GET /api/v1/instruments/fallback
```

**Response:**
```json
{
  "instruments": [
    {
      "id": "EURUSD",
      "name": "Euro/US Dollar (Cached)",
      "type": "forex"
    }
  ],
  "fallback": true,
  "message": "Service temporarily unavailable, showing cached data",
  "timestamp": 1705312200
}
```

## Configuration

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `ACCESS_ENV` | Environment name | `local` | No |
| `ACCESS_LOG_LEVEL` | Log verbosity | `info` | No |
| `ACCESS_REDIS_URL` | Redis connection URL | `redis://localhost:6379/0` | Yes |
| `ACCESS_AUTH_SERVICE_URL` | Auth service URL | `http://localhost:8010` | Yes |
| `ACCESS_ENTITLEMENTS_SERVICE_URL` | Entitlements service URL | `http://localhost:8011` | Yes |
| `ACCESS_METRICS_ENDPOINT` | Metrics service URL | `http://localhost:8012` | Yes |
| `ACCESS_CLICKHOUSE_URL` | ClickHouse URL | `http://localhost:8123` | No |
| `ACCESS_ENABLE_TRACING` | Enable distributed tracing | `false` | No |
| `ACCESS_OTEL_EXPORTER` | OpenTelemetry exporter URL | - | No |

### Rate Limiting Configuration

| Endpoint Type | Rate Limit | Description |
|---------------|------------|-------------|
| `public` | 100 req/min | Health & metadata endpoints |
| `authenticated` | 1000 req/min | Standard REST endpoints |
| `heavy` | 10 req/min | Data intensive operations |
| `admin` | 5 req/min | Administrative operations |

### Caching Configuration

| Cache Type | TTL | Description |
|------------|-----|-------------|
| `instruments` | 60s | Instrument metadata |
| `curves` | 30s | Yield curve data |
| `products` | 120s | Product information |
| `pricing` | 10s | Real-time pricing data |
| `historical` | 300s | Historical data |

## Development

### Local Development

1. **Install dependencies:**
   ```bash
   pip install -r requirements-dev.txt
   ```

2. **Start the service:**
   ```bash
   cd service_gateway
   uvicorn app.main:app --reload --port 8000
   ```

3. **Run tests:**
   ```bash
   pytest tests/ -v
   ```

### Docker Development

1. **Build the image:**
   ```bash
   docker build -t gateway-service .
   ```

2. **Run the container:**
   ```bash
   docker run -p 8000:8000 \
     -e ACCESS_REDIS_URL=redis://localhost:6379/0 \
     -e ACCESS_AUTH_SERVICE_URL=http://localhost:8010 \
     -e ACCESS_ENTITLEMENTS_SERVICE_URL=http://localhost:8011 \
     gateway-service
   ```

### Testing

#### Unit Tests
```bash
pytest tests/test_auth_client.py -v
pytest tests/test_cache_manager.py -v
pytest tests/test_rate_limiter.py -v
pytest tests/test_main.py -v
```

#### Integration Tests
```bash
pytest tests/integration/ -v
```

#### Load Testing
```bash
# Install locust
pip install locust

# Run load tests
locust -f tests/performance/locustfile.py \
  --host=http://localhost:8000 \
  --users=100 \
  --spawn-rate=10 \
  --run-time=5m
```

## Monitoring

### Metrics

The Gateway Service exposes Prometheus metrics at `/metrics`:

- `http_requests_total` - Total HTTP requests
- `http_request_duration_seconds` - Request duration histogram
- `cache_hits_total` - Cache hit counter
- `cache_misses_total` - Cache miss counter
- `rate_limit_exceeded_total` - Rate limit violations
- `circuit_breaker_state` - Circuit breaker state gauge

### Logging

Structured JSON logging with correlation IDs:

```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "level": "INFO",
  "service": "gateway",
  "trace_id": "abc123",
  "request_id": "req-456",
  "message": "GET /api/v1/instruments 200 42ms",
  "user_id": "user-123",
  "tenant_id": "tenant-1"
}
```

### Health Checks

Health check endpoint provides service status:

```bash
curl http://localhost:8000/health
```

## Deployment

### Kubernetes

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: gateway-service
spec:
  replicas: 3
  selector:
    matchLabels:
      app: gateway-service
  template:
    metadata:
      labels:
        app: gateway-service
    spec:
      containers:
      - name: gateway-service
        image: ghcr.io/254carbon/access-layer-gateway:latest
        ports:
        - containerPort: 8000
        env:
        - name: ACCESS_REDIS_URL
          value: "redis://redis-service:6379/0"
        - name: ACCESS_AUTH_SERVICE_URL
          value: "http://auth-service:8010"
        - name: ACCESS_ENTITLEMENTS_SERVICE_URL
          value: "http://entitlements-service:8011"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
```

### Docker Compose

```yaml
version: '3.8'
services:
  gateway-service:
    build:
      context: .
      dockerfile: service_gateway/Dockerfile
    ports:
      - "8000:8000"
    environment:
      - ACCESS_REDIS_URL=redis://redis:6379/0
      - ACCESS_AUTH_SERVICE_URL=http://auth-service:8010
      - ACCESS_ENTITLEMENTS_SERVICE_URL=http://entitlements-service:8011
    depends_on:
      - redis
      - auth-service
      - entitlements-service
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

## Troubleshooting

### Common Issues

1. **Authentication Failures**
   - Check JWT token validity
   - Verify Auth Service connectivity
   - Check JWKS endpoint accessibility

2. **Rate Limiting Issues**
   - Monitor rate limit headers
   - Check Redis connectivity
   - Verify rate limit configuration

3. **Cache Issues**
   - Check Redis connectivity
   - Monitor cache hit ratios
   - Verify cache key generation

4. **Circuit Breaker Issues**
   - Check downstream service health
   - Monitor failure rates
   - Verify circuit breaker configuration

### Debug Commands

```bash
# Check service health
curl http://localhost:8000/health

# Check cache statistics
curl http://localhost:8000/api/v1/cache/stats

# Check rate limit status
curl http://localhost:8000/api/v1/rate-limits

# Check circuit breaker status
curl http://localhost:8000/api/v1/circuit-breakers
```

### Log Analysis

```bash
# Filter for errors
docker logs gateway-service 2>&1 | grep ERROR

# Filter for slow requests
docker logs gateway-service 2>&1 | grep "slow request"

# Filter for authentication issues
docker logs gateway-service 2>&1 | grep "auth"
```

## Performance Tuning

### Optimization Tips

1. **Caching**
   - Enable caching for frequently accessed data
   - Use appropriate TTL values
   - Implement cache warming

2. **Rate Limiting**
   - Adjust rate limits based on usage patterns
   - Use Redis for distributed rate limiting
   - Monitor rate limit violations

3. **Circuit Breaking**
   - Configure appropriate failure thresholds
   - Use fallback responses
   - Monitor circuit breaker states

4. **Connection Pooling**
   - Use connection pooling for downstream services
   - Configure appropriate pool sizes
   - Monitor connection usage

### Scaling Considerations

1. **Horizontal Scaling**
   - Deploy multiple instances
   - Use load balancer for distribution
   - Ensure stateless design

2. **Caching Strategy**
   - Use distributed cache (Redis)
   - Implement cache invalidation
   - Monitor cache performance

3. **Database Optimization**
   - Use connection pooling
   - Optimize queries
   - Monitor database performance

## Security

### Security Features

1. **Authentication**
   - JWT token validation
   - API key authentication
   - Multi-tenant support

2. **Authorization**
   - Entitlement checks
   - Resource-level permissions
   - Role-based access control

3. **Rate Limiting**
   - Request throttling
   - Abuse prevention
   - DDoS protection

4. **Input Validation**
   - Request validation
   - SQL injection prevention
   - XSS protection

### Security Best Practices

1. **Token Management**
   - Use short-lived tokens
   - Implement token refresh
   - Secure token storage

2. **Network Security**
   - Use HTTPS in production
   - Implement network policies
   - Use secure communication

3. **Monitoring**
   - Monitor security events
   - Implement alerting
   - Regular security audits

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

3. **Documentation**
   - Update API documentation
   - Include code comments
   - Update README files

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
