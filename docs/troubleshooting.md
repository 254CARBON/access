# Troubleshooting Guide

This guide helps you diagnose and resolve common issues when working with the 254Carbon Access Layer development environment.

## Quick Diagnostics

### Check Service Status
```bash
# Check all services
docker-compose ps

# Check specific service
docker-compose ps <service-name>

# Check service health
curl http://localhost:<port>/health
```

### Check Logs
```bash
# View all logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f <service-name>

# View last 100 lines
docker-compose logs --tail=100 <service-name>
```

### Validate Environment
```bash
# Run validation script
./scripts/validate-dev-environment.sh

# Check Docker Compose config
docker-compose config
```

## Common Issues

### 1. Services Won't Start

#### Symptoms
- Services exit immediately
- "Container exited with code 1" errors
- Services stuck in "Restarting" state

#### Diagnosis
```bash
# Check service status
docker-compose ps

# Check logs for startup errors
docker-compose logs <service-name>

# Check Docker Compose configuration
docker-compose config
```

#### Solutions

**Port Conflicts**
```bash
# Check if ports are in use
lsof -i :8000  # Gateway
lsof -i :8001  # Streaming
lsof -i :8010  # Auth
lsof -i :8011  # Entitlements
lsof -i :8012  # Metrics

# Stop conflicting services
sudo lsof -ti:8000 | xargs kill -9
```

**Missing Dependencies**
```bash
# Rebuild services
docker-compose build --no-cache

# Pull latest images
docker-compose pull
```

**Configuration Issues**
```bash
# Check environment variables
docker-compose config

# Validate Docker Compose file
docker-compose config --quiet
```

### 2. Database Connection Errors

#### Symptoms
- "Connection refused" errors
- "Authentication failed" errors
- Services can't connect to PostgreSQL

#### Diagnosis
```bash
# Check PostgreSQL status
docker-compose ps postgres

# Check PostgreSQL logs
docker-compose logs postgres

# Test PostgreSQL connection
docker-compose exec postgres pg_isready -U access
```

#### Solutions

**PostgreSQL Not Running**
```bash
# Start PostgreSQL
docker-compose up -d postgres

# Wait for PostgreSQL to be ready
docker-compose logs -f postgres | grep "ready to accept connections"
```

**Connection String Issues**
```bash
# Check environment variables
echo $ACCESS_POSTGRES_DSN

# Verify connection string format
# Should be: postgres://access:access@postgres:5432/access
```

**Database Not Initialized**
```bash
# Check if database exists
docker-compose exec postgres psql -U access -d access -c "\l"

# Initialize database if needed
docker-compose exec postgres psql -U access -c "CREATE DATABASE access;"
```

### 3. Redis Connection Errors

#### Symptoms
- "Connection refused" errors
- "Redis connection failed" errors
- Cache operations failing

#### Diagnosis
```bash
# Check Redis status
docker-compose ps redis

# Check Redis logs
docker-compose logs redis

# Test Redis connection
docker-compose exec redis redis-cli ping
```

#### Solutions

**Redis Not Running**
```bash
# Start Redis
docker-compose up -d redis

# Wait for Redis to be ready
docker-compose logs -f redis | grep "Ready to accept connections"
```

**Connection URL Issues**
```bash
# Check environment variables
echo $ACCESS_REDIS_URL

# Verify connection URL format
# Should be: redis://redis:6379/0
```

**Memory Issues**
```bash
# Check Redis memory usage
docker-compose exec redis redis-cli info memory

# Clear Redis cache if needed
docker-compose exec redis redis-cli flushall
```

### 4. Kafka Connection Errors

#### Symptoms
- "Connection refused" errors
- "Kafka connection failed" errors
- Topics not found

#### Diagnosis
```bash
# Check Kafka status
docker-compose ps kafka

# Check Kafka logs
docker-compose logs kafka

# Test Kafka connection
docker-compose exec kafka kafka-topics --bootstrap-server localhost:9092 --list
```

#### Solutions

**Kafka Not Running**
```bash
# Start Kafka
docker-compose up -d kafka

# Wait for Kafka to be ready
docker-compose logs -f kafka | grep "started"
```

**Topics Not Created**
```bash
# Create Kafka topics
./scripts/kafka_topics.sh

# Verify topics
./scripts/kafka_topics.sh list
```

**Zookeeper Issues**
```bash
# Check Zookeeper status
docker-compose ps zookeeper

# Restart Zookeeper if needed
docker-compose restart zookeeper
```

### 5. WebSocket Connection Issues

#### Symptoms
- WebSocket connection refused
- Connection timeout
- Authentication failures

#### Diagnosis
```bash
# Check Streaming service status
docker-compose ps streaming

# Check Streaming service logs
docker-compose logs streaming

# Test WebSocket endpoint
curl -i -N -H "Connection: Upgrade" -H "Upgrade: websocket" -H "Sec-WebSocket-Key: test" -H "Sec-WebSocket-Version: 13" http://localhost:8001/ws
```

#### Solutions

**Streaming Service Not Running**
```bash
# Start Streaming service
docker-compose up -d streaming

# Check health endpoint
curl http://localhost:8001/health
```

**Authentication Issues**
```bash
# Get JWT token from Keycloak
TOKEN=$(curl -X POST http://localhost:8080/realms/254carbon/protocol/openid-connect/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=client_credentials&client_id=access-layer&client_secret=your-secret" | jq -r '.access_token')

# Test WebSocket with authentication
wscat -c ws://localhost:8001/ws -H "Authorization: Bearer $TOKEN"
```

### 6. Authentication Issues

#### Symptoms
- "Invalid token" errors
- "Authentication failed" errors
- JWT verification failures

#### Diagnosis
```bash
# Check Auth service status
docker-compose ps auth

# Check Auth service logs
docker-compose logs auth

# Test JWT verification
curl -X POST http://localhost:8010/api/v1/tokens/verify \
  -H "Content-Type: application/json" \
  -d '{"token": "your-jwt-token"}'
```

#### Solutions

**Keycloak Not Running**
```bash
# Start Keycloak
docker-compose up -d keycloak

# Wait for Keycloak to be ready
docker-compose logs -f keycloak | grep "started"
```

**JWKS Issues**
```bash
# Check JWKS endpoint
curl http://localhost:8080/realms/254carbon/protocol/openid-connect/certs

# Check Auth service JWKS cache
curl http://localhost:8010/api/v1/jwks
```

**Token Issues**
```bash
# Get new token from Keycloak
TOKEN=$(curl -X POST http://localhost:8080/realms/254carbon/protocol/openid-connect/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=client_credentials&client_id=access-layer&client_secret=your-secret" | jq -r '.access_token')

# Verify token
curl -X POST http://localhost:8010/api/v1/tokens/verify \
  -H "Content-Type: application/json" \
  -d "{\"token\": \"$TOKEN\"}"
```

### 7. Performance Issues

#### Symptoms
- Slow response times
- High memory usage
- Timeout errors

#### Diagnosis
```bash
# Check resource usage
docker stats

# Check service metrics
curl http://localhost:8012/metrics

# Check service logs for performance issues
docker-compose logs --tail=100 <service-name> | grep -i "slow\|timeout\|error"
```

#### Solutions

**High Memory Usage**
```bash
# Check memory usage per service
docker stats --no-stream

# Restart services with high memory usage
docker-compose restart <service-name>

# Check for memory leaks in logs
docker-compose logs <service-name> | grep -i "memory\|leak"
```

**Slow Response Times**
```bash
# Check service health
curl -w "@curl-format.txt" http://localhost:8000/health

# Check database performance
docker-compose exec postgres psql -U access -d access -c "SELECT * FROM pg_stat_activity;"

# Check Redis performance
docker-compose exec redis redis-cli info stats
```

**Timeout Issues**
```bash
# Increase timeout values in docker-compose.yml
# Add to service configuration:
# healthcheck:
#   timeout: 30s
#   interval: 60s
#   retries: 5
```

### 8. Network Issues

#### Symptoms
- Services can't communicate
- "Connection refused" errors
- DNS resolution failures

#### Diagnosis
```bash
# Check Docker network
docker network ls

# Check service network connectivity
docker-compose exec <service-name> ping <other-service>

# Check DNS resolution
docker-compose exec <service-name> nslookup <other-service>
```

#### Solutions

**Network Connectivity**
```bash
# Recreate Docker network
docker-compose down
docker network prune -f
docker-compose up -d

# Check service networking
docker-compose exec <service-name> netstat -tulpn
```

**DNS Issues**
```bash
# Check Docker DNS configuration
docker-compose exec <service-name> cat /etc/resolv.conf

# Restart services
docker-compose restart
```

## Advanced Troubleshooting

### 1. Complete Environment Reset

```bash
# Stop all services
docker-compose down

# Remove volumes (WARNING: This will delete all data)
docker-compose down -v

# Remove unused containers, networks, images
docker system prune -f

# Rebuild and start
docker-compose up -d --build
```

### 2. Service-Specific Debugging

#### Gateway Service
```bash
# Check Gateway logs
docker-compose logs -f gateway

# Test Gateway endpoints
curl http://localhost:8000/health
curl http://localhost:8000/api/v1/info

# Check Gateway metrics
curl http://localhost:8000/metrics
```

#### Streaming Service
```bash
# Check Streaming logs
docker-compose logs -f streaming

# Test WebSocket connection
wscat -c ws://localhost:8001/ws

# Test SSE connection
curl -N http://localhost:8001/sse
```

#### Auth Service
```bash
# Check Auth logs
docker-compose logs -f auth

# Test JWT verification
curl -X POST http://localhost:8010/api/v1/tokens/verify \
  -H "Content-Type: application/json" \
  -d '{"token": "test-token"}'

# Check JWKS endpoint
curl http://localhost:8010/api/v1/jwks
```

#### Entitlements Service
```bash
# Check Entitlements logs
docker-compose logs -f entitlements

# Test entitlement check
curl -X POST http://localhost:8011/api/v1/entitlements/check \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test", "resource": "pricing", "action": "read"}'

# Check rule management
curl http://localhost:8011/api/v1/rules
```

#### Metrics Service
```bash
# Check Metrics logs
docker-compose logs -f metrics

# Check Prometheus metrics
curl http://localhost:8012/metrics

# Test custom metrics
curl -X POST http://localhost:8012/api/v1/metrics \
  -H "Content-Type: application/json" \
  -d '{"name": "test_metric", "value": 42}'
```

### 3. Log Analysis

#### Search for Errors
```bash
# Search for ERROR level logs
docker-compose logs | grep -i error

# Search for specific error patterns
docker-compose logs | grep -i "connection refused"
docker-compose logs | grep -i "timeout"
docker-compose logs | grep -i "authentication failed"
```

#### Monitor Real-time Logs
```bash
# Monitor all logs
docker-compose logs -f

# Monitor specific service
docker-compose logs -f <service-name>

# Monitor logs with timestamps
docker-compose logs -t -f
```

### 4. Performance Monitoring

#### Resource Usage
```bash
# Monitor resource usage
docker stats

# Check specific service resources
docker stats <service-name>

# Monitor resource usage over time
watch -n 5 'docker stats --no-stream'
```

#### Service Metrics
```bash
# Check Gateway metrics
curl http://localhost:8000/metrics | grep gateway_

# Check Streaming metrics
curl http://localhost:8001/metrics | grep streaming_

# Check Auth metrics
curl http://localhost:8010/metrics | grep auth_

# Check Entitlements metrics
curl http://localhost:8011/metrics | grep entitlements_

# Check Metrics service
curl http://localhost:8012/metrics
```

## Getting Help

### 1. Check Documentation
- [Development Setup Guide](development-setup.md)
- [Local Testing Guide](local-testing-guide.md)
- [API Documentation](api-documentation.md)

### 2. Run Diagnostics
```bash
# Run comprehensive validation
./scripts/validate-dev-environment.sh

# Check OpenAPI specifications
./scripts/validate-openapi.py

# Run performance tests
./scripts/run_performance_tests.sh
```

### 3. Collect Information
```bash
# Collect system information
docker-compose ps > system-status.txt
docker-compose logs > system-logs.txt
docker stats --no-stream > resource-usage.txt

# Create diagnostic package
tar -czf diagnostics-$(date +%Y%m%d-%H%M%S).tar.gz \
  system-status.txt system-logs.txt resource-usage.txt \
  docker-compose.yml .env
```

### 4. Contact Support
- **GitHub Issues**: [Create an issue](https://github.com/254carbon/access-layer/issues)
- **Slack**: #dev-support channel
- **Email**: dev-support@254carbon.com

## Prevention

### 1. Regular Maintenance
```bash
# Weekly cleanup
docker system prune -f
docker volume prune -f

# Update dependencies
docker-compose pull
```

### 2. Monitoring
```bash
# Set up monitoring
# Add to crontab:
# 0 */6 * * * /path/to/scripts/validate-dev-environment.sh
```

### 3. Backup
```bash
# Backup important data
docker-compose exec postgres pg_dump -U access access > backup.sql
docker-compose exec redis redis-cli --rdb /data/backup.rdb
```

### 4. Documentation
- Keep this troubleshooting guide updated
- Document any custom configurations
- Share solutions with the team
