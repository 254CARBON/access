#!/bin/bash

# Docker Compose Validation Script
# Validates the Docker Compose setup for the 254Carbon Access Layer

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    local status=$1
    local message=$2
    case $status in
        "SUCCESS")
            echo -e "${GREEN}✅ $message${NC}"
            ;;
        "ERROR")
            echo -e "${RED}❌ $message${NC}"
            ;;
        "WARNING")
            echo -e "${YELLOW}⚠️  $message${NC}"
            ;;
        "INFO")
            echo -e "${YELLOW}ℹ️  $message${NC}"
            ;;
    esac
}

# Function to check if Docker is running
check_docker() {
    print_status "INFO" "Checking Docker installation..."
    
    if ! command -v docker &> /dev/null; then
        print_status "ERROR" "Docker is not installed"
        exit 1
    fi
    
    if ! docker info &> /dev/null; then
        print_status "ERROR" "Docker is not running"
        exit 1
    fi
    
    print_status "SUCCESS" "Docker is installed and running"
}

# Function to check if Docker Compose is available
check_docker_compose() {
    print_status "INFO" "Checking Docker Compose installation..."
    
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        print_status "ERROR" "Docker Compose is not installed"
        exit 1
    fi
    
    print_status "SUCCESS" "Docker Compose is available"
}

# Function to validate Docker Compose file syntax
validate_compose_syntax() {
    print_status "INFO" "Validating Docker Compose file syntax..."
    
    local compose_file="docker-compose.dev.yml"
    
    if [ ! -f "$compose_file" ]; then
        print_status "ERROR" "Docker Compose file $compose_file not found"
        exit 1
    fi
    
    # Check syntax
    if docker-compose -f "$compose_file" config &> /dev/null; then
        print_status "SUCCESS" "Docker Compose file syntax is valid"
    else
        print_status "ERROR" "Docker Compose file syntax is invalid"
        docker-compose -f "$compose_file" config
        exit 1
    fi
}

# Function to check if all required files exist
check_required_files() {
    print_status "INFO" "Checking required files..."
    
    local required_files=(
        "service_gateway/Dockerfile"
        "service_auth/Dockerfile"
        "service_streaming/Dockerfile"
        "service_entitlements/Dockerfile"
        "service_metrics/Dockerfile"
        "requirements-dev.txt"
        "scripts/init-db.sql"
    )
    
    local missing_files=()
    
    for file in "${required_files[@]}"; do
        if [ ! -f "$file" ]; then
            missing_files+=("$file")
        fi
    done
    
    if [ ${#missing_files[@]} -eq 0 ]; then
        print_status "SUCCESS" "All required files exist"
    else
        print_status "ERROR" "Missing required files:"
        for file in "${missing_files[@]}"; do
            echo "  - $file"
        done
        exit 1
    fi
}

# Function to build Docker images
build_images() {
    print_status "INFO" "Building Docker images..."
    
    local compose_file="docker-compose.dev.yml"
    
    # Build images
    if docker-compose -f "$compose_file" build --parallel; then
        print_status "SUCCESS" "Docker images built successfully"
    else
        print_status "ERROR" "Failed to build Docker images"
        exit 1
    fi
}

# Function to start services and check health
start_and_validate_services() {
    print_status "INFO" "Starting services and validating health..."
    
    local compose_file="docker-compose.dev.yml"
    
    # Start services
    if docker-compose -f "$compose_file" up -d; then
        print_status "SUCCESS" "Services started successfully"
    else
        print_status "ERROR" "Failed to start services"
        exit 1
    fi
    
    # Wait for services to be healthy
    print_status "INFO" "Waiting for services to be healthy..."
    
    local services=(
        "redis"
        "postgres"
        "mock-keycloak"
        "mock-kafka"
        "mock-clickhouse"
        "auth-service"
        "entitlements-service"
        "metrics-service"
        "streaming-service"
        "gateway-service"
    )
    
    local max_attempts=30
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        local all_healthy=true
        
        for service in "${services[@]}"; do
            if ! docker-compose -f "$compose_file" ps "$service" | grep -q "healthy"; then
                all_healthy=false
                break
            fi
        done
        
        if [ "$all_healthy" = true ]; then
            print_status "SUCCESS" "All services are healthy"
            break
        fi
        
        if [ $attempt -eq $max_attempts ]; then
            print_status "ERROR" "Services failed to become healthy within timeout"
            print_status "INFO" "Service status:"
            docker-compose -f "$compose_file" ps
            exit 1
        fi
        
        print_status "INFO" "Attempt $attempt/$max_attempts - waiting for services to be healthy..."
        sleep 10
        ((attempt++))
    done
}

# Function to test service endpoints
test_endpoints() {
    print_status "INFO" "Testing service endpoints..."
    
    local endpoints=(
        "http://localhost:8000/health:Gateway"
        "http://localhost:8001/health:Streaming"
        "http://localhost:8010/health:Auth"
        "http://localhost:8011/health:Entitlements"
        "http://localhost:8012/health:Metrics"
    )
    
    local failed_endpoints=()
    
    for endpoint in "${endpoints[@]}"; do
        local url=$(echo "$endpoint" | cut -d: -f1-3)
        local service=$(echo "$endpoint" | cut -d: -f4)
        
        if curl -f -s "$url" > /dev/null; then
            print_status "SUCCESS" "$service service endpoint is responding"
        else
            failed_endpoints+=("$service")
            print_status "ERROR" "$service service endpoint is not responding"
        fi
    done
    
    if [ ${#failed_endpoints[@]} -eq 0 ]; then
        print_status "SUCCESS" "All service endpoints are responding"
    else
        print_status "WARNING" "Some service endpoints are not responding:"
        for service in "${failed_endpoints[@]}"; do
            echo "  - $service"
        done
    fi
}

# Function to run smoke tests
run_smoke_tests() {
    print_status "INFO" "Running smoke tests..."
    
    # Test Gateway API
    if curl -f -s "http://localhost:8000/api/v1/status" > /dev/null; then
        print_status "SUCCESS" "Gateway API is responding"
    else
        print_status "ERROR" "Gateway API is not responding"
    fi
    
    # Test Auth Service
    if curl -f -s "http://localhost:8010/" > /dev/null; then
        print_status "SUCCESS" "Auth Service is responding"
    else
        print_status "ERROR" "Auth Service is not responding"
    fi
    
    # Test Entitlements Service
    if curl -f -s "http://localhost:8011/" > /dev/null; then
        print_status "SUCCESS" "Entitlements Service is responding"
    else
        print_status "ERROR" "Entitlements Service is not responding"
    fi
    
    # Test Metrics Service
    if curl -f -s "http://localhost:8012/" > /dev/null; then
        print_status "SUCCESS" "Metrics Service is responding"
    else
        print_status "ERROR" "Metrics Service is not responding"
    fi
    
    # Test Streaming Service
    if curl -f -s "http://localhost:8001/" > /dev/null; then
        print_status "SUCCESS" "Streaming Service is responding"
    else
        print_status "ERROR" "Streaming Service is not responding"
    fi
}

# Function to show service logs
show_logs() {
    print_status "INFO" "Showing service logs..."
    
    local compose_file="docker-compose.dev.yml"
    
    echo "=== Service Logs ==="
    docker-compose -f "$compose_file" logs --tail=20
}

# Function to cleanup
cleanup() {
    print_status "INFO" "Cleaning up..."
    
    local compose_file="docker-compose.dev.yml"
    
    if docker-compose -f "$compose_file" down; then
        print_status "SUCCESS" "Services stopped successfully"
    else
        print_status "WARNING" "Failed to stop some services"
    fi
}

# Main execution
main() {
    echo "=========================================="
    echo "254Carbon Access Layer - Docker Compose Validation"
    echo "=========================================="
    
    # Parse command line arguments
    local cleanup_only=false
    local skip_build=false
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --cleanup-only)
                cleanup_only=true
                shift
                ;;
            --skip-build)
                skip_build=true
                shift
                ;;
            -h|--help)
                echo "Usage: $0 [OPTIONS]"
                echo "Options:"
                echo "  --cleanup-only    Only cleanup existing services"
                echo "  --skip-build      Skip building images"
                echo "  -h, --help        Show this help message"
                exit 0
                ;;
            *)
                echo "Unknown option: $1"
                exit 1
                ;;
        esac
    done
    
    # Set trap to cleanup on exit
    trap cleanup EXIT
    
    if [ "$cleanup_only" = true ]; then
        cleanup
        exit 0
    fi
    
    # Run validation steps
    check_docker
    check_docker_compose
    validate_compose_syntax
    check_required_files
    
    if [ "$skip_build" = false ]; then
        build_images
    fi
    
    start_and_validate_services
    test_endpoints
    run_smoke_tests
    
    print_status "SUCCESS" "Docker Compose validation completed successfully!"
    print_status "INFO" "Services are running and healthy"
    print_status "INFO" "Use 'docker-compose -f docker-compose.dev.yml logs -f' to view logs"
    print_status "INFO" "Use 'docker-compose -f docker-compose.dev.yml down' to stop services"
    
    # Keep services running for manual testing
    print_status "INFO" "Services will continue running. Press Ctrl+C to stop."
    
    # Wait for user interrupt
    while true; do
        sleep 60
        print_status "INFO" "Services are still running..."
    done
}

# Run main function
main "$@"
