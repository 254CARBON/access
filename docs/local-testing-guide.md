# Local Testing and Debugging Guide

This guide provides comprehensive instructions for testing and debugging the 254Carbon Access Layer services in your local development environment.

## Prerequisites

Ensure your development environment is running:
```bash
docker-compose up -d
./scripts/kafka_topics.sh
```

## Testing Overview

### Test Types
1. **Unit Tests**: Test individual components in isolation
2. **Integration Tests**: Test service interactions
3. **End-to-End Tests**: Test complete workflows
4. **Load Tests**: Test performance and scalability
5. **Contract Tests**: Validate API contracts

## Unit Testing

### Running Unit Tests

#### Individual Service Tests
```bash
# Gateway Service
docker-compose exec gateway python -m pytest service_gateway/tests/ -v

# Streaming Service
docker-compose exec streaming python -m pytest service_streaming/tests/ -v

# Auth Service
docker-compose exec auth python -m pytest service_auth/tests/ -v

# Entitlements Service
docker-compose exec entitlements python -m pytest service_entitlements/tests/ -v

# Metrics Service
docker-compose exec metrics python -m pytest service_metrics/tests/ -v
```

#### All Services Tests
```bash
# Run all unit tests
for service in gateway streaming auth entitlements metrics; do
    echo "Testing $service..."
    docker-compose exec $service python -m pytest service_${service}/tests/ -v
done
```

#### Test Coverage
```bash
# Run tests with coverage
docker-compose exec gateway python -m pytest service_gateway/tests/ --cov=app --cov-report=html
```

### Test Structure
```
service_<name>/tests/
├── test_main.py          # Main application tests
├── test_<component>.py   # Component-specific tests
└── conftest.py          # Test configuration and fixtures
```

## Integration Testing

### Running Integration Tests
```bash
# Run all integration tests
python -m pytest tests/integration/ -v

# Run specific integration test
python -m pytest tests/integration/test_gateway_auth_integration.py -v
```

### Integration Test Scenarios

#### 1. Gateway → Auth Service Integration
```bash
# Test JWT token validation through Gateway
curl -X POST http://localhost:8000/api/v1/auth/verify \
  -H "Content-Type: application/json" \
  -d '{"token": "your-jwt-token"}'
```

#### 2. Gateway → Entitlements Service Integration
```bash
# Test entitlement checks through Gateway
curl -X POST http://localhost:8000/api/v1/entitlements/check \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-jwt-token" \
  -d '{"resource": "pricing", "action": "read"}'
```

#### 3. Streaming → Kafka Integration
```bash
# Test WebSocket connection
wscat -c ws://localhost:8001/ws

# Test SSE connection
curl -N http://localhost:8001/sse
```

## End-to-End Testing

### Complete Workflow Tests

#### 1. Authentication Flow
```bash
# Step 1: Get JWT token from Keycloak
TOKEN=$(curl -X POST http://localhost:8080/realms/254carbon/protocol/openid-connect/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=client_credentials&client_id=access-layer&client_secret=your-secret" | jq -r '.access_token')

# Step 2: Verify token through Gateway
curl -X POST http://localhost:8000/api/v1/auth/verify \
  -H "Content-Type: application/json" \
  -d "{\"token\": \"$TOKEN\"}"
```

#### 2. Entitlement Check Flow
```bash
# Step 1: Check entitlements
curl -X POST http://localhost:8000/api/v1/entitlements/check \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"resource": "pricing", "action": "read", "user_id": "test-user"}'
```

#### 3. Streaming Data Flow
```bash
# Step 1: Connect to WebSocket
wscat -c ws://localhost:8001/ws

# Step 2: Subscribe to topic
{"type": "subscribe", "topic": "254carbon.pricing.curve.updates.v1"}

# Step 3: Send test message to Kafka
docker-compose exec kafka kafka-console-producer --bootstrap-server localhost:9092 --topic 254carbon.pricing.curve.updates.v1
```

## Load Testing

### WebSocket Load Testing
```bash
# Run WebSocket load test
python tests/performance/websocket_load_test.py \
  --streaming-url ws://localhost:8001/ws \
  --users 50 \
  --duration 300

# Run with Locust
locust -f tests/performance/locustfile.py --host ws://localhost:8001
```

### API Load Testing
```bash
# Test Gateway API performance
python tests/performance/api_load_test.py \
  --gateway-url http://localhost:8000 \
  --concurrent-users 100 \
  --duration 60
```

## Debugging

### Service Debugging

#### 1. Check Service Logs
```bash
# View real-time logs
docker-compose logs -f <service-name>

# View logs with timestamps
docker-compose logs -t <service-name>

# View last 100 lines
docker-compose logs --tail=100 <service-name>
```

#### 2. Access Service Shell
```bash
# Access service container shell
docker-compose exec <service-name> /bin/bash

# Access service Python shell
docker-compose exec <service-name> python
```

#### 3. Check Service Health
```bash
# Check health endpoint
curl http://localhost:<port>/health

# Check detailed health
curl http://localhost:<port>/health/detailed
```

### Database Debugging

#### PostgreSQL
```bash
# Connect to PostgreSQL
docker-compose exec postgres psql -U access -d access

# Check tables
\dt

# Check connections
SELECT * FROM pg_stat_activity;

# Check database size
SELECT pg_size_pretty(pg_database_size('access'));
```

#### Redis
```bash
# Connect to Redis
docker-compose exec redis redis-cli

# Check Redis info
INFO

# Check keys
KEYS *

# Check memory usage
INFO memory
```

### Kafka Debugging

#### Check Topics
```bash
# List topics
./scripts/kafka_topics.sh list

# Describe topic
./scripts/kafka_topics.sh describe 254carbon.pricing.curve.updates.v1
```

#### Monitor Messages
```bash
# Consume messages from topic
docker-compose exec kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic 254carbon.pricing.curve.updates.v1 \
  --from-beginning
```

#### Check Consumer Groups
```bash
# List consumer groups
docker-compose exec kafka kafka-consumer-groups \
  --bootstrap-server localhost:9092 \
  --list

# Check consumer group details
docker-compose exec kafka kafka-consumer-groups \
  --bootstrap-server localhost:9092 \
  --group <group-name> \
  --describe
```

## Performance Monitoring

### Metrics Collection
```bash
# Check Prometheus metrics
curl http://localhost:8012/metrics

# Check specific service metrics
curl http://localhost:8000/metrics  # Gateway
curl http://localhost:8001/metrics  # Streaming
curl http://localhost:8010/metrics # Auth
curl http://localhost:8011/metrics # Entitlements
```

### Key Metrics to Monitor
- **Request Rate**: `rate(gateway_requests_total[5m])`
- **Response Time**: `histogram_quantile(0.95, rate(gateway_request_duration_seconds_bucket[5m]))`
- **Error Rate**: `rate(gateway_requests_total{status=~"5.."}[5m])`
- **WebSocket Connections**: `streaming_websocket_connections_total`
- **Kafka Lag**: `streaming_kafka_consumer_lag`

## Common Issues and Solutions

### Issue: Service Won't Start
**Symptoms**: Service container exits immediately
**Solutions**:
1. Check logs: `docker-compose logs <service-name>`
2. Check health endpoint: `curl http://localhost:<port>/health`
3. Verify dependencies are running: `docker-compose ps`
4. Check environment variables: `docker-compose config`

### Issue: Database Connection Errors
**Symptoms**: "Connection refused" or "Authentication failed"
**Solutions**:
1. Check PostgreSQL is running: `docker-compose ps postgres`
2. Check PostgreSQL logs: `docker-compose logs postgres`
3. Verify connection string: `ACCESS_POSTGRES_DSN`
4. Test connection: `docker-compose exec postgres pg_isready -U access`

### Issue: Redis Connection Errors
**Symptoms**: "Connection refused" or "Redis connection failed"
**Solutions**:
1. Check Redis is running: `docker-compose ps redis`
2. Check Redis logs: `docker-compose logs redis`
3. Test connection: `docker-compose exec redis redis-cli ping`
4. Verify Redis URL: `ACCESS_REDIS_URL`

### Issue: Kafka Connection Errors
**Symptoms**: "Connection refused" or "Kafka connection failed"
**Solutions**:
1. Check Kafka is running: `docker-compose ps kafka`
2. Check Kafka logs: `docker-compose logs kafka`
3. Wait for Kafka to be ready: `docker-compose logs kafka | grep "started"`
4. Test connection: `./scripts/kafka_topics.sh list`

### Issue: WebSocket Connection Fails
**Symptoms**: WebSocket connection refused or timeout
**Solutions**:
1. Check Streaming service is running: `docker-compose ps streaming`
2. Check Streaming logs: `docker-compose logs streaming`
3. Verify WebSocket endpoint: `ws://localhost:8001/ws`
4. Check authentication: Ensure valid JWT token

### Issue: High Memory Usage
**Symptoms**: Services consuming excessive memory
**Solutions**:
1. Check memory usage: `docker stats`
2. Check service logs for memory leaks
3. Restart services: `docker-compose restart <service-name>`
4. Check resource limits in `docker-compose.yml`

### Issue: Slow Response Times
**Symptoms**: High latency in API responses
**Solutions**:
1. Check service logs for errors
2. Monitor metrics: `curl http://localhost:<port>/metrics`
3. Check database performance: `docker-compose exec postgres psql -U access -d access`
4. Check Redis performance: `docker-compose exec redis redis-cli info`
5. Check Kafka lag: `./scripts/kafka_topics.sh describe <topic>`

## Testing Best Practices

### 1. Test Isolation
- Each test should be independent
- Use test databases and Redis instances
- Clean up after tests

### 2. Test Data Management
- Use fixtures for consistent test data
- Create test data programmatically
- Clean up test data after tests

### 3. Error Testing
- Test error conditions and edge cases
- Verify error responses and status codes
- Test timeout scenarios

### 4. Performance Testing
- Test under various load conditions
- Monitor resource usage during tests
- Test scalability limits

### 5. Security Testing
- Test authentication and authorization
- Verify input validation
- Test for security vulnerabilities

## Continuous Testing

### Automated Testing
```bash
# Run all tests in CI/CD pipeline
make test

# Run specific test suites
make test-unit
make test-integration
make test-load
```

### Test Reporting
```bash
# Generate test coverage report
python -m pytest --cov=app --cov-report=html

# Generate test results in JUnit format
python -m pytest --junitxml=test-results.xml
```

## Next Steps

After completing local testing:

1. **Review test results** and fix any failures
2. **Optimize performance** based on load test results
3. **Update documentation** with any changes
4. **Prepare for staging deployment**
5. **Set up monitoring** and alerting
