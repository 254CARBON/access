# 254Carbon Access Layer Documentation

Welcome to the 254Carbon Access Layer documentation. This directory contains comprehensive guides for developing, testing, and deploying the access layer services.

## 📚 Documentation Overview

### Getting Started
- **[Development Setup Guide](development-setup.md)** - Complete setup instructions for local development
- **[Local Testing Guide](local-testing-guide.md)** - Comprehensive testing and debugging instructions
- **[Troubleshooting Guide](troubleshooting.md)** - Common issues and solutions

### API Documentation
- **[API Documentation](api-documentation.md)** - Complete API reference for all services
- **[Streaming Protocols](streaming-protocols.md)** - WebSocket and SSE protocol details

### Service Documentation
- **[Gateway Service](../service_gateway/README.md)** - API Gateway service documentation
- **[Streaming Service](../service_streaming/README.md)** - Real-time streaming service documentation
- **[Auth Service](../service_auth/README.md)** - Authentication service documentation
- **[Entitlements Service](../service_entitlements/README.md)** - Access control service documentation
- **[Metrics Service](../service_metrics/README.md)** - Metrics collection service documentation

## 🚀 Quick Start

### Prerequisites
- Docker and Docker Compose
- Python 3.12+
- Git
- curl

### Setup Development Environment
```bash
# Clone the repository
git clone <repository-url>
cd access

# Start the development environment
docker-compose up -d

# Initialize Kafka topics
./scripts/kafka_topics.sh

# Verify services are running
./scripts/validate-dev-environment.sh
```

### Test the Setup
```bash
# Check service health
curl http://localhost:8000/health  # Gateway
curl http://localhost:8001/health  # Streaming
curl http://localhost:8010/health  # Auth
curl http://localhost:8011/health # Entitlements
curl http://localhost:8012/health  # Metrics

# Test WebSocket connection
wscat -c ws://localhost:8001/ws

# View API documentation
open http://localhost:8000/docs
```

## 🏗️ Architecture Overview

The 254Carbon Access Layer consists of five microservices:

### Core Services
1. **Gateway Service** (Port 8000) - Main API gateway with routing, authentication, rate limiting, and caching
2. **Streaming Service** (Port 8001) - Real-time data streaming via WebSocket and SSE
3. **Auth Service** (Port 8010) - JWT token verification and management
4. **Entitlements Service** (Port 8011) - Fine-grained access control using rule engine
5. **Metrics Service** (Port 8012) - Custom metrics collection and Prometheus export

### Infrastructure Services
- **PostgreSQL** (Port 5432) - Database for entitlements and persistence
- **Redis** (Port 6379) - Caching and session storage
- **Kafka** (Port 9092) - Message streaming and event distribution
- **Keycloak** (Port 8080) - Identity and access management

## 🔧 Development Workflow

### Making Changes
```bash
# Stop the service you're working on
docker-compose stop <service-name>

# Rebuild the service
docker-compose build <service-name>

# Start the service
docker-compose up -d <service-name>

# Check logs
docker-compose logs -f <service-name>
```

### Running Tests
```bash
# Unit tests
docker-compose exec <service-name> python -m pytest tests/ -v

# Integration tests
python -m pytest tests/integration/ -v

# Load tests
python tests/performance/websocket_load_test.py
```

### Debugging
```bash
# View service logs
docker-compose logs -f <service-name>

# Access service shell
docker-compose exec <service-name> /bin/bash

# Check service health
curl http://localhost:<port>/health
```

## 📊 Monitoring and Observability

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

### Tracing
Distributed tracing is implemented using OpenTelemetry.

## 🔒 Security

### Authentication
- JWT tokens issued by Keycloak
- API keys for service-to-service communication
- Token verification via Auth Service

### Authorization
- Fine-grained entitlements via Entitlements Service
- Rule-based access control
- Context-aware permissions

### Rate Limiting
- Token bucket algorithm
- Redis-backed distributed rate limiting
- Different limits for different endpoint types

## 🚀 Deployment

### Local Development
```bash
# Start all services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f
```

### Staging
```bash
# Deploy to staging
./scripts/deploy-staging.sh

# Run smoke tests
./scripts/smoke.sh staging
```

### Production
```bash
# Deploy to production
./scripts/deploy-production.sh

# Monitor deployment
./scripts/monitor-deployment.sh
```

## 🧪 Testing

### Test Types
1. **Unit Tests** - Test individual components
2. **Integration Tests** - Test service interactions
3. **End-to-End Tests** - Test complete workflows
4. **Load Tests** - Test performance and scalability
5. **Contract Tests** - Validate API contracts

### Running Tests
```bash
# All tests
make test

# Specific test types
make test-unit
make test-integration
make test-load

# Test coverage
make test-coverage
```

## 📈 Performance

### Load Testing
```bash
# WebSocket load test
python tests/performance/websocket_load_test.py \
  --streaming-url ws://localhost:8001/ws \
  --users 100 \
  --duration 300

# API load test
python tests/performance/api_load_test.py \
  --gateway-url http://localhost:8000 \
  --concurrent-users 50 \
  --duration 60
```

### Performance Monitoring
- Prometheus metrics collection
- Grafana dashboards
- Alerting rules
- Performance baselines

## 🔧 Configuration

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
```

### Configuration Files
- `docker-compose.yml` - Service orchestration
- `env.example` - Environment variable template
- `requirements-dev.txt` - Python dependencies
- `monitoring/prometheus.yml` - Prometheus configuration
- `monitoring/grafana/` - Grafana dashboards

## 🛠️ Tools and Scripts

### Development Scripts
- `scripts/validate-dev-environment.sh` - Validate development environment
- `scripts/kafka_topics.sh` - Manage Kafka topics
- `scripts/validate-openapi.py` - Validate OpenAPI specifications
- `scripts/run_performance_tests.sh` - Run performance tests

### CI/CD Scripts
- `scripts/deploy-staging.sh` - Deploy to staging
- `scripts/deploy-production.sh` - Deploy to production
- `scripts/smoke.sh` - Run smoke tests
- `scripts/monitor-deployment.sh` - Monitor deployment

## 📝 Contributing

### Code Style
- Follow PEP 8 for Python code
- Use type hints
- Write comprehensive docstrings
- Follow SOLID principles

### Testing
- Write unit tests for all new code
- Maintain test coverage above 80%
- Write integration tests for new features
- Update documentation for API changes

### Documentation
- Update README files for service changes
- Document new API endpoints
- Update troubleshooting guide for new issues
- Keep architecture diagrams current

## 🆘 Support

### Getting Help
1. **Check Documentation** - Start with this README and service-specific docs
2. **Run Diagnostics** - Use validation and troubleshooting scripts
3. **Check Logs** - Review service logs for errors
4. **Search Issues** - Look for similar issues in GitHub
5. **Contact Support** - Reach out to the development team

### Reporting Issues
When reporting issues, please include:
- Service name and version
- Error messages and logs
- Steps to reproduce
- Environment details
- Expected vs actual behavior

### Contact Information
- **GitHub Issues**: [Create an issue](https://github.com/254carbon/access-layer/issues)
- **Slack**: #dev-support channel
- **Email**: dev-support@254carbon.com

## 📚 Additional Resources

### External Documentation
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [Prometheus Documentation](https://prometheus.io/docs/)
- [Grafana Documentation](https://grafana.com/docs/)
- [OpenTelemetry Documentation](https://opentelemetry.io/docs/)

### Internal Resources
- [Architecture Decision Records](../docs/adr/)
- [API Specifications](../openapi/)
- [Monitoring Dashboards](../monitoring/grafana/)
- [Deployment Manifests](../k8s/)

## 🔄 Updates and Maintenance

### Regular Updates
- Update dependencies monthly
- Review security advisories weekly
- Update documentation with new features
- Maintain test coverage and quality

### Version Management
- Follow semantic versioning
- Tag releases in Git
- Maintain changelog
- Update service versions

---

**Last Updated**: 2024-01-01  
**Version**: 1.0.0  
**Maintainer**: 254Carbon Development Team
