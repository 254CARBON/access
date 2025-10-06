# Entitlements Service

The Entitlements Service provides fine-grained access control for the 254Carbon Access Layer, implementing a rule-based authorization system with caching and persistence.

## Overview

The Entitlements Service handles:
- **Rule-Based Authorization** - Flexible rule engine for access control
- **Rule Management** - CRUD operations for entitlement rules
- **Caching** - Redis-backed caching for performance
- **Persistence** - PostgreSQL storage for rule definitions
- **Multi-tenant Support** - Tenant-specific rule isolation
- **Performance Optimization** - High-throughput entitlement checks
- **Observability** - Authorization metrics and logging

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Gateway       │───▶│  Entitlements   │───▶│   PostgreSQL    │
│   Service       │    │   Service       │    │   Database      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌─────────────────┐
                       │     Redis       │
                       │    (Cache)      │
                       └─────────────────┘
```

## Features

### Rule Engine
- Flexible rule evaluation engine
- Support for complex conditions
- Priority-based rule ordering
- Rule expiration and disabling
- Performance-optimized evaluation

### Rule Management
- CRUD operations for rules
- Rule validation and testing
- Rule versioning and history
- Bulk rule operations
- Rule import/export

### Caching
- Redis-backed result caching
- Configurable cache TTL
- Cache invalidation strategies
- Performance monitoring
- Cache warming capabilities

### Persistence
- PostgreSQL storage for rules
- ACID compliance
- Backup and recovery
- Data migration support
- Performance optimization

### Multi-tenant Support
- Tenant-specific rule isolation
- Cross-tenant rule inheritance
- Tenant-specific configurations
- Tenant-level rule management

### Performance Optimization
- High-throughput evaluation
- Parallel rule processing
- Optimized data structures
- Memory-efficient caching
- Connection pooling

### Observability
- Authorization metrics
- Rule evaluation logging
- Performance monitoring
- Health checks
- Audit trails

## API Endpoints

### Entitlement Endpoints

#### Check Entitlements
```http
POST /entitlements/check
Content-Type: application/json

{
  "user_id": "user-123",
  "tenant_id": "tenant-1",
  "resource": "curve",
  "action": "read",
  "context": {
    "user_roles": ["user", "analyst"],
    "resource_id": "curve-1",
    "commodity": "oil"
  }
}
```

**Response:**
```json
{
  "allowed": true,
  "reason": "Rule 'Analyst Access' matched",
  "matched_rules": ["rule-123"],
  "evaluation_time_ms": 5.2,
  "ttl_seconds": 300
}
```

### Rule Management Endpoints

#### List Rules
```http
GET /entitlements/rules?resource=curve&page=1&limit=10
```

**Response:**
```json
{
  "rules": [
    {
      "rule_id": "rule-123",
      "name": "Analyst Access",
      "description": "Allow analysts to read curve data",
      "resource": "curve",
      "action": "allow",
      "conditions": [
        {
          "field": "user_roles",
          "operator": "contains",
          "value": "analyst",
          "description": "User must have analyst role"
        }
      ],
      "priority": 100,
      "enabled": true,
      "tenant_id": "tenant-1",
      "user_id": null,
      "created_at": "2024-01-01T00:00:00Z",
      "updated_at": "2024-01-01T00:00:00Z",
      "expires_at": null
    }
  ],
  "total": 1,
  "page": 1,
  "limit": 10
}
```

#### Create Rule
```http
POST /entitlements/rules
Content-Type: application/json

{
  "name": "New Rule",
  "description": "Rule description",
  "resource": "curve",
  "action": "allow",
  "conditions": [
    {
      "field": "tenant_id",
      "operator": "equals",
      "value": "tenant-1",
      "description": "Tenant must be tenant-1"
    }
  ],
  "priority": 100,
  "tenant_id": "tenant-1",
  "user_id": null,
  "expires_at": null
}
```

**Response:**
```json
{
  "rule_id": "rule-456",
  "name": "New Rule",
  "description": "Rule description",
  "resource": "curve",
  "action": "allow",
  "conditions": [
    {
      "field": "tenant_id",
      "operator": "equals",
      "value": "tenant-1",
      "description": "Tenant must be tenant-1"
    }
  ],
  "priority": 100,
  "enabled": true,
  "tenant_id": "tenant-1",
  "user_id": null,
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:30:00Z",
  "expires_at": null
}
```

#### Update Rule
```http
PUT /entitlements/rules/rule-456
Content-Type: application/json

{
  "name": "Updated Rule",
  "description": "Updated description",
  "priority": 200
}
```

**Response:**
```json
{
  "rule_id": "rule-456",
  "name": "Updated Rule",
  "description": "Updated description",
  "resource": "curve",
  "action": "allow",
  "conditions": [
    {
      "field": "tenant_id",
      "operator": "equals",
      "value": "tenant-1",
      "description": "Tenant must be tenant-1"
    }
  ],
  "priority": 200,
  "enabled": true,
  "tenant_id": "tenant-1",
  "user_id": null,
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T11:00:00Z",
  "expires_at": null
}
```

#### Delete Rule
```http
DELETE /entitlements/rules/rule-456
```

**Response:**
```json
{
  "success": true,
  "message": "Rule deleted successfully"
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
  "service": "entitlements",
  "status": "ok",
  "uptime_seconds": 5231,
  "dependencies": {
    "redis": "ok",
    "postgres": "ok"
  },
  "version": "1.0.0",
  "commit": "abc1234"
}
```

#### Service Statistics
```http
GET /entitlements/stats
```

**Response:**
```json
{
  "engine": {
    "total_rules": 150,
    "enabled_rules": 145,
    "disabled_rules": 5,
    "expired_rules": 0
  },
  "cache": {
    "hit_ratio": 0.85,
    "total_requests": 10000,
    "cache_hits": 8500,
    "cache_misses": 1500
  },
  "persistence": {
    "total_rules": 150,
    "rules_by_tenant": {
      "tenant-1": 75,
      "tenant-2": 75
    }
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
| `ACCESS_REDIS_URL` | Redis connection URL | `redis://localhost:6379/0` | Yes |
| `ACCESS_POSTGRES_DSN` | PostgreSQL connection string | `postgresql://user:pass@localhost:5432/db` | Yes |
| `ACCESS_METRICS_ENDPOINT` | Metrics service URL | `http://localhost:8012` | Yes |
| `ACCESS_CACHE_TTL` | Cache TTL (seconds) | `300` | No |
| `ACCESS_MAX_RULES` | Maximum rules per tenant | `1000` | No |
| `ACCESS_ENABLE_TRACING` | Enable distributed tracing | `false` | No |

### Database Configuration

| Setting | Description | Default |
|---------|-------------|---------|
| `host` | Database host | `localhost` |
| `port` | Database port | `5432` |
| `database` | Database name | `access_layer` |
| `username` | Database username | `access_user` |
| `password` | Database password | Required |
| `pool_size` | Connection pool size | `10` |
| `max_overflow` | Max overflow connections | `20` |

### Cache Configuration

| Setting | Description | Default |
|---------|-------------|---------|
| `host` | Redis host | `localhost` |
| `port` | Redis port | `6379` |
| `database` | Redis database | `0` |
| `password` | Redis password | None |
| `ttl` | Default cache TTL | `300` |
| `max_connections` | Max connections | `10` |

## Development

### Local Development

1. **Install dependencies:**
   ```bash
   pip install -r requirements-dev.txt
   ```

2. **Start the service:**
   ```bash
   cd service_entitlements
   uvicorn app.main:app --reload --port 8011
   ```

3. **Run tests:**
   ```bash
   pytest tests/ -v
   ```

### Docker Development

1. **Build the image:**
   ```bash
   docker build -t entitlements-service .
   ```

2. **Run the container:**
   ```bash
   docker run -p 8011:8011 \
     -e ACCESS_REDIS_URL=redis://localhost:6379/0 \
     -e ACCESS_POSTGRES_DSN=postgresql://user:pass@localhost:5432/db \
     entitlements-service
   ```

### Testing

#### Unit Tests
```bash
pytest tests/test_rule_engine.py -v
pytest tests/test_main.py -v
```

#### Integration Tests
```bash
pytest tests/integration/ -v
```

#### Rule Testing
```bash
# Test entitlement check
curl -X POST http://localhost:8011/entitlements/check \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user-123",
    "tenant_id": "tenant-1",
    "resource": "curve",
    "action": "read",
    "context": {"user_roles": ["analyst"]}
  }'

# Test rule creation
curl -X POST http://localhost:8011/entitlements/rules \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Rule",
    "description": "Test rule",
    "resource": "curve",
    "action": "allow",
    "conditions": [{"field": "tenant_id", "operator": "equals", "value": "tenant-1"}],
    "priority": 100,
    "tenant_id": "tenant-1"
  }'
```

## Monitoring

### Metrics

The Entitlements Service exposes Prometheus metrics at `/metrics`:

- `entitlements_checks_total` - Total entitlement checks
- `entitlements_check_duration_seconds` - Entitlement check duration
- `entitlements_cache_hits_total` - Cache hits
- `entitlements_cache_misses_total` - Cache misses
- `entitlements_rules_total` - Total rules
- `entitlements_errors_total` - Total errors

### Logging

Structured JSON logging with correlation IDs:

```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "level": "INFO",
  "service": "entitlements",
  "trace_id": "abc123",
  "request_id": "req-456",
  "message": "Entitlement check successful",
  "user_id": "user-123",
  "tenant_id": "tenant-1",
  "resource": "curve",
  "action": "read",
  "allowed": true
}
```

### Health Checks

Health check endpoint provides service status:

```bash
curl http://localhost:8011/health
```

## Deployment

### Kubernetes

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: entitlements-service
spec:
  replicas: 3
  selector:
    matchLabels:
      app: entitlements-service
  template:
    metadata:
      labels:
        app: entitlements-service
    spec:
      containers:
      - name: entitlements-service
        image: ghcr.io/254carbon/access-layer-entitlements:latest
        ports:
        - containerPort: 8011
        env:
        - name: ACCESS_REDIS_URL
          value: "redis://redis-service:6379/0"
        - name: ACCESS_POSTGRES_DSN
          valueFrom:
            secretKeyRef:
              name: postgres-secret
              key: dsn
        livenessProbe:
          httpGet:
            path: /health
            port: 8011
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8011
          initialDelaySeconds: 5
          periodSeconds: 5
```

### Docker Compose

```yaml
version: '3.8'
services:
  entitlements-service:
    build:
      context: .
      dockerfile: service_entitlements/Dockerfile
    ports:
      - "8011:8011"
    environment:
      - ACCESS_REDIS_URL=redis://redis:6379/0
      - ACCESS_POSTGRES_DSN=postgresql://access_user:access_pass@postgres:5432/access_layer
    depends_on:
      - redis
      - postgres
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8011/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

## Troubleshooting

### Common Issues

1. **Rule Evaluation Failures**
   - Check rule syntax and conditions
   - Verify rule priority ordering
   - Check rule expiration status
   - Validate rule context

2. **Cache Issues**
   - Check Redis connectivity
   - Monitor cache hit ratio
   - Verify cache TTL settings
   - Check cache invalidation

3. **Database Issues**
   - Check PostgreSQL connectivity
   - Verify database schema
   - Monitor connection pool
   - Check query performance

4. **Performance Issues**
   - Monitor rule evaluation latency
   - Check cache performance
   - Monitor database performance
   - Verify connection pooling

### Debug Commands

```bash
# Check service health
curl http://localhost:8011/health

# Check service statistics
curl http://localhost:8011/entitlements/stats

# Test entitlement check
curl -X POST http://localhost:8011/entitlements/check \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test", "tenant_id": "test", "resource": "test", "action": "read"}'
```

### Log Analysis

```bash
# Filter for entitlement checks
docker logs entitlements-service 2>&1 | grep "entitlement_check"

# Filter for rule evaluation
docker logs entitlements-service 2>&1 | grep "rule_evaluation"

# Filter for cache events
docker logs entitlements-service 2>&1 | grep "cache"

# Filter for errors
docker logs entitlements-service 2>&1 | grep ERROR
```

## Performance Tuning

### Optimization Tips

1. **Rule Engine Optimization**
   - Optimize rule conditions
   - Use appropriate rule priorities
   - Implement rule indexing
   - Monitor evaluation performance

2. **Caching Strategy**
   - Enable result caching
   - Use appropriate cache TTL
   - Implement cache warming
   - Monitor cache performance

3. **Database Optimization**
   - Use connection pooling
   - Optimize queries
   - Implement indexing
   - Monitor database performance

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

2. **Database Scaling**
   - Use read replicas
   - Implement connection pooling
   - Monitor query performance
   - Use appropriate indexing

3. **Cache Scaling**
   - Use distributed cache (Redis)
   - Implement cache sharding
   - Monitor cache performance
   - Use appropriate cache TTL

## Security

### Security Features

1. **Rule Validation**
   - Rule syntax validation
   - Condition validation
   - Priority validation
   - Expiration checking

2. **Access Control**
   - Tenant isolation
   - User-specific rules
   - Role-based access
   - Resource-level permissions

3. **Data Protection**
   - Encrypted storage
   - Secure communication
   - Access logging
   - Audit trails

4. **Input Validation**
   - Rule validation
   - Condition validation
   - Parameter validation
   - SQL injection prevention

### Security Best Practices

1. **Rule Management**
   - Validate rule syntax
   - Test rule conditions
   - Monitor rule changes
   - Implement rule versioning

2. **Access Control**
   - Implement tenant isolation
   - Use role-based access
   - Monitor access patterns
   - Implement audit logging

3. **Data Security**
   - Use encrypted storage
   - Implement secure communication
   - Monitor data access
   - Regular security audits

4. **Monitoring**
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
