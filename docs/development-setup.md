# Development Environment Setup Guide

This guide will help you set up the 254Carbon Access Layer development environment on your local machine.

## Prerequisites

Before you begin, ensure you have the following installed:

- **Docker** (version 20.10+) and **Docker Compose** (version 2.0+)
- **Python** 3.12+
- **Git**
- **curl** (for health checks)
- **kafka-topics** command (for Kafka topic management)

### Installing Prerequisites

#### macOS (using Homebrew)
```bash
# Install Docker Desktop
brew install --cask docker

# Install Python 3.12
brew install python@3.12

# Install Git (if not already installed)
brew install git

# Install curl (if not already installed)
brew install curl
```

#### Ubuntu/Debian
```bash
# Install Docker
sudo apt-get update
sudo apt-get install docker.io docker-compose-plugin

# Install Python 3.12
sudo apt-get install python3.12 python3.12-venv python3.12-dev

# Install Git
sudo apt-get install git

# Install curl
sudo apt-get install curl
```

#### Windows
- Download and install [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- Download and install [Python 3.12](https://www.python.org/downloads/)
- Download and install [Git for Windows](https://git-scm.com/download/win)

## Quick Start

### 1. Clone the Repository
```bash
git clone <repository-url>
cd access
```

### 2. Set Up Environment Variables
```bash
# Copy the example environment file
cp env.example .env

# Edit the environment file with your settings
# Most defaults should work for local development
```

### 3. Start the Development Environment
```bash
# Start all services
docker-compose up -d

# Check service status
docker-compose ps

# View logs
docker-compose logs -f
```

### 4. Initialize Kafka Topics
```bash
# Wait for Kafka to be ready (about 30 seconds)
sleep 30

# Create Kafka topics
./scripts/kafka_topics.sh

# Verify topics were created
./scripts/kafka_topics.sh list
```

### 5. Verify Services are Running
```bash
# Check health endpoints
curl http://localhost:8000/health  # Gateway
curl http://localhost:8001/health  # Streaming
curl http://localhost:8010/health  # Auth
curl http://localhost:8011/health # Entitlements
curl http://localhost:8012/health  # Metrics

# Check infrastructure services
curl http://localhost:8080/health/ready  # Keycloak
```

## Service Details

### Service Ports
- **Gateway Service**: 8000
- **Streaming Service**: 8001
- **Auth Service**: 8010
- **Entitlements Service**: 8011
- **Metrics Service**: 8012
- **Keycloak**: 8080
- **PostgreSQL**: 5432
- **Redis**: 6379
- **Kafka**: 9092
- **Zookeeper**: 2181

### Service Dependencies
```
Gateway → Auth, Entitlements, Metrics, Redis
Streaming → Kafka, Redis, Auth, Entitlements, Metrics
Auth → Keycloak
Entitlements → PostgreSQL, Redis
Metrics → (standalone)
```

## Development Workflow

### Making Changes to Services

1. **Stop the specific service**:
   ```bash
   docker-compose stop <service-name>
   ```

2. **Rebuild the service**:
   ```bash
   docker-compose build <service-name>
   ```

3. **Start the service**:
   ```bash
   docker-compose up -d <service-name>
   ```

### Running Tests

#### Unit Tests
```bash
# Run tests for a specific service
docker-compose exec <service-name> python -m pytest tests/ -v

# Run all tests
docker-compose exec gateway python -m pytest tests/ -v
docker-compose exec streaming python -m pytest tests/ -v
docker-compose exec auth python -m pytest tests/ -v
docker-compose exec entitlements python -m pytest tests/ -v
docker-compose exec metrics python -m pytest tests/ -v
```

#### Integration Tests
```bash
# Run integration tests
python -m pytest tests/integration/ -v
```

#### Load Tests
```bash
# Run WebSocket load tests
python tests/performance/websocket_load_test.py
```

### Debugging Services

#### View Service Logs
```bash
# View logs for a specific service
docker-compose logs -f <service-name>

# View logs for all services
docker-compose logs -f
```

#### Access Service Shell
```bash
# Access shell inside a service container
docker-compose exec <service-name> /bin/bash
```

#### Check Service Health
```bash
# Check health status
docker-compose ps

# Check health endpoints
curl http://localhost:<port>/health
```

## Common Issues and Solutions

### Issue: Services Won't Start
**Solution**: Check Docker Compose logs
```bash
docker-compose logs
```

### Issue: Kafka Topics Not Created
**Solution**: Ensure Kafka is fully started before creating topics
```bash
# Wait for Kafka to be ready
docker-compose logs kafka | grep "started"

# Then create topics
./scripts/kafka_topics.sh
```

### Issue: Database Connection Errors
**Solution**: Ensure PostgreSQL is healthy
```bash
# Check PostgreSQL health
docker-compose exec postgres pg_isready -U access

# Check PostgreSQL logs
docker-compose logs postgres
```

### Issue: Redis Connection Errors
**Solution**: Ensure Redis is healthy
```bash
# Check Redis health
docker-compose exec redis redis-cli ping

# Check Redis logs
docker-compose logs redis
```

### Issue: Port Conflicts
**Solution**: Check if ports are already in use
```bash
# Check port usage
lsof -i :8000  # Gateway port
lsof -i :8001  # Streaming port
# ... etc

# Stop conflicting services or change ports in docker-compose.yml
```

## Environment Configuration

### Environment Variables

Key environment variables for local development:

```bash
# General
ACCESS_ENV=local

# Database
ACCESS_POSTGRES_DSN=postgres://access:access@postgres:5432/access

# Redis
ACCESS_REDIS_URL=redis://redis:6379/0

# Kafka
ACCESS_KAFKA_BOOTSTRAP=kafka:9092

# Service URLs
ACCESS_AUTH_SERVICE_URL=http://auth:8010
ACCESS_ENTITLEMENTS_SERVICE_URL=http://entitlements:8011
ACCESS_METRICS_SERVICE_URL=http://metrics:8012

# Keycloak
ACCESS_JWKS_URL=http://keycloak:8080/realms/254carbon/protocol/openid-connect/certs
```

### Customizing the Environment

#### Adding New Services
1. Create service directory: `service_<name>/`
2. Add Dockerfile
3. Add service to `docker-compose.yml`
4. Update dependencies

#### Changing Ports
1. Update `docker-compose.yml` ports section
2. Update service environment variables
3. Update health check URLs

#### Adding New Dependencies
1. Update `requirements-dev.txt`
2. Rebuild affected services
3. Update service configurations

## Monitoring and Observability

### Health Checks
All services expose health check endpoints:
- `GET /health` - Basic health check
- `GET /health/ready` - Readiness check
- `GET /health/live` - Liveness check

### Metrics
All services expose Prometheus metrics:
- `GET /metrics` - Prometheus metrics endpoint

### Logs
All services use structured JSON logging with correlation IDs.

## Troubleshooting

### Reset the Environment
```bash
# Stop all services
docker-compose down

# Remove volumes (WARNING: This will delete all data)
docker-compose down -v

# Rebuild and start
docker-compose up -d --build
```

### Clean Up
```bash
# Remove unused containers, networks, images
docker system prune -f

# Remove unused volumes
docker volume prune -f
```

### Performance Issues
```bash
# Check resource usage
docker stats

# Check service resource limits
docker-compose config
```

## Next Steps

Once your development environment is running:

1. **Explore the APIs**: Use the OpenAPI documentation at `http://localhost:8000/docs`
2. **Test WebSocket connections**: Connect to `ws://localhost:8001/ws`
3. **Monitor metrics**: Check `http://localhost:8012/metrics`
4. **View logs**: Use `docker-compose logs -f` to monitor service activity

## Getting Help

- Check service logs: `docker-compose logs <service-name>`
- Verify health endpoints: `curl http://localhost:<port>/health`
- Review this documentation
- Check the troubleshooting section above
