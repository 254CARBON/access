# 254Carbon Access Layer Makefile

.PHONY: help install dev-all test lint build buildx buildx-push spec-sync contract-check smoke manifest-validate docker-up docker-down docker-logs docker-test

# Default target
help:
	@echo "254Carbon Access Layer - Available targets:"
	@echo "  install          - Install shared dev dependencies"
	@echo "  dev-all          - Run all services in dev mode"
	@echo "  test             - Run tests for all services"
	@echo "  lint             - Lint & format check"
	@echo "  build SERVICE=<svc> VERSION=<ver> - Build single service image"
	@echo "  buildx SERVICE=<svc> VERSION=<ver> - Build multi-arch image"
	@echo "  push SERVICE=<svc> VERSION=<ver> - Push image to GHCR"
	@echo "  spec-sync        - Pull latest specs from specs repo"
	@echo "  contract-check   - Verify no breaking changes"
	@echo "  smoke            - Basic liveness test across services"
	@echo "  manifest-validate - Validate all service manifests"
	@echo "  docker-up        - Start Docker Compose stack (dev)"
	@echo "  docker-down      - Stop Docker Compose stack"
	@echo "  docker-logs      - View Docker Compose logs"
	@echo "  docker-test      - Start test environment"

# Install shared dev dependencies
install:
	pip install -r requirements-dev.txt
	pre-commit install

# Run all services in development mode
dev-all:
	@echo "Starting all services in development mode..."
	@echo "Gateway: http://localhost:8000"
	@echo "Streaming: http://localhost:8001"
	@echo "Auth: http://localhost:8010"
	@echo "Entitlements: http://localhost:8011"
	@echo "Metrics: http://localhost:8012"
	./scripts/dev_cluster.sh

# Run tests for all services
test:
	pytest service_*/tests/ -v --cov=service_*/app --cov-report=html

# Lint and format check
lint:
	black --check service_*/app/
	flake8 service_*/app/
	mypy service_*/app/

# Build single service image
build:
	@if [ -z "$(SERVICE)" ]; then echo "SERVICE variable required"; exit 1; fi
	docker build -f service_$(SERVICE)/Dockerfile -t ghcr.io/254carbon/$(SERVICE):latest .

# Build multi-arch image
buildx:
	@if [ -z "$(SERVICE)" ]; then echo "SERVICE variable required"; exit 1; fi
	@if [ -z "$(VERSION)" ]; then echo "VERSION variable required"; exit 1; fi
	docker buildx build \
		--platform linux/amd64,linux/arm64 \
		-f service_$(SERVICE)/Dockerfile \
		-t ghcr.io/254carbon/$(SERVICE):$(VERSION) \
		-t ghcr.io/254carbon/$(SERVICE):latest \
		--push .

# Push image to GHCR
push:
	@if [ -z "$(SERVICE)" ]; then echo "SERVICE variable required"; exit 1; fi
	@if [ -z "$(VERSION)" ]; then echo "VERSION variable required"; exit 1; fi
	docker push ghcr.io/254carbon/$(SERVICE):$(VERSION)
	docker push ghcr.io/254carbon/$(SERVICE):latest

# Sync specs from specs repo
spec-sync:
	python scripts/codegen_sync.py

# Check for contract breaking changes
contract-check:
	python scripts/contract_check.py

# Basic smoke test
smoke:
	./scripts/smoke.sh

# Validate service manifests
manifest-validate:
	python scripts/validate_manifests.py

# Docker Compose management
docker-up:
	./scripts/docker-compose-manager.sh -e dev -a up -d

docker-down:
	./scripts/docker-compose-manager.sh -e dev -a down

docker-logs:
	./scripts/docker-compose-manager.sh -e dev -a logs

docker-test:
	./scripts/docker-compose-manager.sh -e test -a up -d

# Clean up build artifacts
clean:
	docker system prune -f
	rm -rf service_*/__pycache__/
	rm -rf service_*/.pytest_cache/
	rm -rf htmlcov/
