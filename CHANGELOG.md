# Changelog

All notable changes to the 254Carbon Access Layer will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial repository structure with all 5 services
- Base service class with common functionality
- Shared libraries for config, logging, tracing, and metrics
- Service manifests for all services
- Dockerfiles for multi-arch builds
- GitHub Actions CI/CD pipeline
- Development scripts and tools
- Basic test framework
- Docker Compose for local development
- Kubernetes deployment manifests
- Pre-commit hooks for code quality

### Services
- **Gateway Service**: Basic FastAPI application with health endpoints
- **Streaming Service**: WebSocket and SSE endpoint placeholders
- **Auth Service**: JWT validation endpoint placeholders
- **Entitlements Service**: Authorization check endpoint placeholders
- **Metrics Service**: Metrics ingestion and export endpoint placeholders

### Infrastructure
- Multi-arch Docker builds (amd64 + arm64)
- Prometheus metrics collection
- OpenTelemetry tracing setup
- Structured JSON logging
- Health check endpoints for all services
- Rate limiting framework (placeholder)
- Caching utilities (placeholder)

## [1.0.0] - 2025-01-27

### Added
- Initial release of 254Carbon Access Layer
- All 5 services with basic functionality
- Complete development and deployment infrastructure
- Comprehensive documentation and examples
