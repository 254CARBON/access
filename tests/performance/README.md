# Performance Testing

This directory contains performance and load testing tools for the 254Carbon Access Layer.

## Overview

The performance testing suite includes:
- **Locust Load Tests** - Comprehensive REST API and WebSocket load testing
- **WebSocket Load Tests** - Dedicated WebSocket connection and message testing
- **Performance Benchmarks** - Baseline performance measurements
- **Stress Testing** - System limits and failure point testing

## Tools

### 1. Locust Load Testing (`locustfile.py`)

Comprehensive load testing using Locust framework for all services.

**Features:**
- Gateway Service REST API testing
- Streaming Service WebSocket and SSE testing
- Auth Service token validation testing
- Entitlements Service authorization testing
- Metrics Service collection and export testing
- Configurable load scenarios
- Performance threshold monitoring

**Usage:**
```bash
# Install Locust
pip install locust

# Light load test (10 users, 5 minutes)
locust -f tests/performance/locustfile.py \
  --host=http://localhost:8000 \
  --users=10 \
  --spawn-rate=2 \
  --run-time=5m

# Medium load test (50 users, 10 minutes)
locust -f tests/performance/locustfile.py \
  --host=http://localhost:8000 \
  --users=50 \
  --spawn-rate=5 \
  --run-time=10m

# Heavy load test (100 users, 15 minutes)
locust -f tests/performance/locustfile.py \
  --host=http://localhost:8000 \
  --users=100 \
  --spawn-rate=10 \
  --run-time=15m

# Stress test (200 users, 20 minutes)
locust -f tests/performance/locustfile.py \
  --host=http://localhost:8000 \
  --users=200 \
  --spawn-rate=20 \
  --run-time=20m

# Test specific service
locust -f tests/performance/locustfile.py \
  GatewayRESTUser \
  --host=http://localhost:8000 \
  --users=50 \
  --spawn-rate=5 \
  --run-time=10m
```

### 2. WebSocket Load Testing (`websocket_load_test.py`)

Dedicated WebSocket connection and message testing.

**Features:**
- WebSocket connection management
- Message subscription and handling
- Ping/pong latency testing
- Connection failure analysis
- Performance metrics collection
- Configurable test parameters

**Usage:**
```bash
# Basic WebSocket load test
python tests/performance/websocket_load_test.py \
  --max-connections=100 \
  --message-rate=1.0 \
  --test-duration=300

# High-load WebSocket test
python tests/performance/websocket_load_test.py \
  --max-connections=500 \
  --message-rate=5.0 \
  --test-duration=600 \
  --log-level=INFO

# Stress test WebSocket connections
python tests/performance/websocket_load_test.py \
  --max-connections=1000 \
  --message-rate=10.0 \
  --test-duration=900 \
  --log-level=WARNING
```

**Parameters:**
- `--streaming-url`: WebSocket streaming service URL (default: ws://localhost:8001)
- `--auth-url`: Auth service URL (default: http://localhost:8010)
- `--max-connections`: Maximum concurrent connections (default: 100)
- `--message-rate`: Messages per second per connection (default: 1.0)
- `--test-duration`: Test duration in seconds (default: 300)
- `--log-level`: Logging level (DEBUG, INFO, WARNING, ERROR)

## Test Scenarios

### 1. Light Load Scenario
- **Purpose**: Basic functionality verification
- **Users**: 10-20 concurrent users
- **Duration**: 5-10 minutes
- **Expected**: All services responsive, <100ms latency

### 2. Medium Load Scenario
- **Purpose**: Normal production load simulation
- **Users**: 50-100 concurrent users
- **Duration**: 10-15 minutes
- **Expected**: Stable performance, <200ms latency

### 3. Heavy Load Scenario
- **Purpose**: High traffic simulation
- **Users**: 100-200 concurrent users
- **Duration**: 15-20 minutes
- **Expected**: Acceptable performance degradation, <500ms latency

### 4. Stress Test Scenario
- **Purpose**: System limits testing
- **Users**: 200+ concurrent users
- **Duration**: 20+ minutes
- **Expected**: Identify breaking points and failure modes

## Performance Thresholds

### Response Time Thresholds (milliseconds)

| Service | Endpoint | Excellent | Good | Acceptable | Poor |
|---------|----------|-----------|------|------------|------|
| Gateway | instruments | <50 | <100 | <200 | >200 |
| Gateway | curves | <50 | <100 | <200 | >200 |
| Gateway | products | <75 | <150 | <300 | >300 |
| Gateway | pricing | <100 | <200 | <400 | >400 |
| Gateway | historical | <250 | <500 | <1000 | >1000 |
| Auth | verify_token | <25 | <50 | <100 | >100 |
| Auth | verify_ws_token | <25 | <50 | <100 | >100 |
| Entitlements | check | <50 | <100 | <200 | >200 |
| Metrics | track | <25 | <50 | <100 | >100 |
| Metrics | export | <250 | <500 | <1000 | >1000 |
| Streaming | ws_connect | <500 | <1000 | <2000 | >2000 |
| Streaming | sse_stream | <100 | <200 | <400 | >400 |

### Error Rate Thresholds (percentage)

| Service | Excellent | Good | Acceptable | Poor |
|---------|-----------|------|------------|------|
| Gateway | <0.1% | <0.5% | <1.0% | >1.0% |
| Auth | <0.05% | <0.1% | <0.5% | >0.5% |
| Entitlements | <0.1% | <0.5% | <1.0% | >1.0% |
| Metrics | <0.05% | <0.1% | <0.5% | >0.5% |
| Streaming | <0.2% | <0.5% | <2.0% | >2.0% |

### Throughput Thresholds (requests per second)

| Service | Excellent | Good | Acceptable | Poor |
|---------|-----------|------|------------|------|
| Gateway | >200 | >100 | >50 | <50 |
| Auth | >500 | >200 | >100 | <100 |
| Entitlements | >300 | >150 | >75 | <75 |
| Metrics | >600 | >300 | >150 | <150 |
| Streaming | >100 | >50 | >25 | <25 |

## Running Tests

### Prerequisites

1. **Install Dependencies:**
   ```bash
   pip install -r requirements-dev.txt
   pip install locust websockets httpx
   ```

2. **Start Services:**
   ```bash
   # Start all services using Docker Compose
   docker-compose -f docker-compose.dev.yml up -d
   
   # Or start services individually
   cd service_gateway && uvicorn app.main:app --port 8000 &
   cd service_streaming && uvicorn app.main:app --port 8001 &
   cd service_auth && uvicorn app.main:app --port 8010 &
   cd service_entitlements && uvicorn app.main:app --port 8011 &
   cd service_metrics && uvicorn app.main:app --port 8012 &
   ```

3. **Verify Services:**
   ```bash
   # Check service health
   curl http://localhost:8000/health
   curl http://localhost:8001/health
   curl http://localhost:8010/health
   curl http://localhost:8011/health
   curl http://localhost:8012/health
   ```

### Test Execution

#### 1. Quick Smoke Test
```bash
# Test basic functionality
python tests/performance/websocket_load_test.py \
  --max-connections=10 \
  --test-duration=60

# Test REST APIs
locust -f tests/performance/locustfile.py \
  --host=http://localhost:8000 \
  --users=5 \
  --spawn-rate=1 \
  --run-time=2m \
  --headless
```

#### 2. Comprehensive Load Test
```bash
# Run full load test suite
./scripts/run_performance_tests.sh
```

#### 3. Individual Service Testing
```bash
# Test Gateway Service
locust -f tests/performance/locustfile.py \
  GatewayRESTUser \
  --host=http://localhost:8000 \
  --users=50 \
  --spawn-rate=5 \
  --run-time=10m

# Test Streaming Service
python tests/performance/websocket_load_test.py \
  --max-connections=100 \
  --message-rate=2.0 \
  --test-duration=300

# Test Auth Service
locust -f tests/performance/locustfile.py \
  AuthServiceUser \
  --host=http://localhost:8010 \
  --users=25 \
  --spawn-rate=3 \
  --run-time=5m
```

## Test Results Analysis

### Key Metrics to Monitor

1. **Response Times**
   - Average response time
   - 95th percentile response time
   - Maximum response time
   - Response time distribution

2. **Throughput**
   - Requests per second
   - Messages per second
   - Connections per second
   - Data transfer rate

3. **Error Rates**
   - HTTP error rates
   - Connection failure rates
   - Timeout rates
   - Authentication failures

4. **Resource Utilization**
   - CPU usage
   - Memory usage
   - Network bandwidth
   - Database connections

5. **Scalability**
   - Performance degradation under load
   - Breaking points
   - Recovery time
   - Resource limits

### Performance Reports

#### Locust Reports
Locust generates HTML reports with:
- Request statistics
- Response time charts
- Error rate analysis
- User behavior simulation
- Performance trends

#### WebSocket Test Reports
WebSocket tests provide:
- Connection success rates
- Message latency statistics
- Error breakdown
- Performance assessment
- Connection lifecycle analysis

### Interpreting Results

#### Good Performance Indicators
- ✅ Response times within thresholds
- ✅ Error rates <1%
- ✅ Stable throughput under load
- ✅ Graceful degradation
- ✅ Quick recovery from failures

#### Performance Issues
- ❌ Response times exceeding thresholds
- ❌ High error rates (>5%)
- ❌ Throughput degradation
- ❌ Memory leaks
- ❌ Connection failures

#### Optimization Recommendations
- 🔧 Database query optimization
- 🔧 Caching strategy improvements
- 🔧 Connection pooling tuning
- 🔧 Load balancing optimization
- 🔧 Resource scaling

## Continuous Performance Testing

### CI/CD Integration

1. **Automated Performance Tests:**
   ```yaml
   # GitHub Actions workflow
   - name: Run Performance Tests
     run: |
       python tests/performance/websocket_load_test.py \
         --max-connections=50 \
         --test-duration=300
   ```

2. **Performance Regression Detection:**
   - Baseline performance metrics
   - Automated threshold checking
   - Performance trend analysis
   - Alert on performance degradation

3. **Load Testing in Staging:**
   - Pre-production validation
   - Capacity planning
   - Performance benchmarking
   - Stress testing

### Monitoring Integration

1. **Real-time Performance Monitoring:**
   - Prometheus metrics collection
   - Grafana dashboards
   - Alerting on performance issues
   - Performance trend analysis

2. **Performance Baselines:**
   - Historical performance data
   - Performance regression detection
   - Capacity planning insights
   - Optimization recommendations

## Troubleshooting

### Common Issues

1. **Connection Failures**
   - Check service availability
   - Verify network connectivity
   - Check authentication tokens
   - Monitor resource limits

2. **High Latency**
   - Database query optimization
   - Cache hit ratio analysis
   - Network latency investigation
   - Resource bottleneck identification

3. **Memory Issues**
   - Memory leak detection
   - Garbage collection analysis
   - Connection pool monitoring
   - Resource cleanup verification

4. **Throughput Issues**
   - Load balancing configuration
   - Connection pooling tuning
   - Database connection limits
   - Network bandwidth analysis

### Debug Commands

```bash
# Check service health
curl http://localhost:8000/health

# Monitor resource usage
docker stats

# Check service logs
docker logs gateway-service
docker logs streaming-service

# Test individual endpoints
curl -X POST http://localhost:8010/auth/verify \
  -H "Content-Type: application/json" \
  -d '{"token": "test-token"}'

# WebSocket connection test
wscat -c ws://localhost:8001/ws/stream?token=test-token
```

## Best Practices

### Test Design
1. **Start Small**: Begin with light load tests
2. **Gradual Increase**: Incrementally increase load
3. **Realistic Scenarios**: Use production-like data
4. **Comprehensive Coverage**: Test all service endpoints
5. **Long Duration**: Run tests for sufficient time

### Test Execution
1. **Consistent Environment**: Use same hardware/network
2. **Baseline Measurements**: Establish performance baselines
3. **Multiple Runs**: Run tests multiple times
4. **Documentation**: Record test conditions and results
5. **Analysis**: Thoroughly analyze results

### Performance Optimization
1. **Identify Bottlenecks**: Find performance limiting factors
2. **Optimize Critical Paths**: Focus on high-impact improvements
3. **Monitor Trends**: Track performance over time
4. **Capacity Planning**: Plan for future growth
5. **Continuous Improvement**: Regular performance reviews

## Contributing

### Adding New Tests
1. **Follow Patterns**: Use existing test patterns
2. **Documentation**: Document test purpose and usage
3. **Configuration**: Make tests configurable
4. **Error Handling**: Implement proper error handling
5. **Performance**: Optimize test performance

### Test Maintenance
1. **Regular Updates**: Keep tests current with code changes
2. **Threshold Updates**: Update performance thresholds
3. **New Scenarios**: Add new test scenarios
4. **Bug Fixes**: Fix test issues promptly
5. **Documentation**: Keep documentation current
