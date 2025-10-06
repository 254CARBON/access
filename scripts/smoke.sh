#!/bin/bash

# Smoke test script for 254Carbon Access Layer
# This script performs basic health checks on all services

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check service health
check_service_health() {
    local service=$1
    local port=$2
    local url="http://localhost:$port/health"
    
    print_status "Checking health of $service service at $url..."
    
    # Use curl with timeout
    if curl -f -s --max-time 10 "$url" > /dev/null 2>&1; then
        print_success "$service service is healthy"
        return 0
    else
        print_error "$service service health check failed"
        return 1
    fi
}

# Function to check service metrics endpoint
check_service_metrics() {
    local service=$1
    local port=$2
    local url="http://localhost:$port/metrics"
    
    print_status "Checking metrics endpoint of $service service at $url..."
    
    # Use curl with timeout
    if curl -f -s --max-time 10 "$url" > /dev/null 2>&1; then
        print_success "$service service metrics endpoint is accessible"
        return 0
    else
        print_warning "$service service metrics endpoint is not accessible"
        return 1
    fi
}

# Main smoke test function
run_smoke_tests() {
    local failed_services=()
    local total_services=0
    
    print_status "Starting smoke tests for 254Carbon Access Layer..."
    
    # Check each service
    local services="gateway:8000 streaming:8001 auth:8010 entitlements:8011 metrics:8012"
    
    for service_port in $services; do
        local service=$(echo $service_port | cut -d: -f1)
        local port=$(echo $service_port | cut -d: -f2)
        total_services=$((total_services + 1))
        
        # Health check
        if ! check_service_health $service $port; then
            failed_services+=($service)
        fi
        
        # Metrics check (optional)
        check_service_metrics $service $port
        
        echo ""
    done
    
    # Summary
    local passed_services=$((total_services - ${#failed_services[@]}))
    
    print_status "Smoke test summary:"
    print_status "  Total services: $total_services"
    print_success "  Passed: $passed_services"
    
    if [ ${#failed_services[@]} -gt 0 ]; then
        print_error "  Failed: ${#failed_services[@]}"
        print_error "  Failed services: ${failed_services[*]}"
        return 1
    else
        print_success "All services passed smoke tests!"
        return 0
    fi
}

# Check if curl is available
if ! command -v curl &> /dev/null; then
    print_error "curl is required but not installed"
    exit 1
fi

# Run smoke tests
if run_smoke_tests; then
    exit 0
else
    exit 1
fi