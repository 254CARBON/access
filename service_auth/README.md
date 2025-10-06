# Auth Service

The Auth Service provides authentication and authorization capabilities for the 254Carbon Access Layer, handling JWT token validation and user context extraction.

## Overview

The Auth Service handles:
- **JWT Token Validation** - Token signature verification and claims extraction
- **JWKS Integration** - JSON Web Key Set management for token validation
- **User Context Extraction** - User information extraction from tokens
- **Token Management** - Token refresh and validation lifecycle
- **Multi-tenant Support** - Tenant-specific authentication
- **Caching** - JWKS caching for improved performance
- **Observability** - Authentication metrics and logging

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Gateway       │───▶│   Auth Service  │───▶│   Keycloak      │
│   Service       │    │                 │    │   (JWKS)        │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌─────────────────┐
                       │   Streaming     │
                       │   Service       │
                       └─────────────────┘
```

## Features

### JWT Token Validation
- Token signature verification using JWKS
- Claims validation and extraction
- Token expiration checking
- Algorithm validation (RS256, HS256)

### JWKS Management
- JSON Web Key Set caching
- Automatic key rotation support
- Key validation and verification
- Performance optimization

### User Context Extraction
- User ID extraction from tokens
- Tenant ID extraction
- Role and permission extraction
- Custom claims support

### Token Management
- Token refresh support
- Token validation lifecycle
- Token blacklisting (future)
- Session management

### Multi-tenant Support
- Tenant-specific validation
- Tenant context extraction
- Cross-tenant isolation
- Tenant-specific configurations

### Caching
- JWKS caching for performance
- Token validation result caching
- Configurable cache TTL
- Cache invalidation strategies

### Observability
- Authentication metrics
- Token validation logging
- Performance monitoring
- Health checks

## API Endpoints

### Authentication Endpoints

#### Verify Token (REST)
```http
POST /auth/verify
Content-Type: application/json

{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response:**
```json
{
  "valid": true,
  "claims": {
    "sub": "user-123",
    "tenant_id": "tenant-1",
    "roles": ["user", "analyst"],
    "iat": 1705312200,
    "exp": 1705315800
  },
  "user_info": {
    "user_id": "user-123",
    "tenant_id": "tenant-1",
    "roles": ["user", "analyst"],
    "email": "user@example.com"
  }
}
```

#### Verify Token (WebSocket)
```http
POST /auth/verify-ws
Content-Type: application/json

{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response:**
```json
{
  "valid": true,
  "claims": {
    "sub": "user-123",
    "tenant_id": "tenant-1",
    "roles": ["user", "analyst"],
    "iat": 1705312200,
    "exp": 1705315800
  },
  "user_info": {
    "user_id": "user-123",
    "tenant_id": "tenant-1",
    "roles": ["user", "analyst"],
    "email": "user@example.com"
  }
}
```

#### Refresh Token
```http
POST /auth/refresh
Content-Type: application/json

{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response:**
```json
{
  "success": true,
  "new_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "expires_in": 3600
}
```

#### Logout
```http
POST /auth/logout
Content-Type: application/json

{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response:**
```json
{
  "success": true,
  "message": "Token invalidated successfully"
}
```

### User Management Endpoints

#### Get User Information
```http
GET /auth/users/{user_id}
```

**Response:**
```json
{
  "user_id": "user-123",
  "username": "john.doe",
  "email": "john.doe@example.com",
  "tenant_id": "tenant-1",
  "roles": ["user", "analyst"],
  "created_at": "2024-01-01T00:00:00Z",
  "last_login": "2024-01-15T10:30:00Z",
  "status": "active"
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
  "service": "auth",
  "status": "ok",
  "uptime_seconds": 5231,
  "dependencies": {
    "jwks": "ok",
    "redis": "ok"
  },
  "version": "1.0.0",
  "commit": "abc1234"
}
```

#### Service Status
```http
GET /
```

**Response:**
```json
{
  "service": "auth",
  "message": "254Carbon Access Layer - Auth Service",
  "capabilities": [
    "jwt_validation",
    "jwks_management",
    "user_context",
    "multi_tenant"
  ],
  "version": "1.0.0"
}
```

## Configuration

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `ACCESS_ENV` | Environment name | `local` | No |
| `ACCESS_LOG_LEVEL` | Log verbosity | `info` | No |
| `ACCESS_JWKS_URL` | JWKS endpoint URL | `http://localhost:8080/realms/254carbon/protocol/openid-connect/certs` | Yes |
| `ACCESS_REDIS_URL` | Redis connection URL | `redis://localhost:6379/0` | Yes |
| `ACCESS_METRICS_ENDPOINT` | Metrics service URL | `http://localhost:8012` | Yes |
| `ACCESS_JWKS_CACHE_TTL` | JWKS cache TTL (seconds) | `3600` | No |
| `ACCESS_TOKEN_CACHE_TTL` | Token cache TTL (seconds) | `300` | No |
| `ACCESS_ENABLE_TRACING` | Enable distributed tracing | `false` | No |

### JWKS Configuration

| Setting | Description | Default |
|---------|-------------|---------|
| `jwks_url` | JWKS endpoint URL | Required |
| `cache_ttl` | Cache TTL in seconds | `3600` |
| `timeout` | Request timeout in seconds | `10` |
| `retry_attempts` | Retry attempts | `3` |
| `retry_delay` | Retry delay in seconds | `1` |

### Token Validation Configuration

| Setting | Description | Default |
|---------|-------------|---------|
| `algorithms` | Allowed algorithms | `["RS256", "HS256"]` |
| `issuer` | Expected issuer | Required |
| `audience` | Expected audience | Required |
| `clock_skew` | Clock skew tolerance (seconds) | `60` |

## Development

### Local Development

1. **Install dependencies:**
   ```bash
   pip install -r requirements-dev.txt
   ```

2. **Start the service:**
   ```bash
   cd service_auth
   uvicorn app.main:app --reload --port 8010
   ```

3. **Run tests:**
   ```bash
   pytest tests/ -v
   ```

### Docker Development

1. **Build the image:**
   ```bash
   docker build -t auth-service .
   ```

2. **Run the container:**
   ```bash
   docker run -p 8010:8010 \
     -e ACCESS_JWKS_URL=http://localhost:8080/realms/254carbon/protocol/openid-connect/certs \
     -e ACCESS_REDIS_URL=redis://localhost:6379/0 \
     auth-service
   ```

### Testing

#### Unit Tests
```bash
pytest tests/test_token_validator.py -v
pytest tests/test_jwks_client.py -v
pytest tests/test_main.py -v
```

#### Integration Tests
```bash
pytest tests/integration/ -v
```

#### Token Validation Testing
```bash
# Test token validation
curl -X POST http://localhost:8010/auth/verify \
  -H "Content-Type: application/json" \
  -d '{"token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."}'

# Test WebSocket token validation
curl -X POST http://localhost:8010/auth/verify-ws \
  -H "Content-Type: application/json" \
  -d '{"token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."}'
```

## Monitoring

### Metrics

The Auth Service exposes Prometheus metrics at `/metrics`:

- `auth_token_validations_total` - Total token validations
- `auth_token_validation_duration_seconds` - Token validation duration
- `auth_jwks_requests_total` - Total JWKS requests
- `auth_jwks_cache_hits_total` - JWKS cache hits
- `auth_jwks_cache_misses_total` - JWKS cache misses
- `auth_errors_total` - Total authentication errors

### Logging

Structured JSON logging with correlation IDs:

```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "level": "INFO",
  "service": "auth",
  "trace_id": "abc123",
  "request_id": "req-456",
  "message": "Token validation successful",
  "user_id": "user-123",
  "tenant_id": "tenant-1"
}
```

### Health Checks

Health check endpoint provides service status:

```bash
curl http://localhost:8010/health
```

## Deployment

### Kubernetes

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: auth-service
spec:
  replicas: 3
  selector:
    matchLabels:
      app: auth-service
  template:
    metadata:
      labels:
        app: auth-service
    spec:
      containers:
      - name: auth-service
        image: ghcr.io/254carbon/access-layer-auth:latest
        ports:
        - containerPort: 8010
        env:
        - name: ACCESS_JWKS_URL
          value: "http://keycloak:8080/realms/254carbon/protocol/openid-connect/certs"
        - name: ACCESS_REDIS_URL
          value: "redis://redis-service:6379/0"
        livenessProbe:
          httpGet:
            path: /health
            port: 8010
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8010
          initialDelaySeconds: 5
          periodSeconds: 5
```

### Docker Compose

```yaml
version: '3.8'
services:
  auth-service:
    build:
      context: .
      dockerfile: service_auth/Dockerfile
    ports:
      - "8010:8010"
    environment:
      - ACCESS_JWKS_URL=http://keycloak:8080/realms/254carbon/protocol/openid-connect/certs
      - ACCESS_REDIS_URL=redis://redis:6379/0
    depends_on:
      - redis
      - keycloak
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8010/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

## Troubleshooting

### Common Issues

1. **Token Validation Failures**
   - Check JWKS endpoint accessibility
   - Verify token format and claims
   - Check token expiration
   - Validate algorithm support

2. **JWKS Issues**
   - Check JWKS endpoint connectivity
   - Verify key format and rotation
   - Monitor cache performance
   - Check network connectivity

3. **Performance Issues**
   - Monitor JWKS cache hit ratio
   - Check token validation latency
   - Monitor Redis connectivity
   - Verify key rotation frequency

4. **Authentication Errors**
   - Check token claims validity
   - Verify issuer and audience
   - Check clock synchronization
   - Validate algorithm support

### Debug Commands

```bash
# Check service health
curl http://localhost:8010/health

# Test token validation
curl -X POST http://localhost:8010/auth/verify \
  -H "Content-Type: application/json" \
  -d '{"token": "test-token"}'

# Check JWKS endpoint
curl http://localhost:8080/realms/254carbon/protocol/openid-connect/certs
```

### Log Analysis

```bash
# Filter for token validation events
docker logs auth-service 2>&1 | grep "token_validation"

# Filter for JWKS events
docker logs auth-service 2>&1 | grep "jwks"

# Filter for errors
docker logs auth-service 2>&1 | grep ERROR

# Filter for cache events
docker logs auth-service 2>&1 | grep "cache"
```

## Performance Tuning

### Optimization Tips

1. **JWKS Caching**
   - Enable JWKS caching
   - Use appropriate cache TTL
   - Monitor cache hit ratio
   - Implement cache warming

2. **Token Validation**
   - Cache validation results
   - Use appropriate cache TTL
   - Monitor validation latency
   - Optimize validation logic

3. **Connection Pooling**
   - Use connection pooling for Redis
   - Configure appropriate pool sizes
   - Monitor connection usage
   - Implement connection health checks

4. **Memory Management**
   - Monitor memory usage
   - Implement cache eviction
   - Use appropriate buffer sizes
   - Monitor garbage collection

### Scaling Considerations

1. **Horizontal Scaling**
   - Deploy multiple instances
   - Use load balancer for distribution
   - Ensure stateless design
   - Share cache across instances

2. **Caching Strategy**
   - Use distributed cache (Redis)
   - Implement cache invalidation
   - Monitor cache performance
   - Use appropriate cache TTL

3. **JWKS Management**
   - Monitor key rotation
   - Implement key validation
   - Use appropriate cache TTL
   - Monitor JWKS performance

## Security

### Security Features

1. **Token Validation**
   - Signature verification
   - Claims validation
   - Expiration checking
   - Algorithm validation

2. **JWKS Security**
   - Key validation
   - Key rotation support
   - Secure key storage
   - Key integrity checking

3. **Caching Security**
   - Secure cache storage
   - Cache invalidation
   - Access control
   - Data encryption

4. **Input Validation**
   - Token format validation
   - Claims validation
   - Parameter validation
   - SQL injection prevention

### Security Best Practices

1. **Token Management**
   - Use short-lived tokens
   - Implement token refresh
   - Secure token storage
   - Monitor token usage

2. **JWKS Security**
   - Use HTTPS for JWKS endpoint
   - Implement key rotation
   - Monitor key changes
   - Validate key integrity

3. **Network Security**
   - Use HTTPS in production
   - Implement network policies
   - Use secure communication
   - Monitor network traffic

4. **Monitoring**
   - Monitor security events
   - Implement alerting
   - Regular security audits
   - Monitor authentication patterns

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
   - Test security scenarios

3. **Documentation**
   - Update API documentation
   - Include code comments
   - Update README files
   - Document security considerations

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
