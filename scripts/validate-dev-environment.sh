#!/bin/bash

# Development environment validation script for 254Carbon Access Layer
# This script validates that the development environment is properly set up

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

# Configuration
SERVICES=("gateway" "streaming" "auth" "entitlements" "metrics")
PORTS=(8000 8001 8010 8011 8012)
INFRASTRUCTURE_SERVICES=("postgres" "redis" "kafka" "keycloak")
INFRASTRUCTURE_PORTS=(5432 6379 9092 8080)

# Validation results
VALIDATION_ERRORS=0
VALIDATION_WARNINGS=0

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check if a port is in use
port_in_use() {
    local port=$1
    if lsof -i :$port >/dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# Function to check Docker Compose
check_docker_compose() {
    print_status "Checking Docker Compose..."
    
    if ! command_exists docker; then
        print_error "Docker is not installed"
        ((VALIDATION_ERRORS++))
        return 1
    fi
    
    if ! command_exists docker-compose; then
        print_error "Docker Compose is not installed"
        ((VALIDATION_ERRORS++))
        return 1
    fi
    
    # Check Docker daemon
    if ! docker info >/dev/null 2>&1; then
        print_error "Docker daemon is not running"
        ((VALIDATION_ERRORS++))
        return 1
    fi
    
    print_success "Docker Compose is available"
    return 0
}

# Function to validate Docker Compose configuration
validate_docker_compose_config() {
    print_status "Validating Docker Compose configuration..."
    
    if [ ! -f "docker-compose.yml" ]; then
        print_error "docker-compose.yml not found"
        ((VALIDATION_ERRORS++))
        return 1
    fi
    
    # Validate configuration
    if ! docker-compose config >/dev/null 2>&1; then
        print_error "Docker Compose configuration is invalid"
        ((VALIDATION_ERRORS++))
        return 1
    fi
    
    print_success "Docker Compose configuration is valid"
    return 0
}

# Function to check service health
check_service_health() {
    local service=$1
    local port=$2
    
    print_status "Checking health of $service service..."
    
    # Check if service is running
    if ! docker-compose ps | grep -q "$service.*Up"; then
        print_error "Service $service is not running"
        ((VALIDATION_ERRORS++))
        return 1
    fi
    
    # Check health endpoint
    local health_url="http://localhost:$port/health"
    if curl -f -s "$health_url" >/dev/null 2>&1; then
        print_success "Service $service is healthy"
        return 0
    else
        print_error "Service $service health check failed"
        ((VALIDATION_ERRORS++))
        return 1
    fi
}

# Function to check infrastructure service
check_infrastructure_service() {
    local service=$1
    local port=$2
    
    print_status "Checking $service service..."
    
    # Check if service is running
    if ! docker-compose ps | grep -q "$service.*Up"; then
        print_error "Infrastructure service $service is not running"
        ((VALIDATION_ERRORS++))
        return 1
    fi
    
    # Check port accessibility
    if port_in_use "$port"; then
        print_success "Infrastructure service $service is accessible on port $port"
        return 0
    else
        print_error "Infrastructure service $service is not accessible on port $port"
        ((VALIDATION_ERRORS++))
        return 1
    fi
}

# Function to check Kafka topics
check_kafka_topics() {
    print_status "Checking Kafka topics..."
    
    # Wait for Kafka to be ready
    local max_attempts=30
    local attempt=0
    
    while [ $attempt -lt $max_attempts ]; do
        if docker-compose exec kafka kafka-topics --bootstrap-server localhost:9092 --list >/dev/null 2>&1; then
            break
        fi
        
        ((attempt++))
        sleep 2
    done
    
    if [ $attempt -eq $max_attempts ]; then
        print_error "Kafka is not ready after $max_attempts attempts"
        ((VALIDATION_ERRORS++))
        return 1
    fi
    
    # Check if topics exist
    local topics_output
    topics_output=$(docker-compose exec kafka kafka-topics --bootstrap-server localhost:9092 --list 2>/dev/null || echo "")
    
    if [ -z "$topics_output" ]; then
        print_warning "No Kafka topics found. Run './scripts/kafka_topics.sh' to create them."
        ((VALIDATION_WARNINGS++))
    else
        print_success "Kafka topics are available"
    fi
    
    return 0
}

# Function to check environment variables
check_environment_variables() {
    print_status "Checking environment variables..."
    
    local required_vars=(
        "ACCESS_ENV"
        "ACCESS_POSTGRES_DSN"
        "ACCESS_REDIS_URL"
        "ACCESS_KAFKA_BOOTSTRAP"
    )
    
    local missing_vars=()
    
    for var in "${required_vars[@]}"; do
        if [ -z "${!var}" ]; then
            missing_vars+=("$var")
        fi
    done
    
    if [ ${#missing_vars[@]} -gt 0 ]; then
        print_warning "Missing environment variables: ${missing_vars[*]}"
        print_warning "Consider setting these in your .env file"
        ((VALIDATION_WARNINGS++))
    else
        print_success "Required environment variables are set"
    fi
    
    return 0
}

# Function to check file permissions
check_file_permissions() {
    print_status "Checking file permissions..."
    
    local scripts=(
        "scripts/kafka_topics.sh"
        "scripts/validate-openapi.py"
        "scripts/run_performance_tests.sh"
    )
    
    local permission_issues=()
    
    for script in "${scripts[@]}"; do
        if [ -f "$script" ] && [ ! -x "$script" ]; then
            permission_issues+=("$script")
        fi
    done
    
    if [ ${#permission_issues[@]} -gt 0 ]; then
        print_warning "Scripts without execute permission: ${permission_issues[*]}"
        print_warning "Run 'chmod +x' on these files"
        ((VALIDATION_WARNINGS++))
    else
        print_success "File permissions are correct"
    fi
    
    return 0
}

# Function to check Python dependencies
check_python_dependencies() {
    print_status "Checking Python dependencies..."
    
    if ! command_exists python3; then
        print_error "Python 3 is not installed"
        ((VALIDATION_ERRORS++))
        return 1
    fi
    
    # Check Python version
    local python_version
    python_version=$(python3 --version 2>&1 | cut -d' ' -f2)
    local major_version
    major_version=$(echo "$python_version" | cut -d'.' -f1)
    local minor_version
    minor_version=$(echo "$python_version" | cut -d'.' -f2)
    
    if [ "$major_version" -lt 3 ] || ([ "$major_version" -eq 3 ] && [ "$minor_version" -lt 8 ]); then
        print_error "Python 3.8+ is required, found $python_version"
        ((VALIDATION_ERRORS++))
        return 1
    fi
    
    # Check if requirements file exists
    if [ ! -f "requirements-dev.txt" ]; then
        print_warning "requirements-dev.txt not found"
        ((VALIDATION_WARNINGS++))
    else
        print_success "Python dependencies file found"
    fi
    
    return 0
}

# Function to run integration tests
run_integration_tests() {
    print_status "Running integration tests..."
    
    if [ ! -d "tests/integration" ]; then
        print_warning "Integration tests directory not found"
        ((VALIDATION_WARNINGS++))
        return 0
    fi
    
    # Check if pytest is available
    if ! command_exists pytest; then
        print_warning "pytest not found, skipping integration tests"
        ((VALIDATION_WARNINGS++))
        return 0
    fi
    
    # Run a simple integration test
    if python3 -m pytest tests/integration/ -v --tb=short >/dev/null 2>&1; then
        print_success "Integration tests passed"
        return 0
    else
        print_warning "Integration tests failed or had issues"
        ((VALIDATION_WARNINGS++))
        return 0
    fi
}

# Function to check service logs for errors
check_service_logs() {
    print_status "Checking service logs for errors..."
    
    local error_count=0
    
    for service in "${SERVICES[@]}"; do
        # Check for ERROR level logs in the last 100 lines
        local error_logs
        error_logs=$(docker-compose logs --tail=100 "$service" 2>/dev/null | grep -i "error" | wc -l)
        
        if [ "$error_logs" -gt 0 ]; then
            print_warning "Service $service has $error_logs error log entries"
            ((VALIDATION_WARNINGS++))
            ((error_count++))
        fi
    done
    
    if [ $error_count -eq 0 ]; then
        print_success "No error logs found in services"
    fi
    
    return 0
}

# Function to generate validation report
generate_report() {
    print_status "Generating validation report..."
    
    local report_file="validation-report.txt"
    
    cat > "$report_file" << EOF
254Carbon Access Layer - Development Environment Validation Report
Generated on: $(date)

SUMMARY:
- Errors: $VALIDATION_ERRORS
- Warnings: $VALIDATION_WARNINGS

SERVICES STATUS:
EOF
    
    for i in "${!SERVICES[@]}"; do
        local service="${SERVICES[$i]}"
        local port="${PORTS[$i]}"
        
        if docker-compose ps | grep -q "$service.*Up"; then
            echo "- $service: Running on port $port" >> "$report_file"
        else
            echo "- $service: Not running" >> "$report_file"
        fi
    done
    
    echo "" >> "$report_file"
    echo "INFRASTRUCTURE STATUS:" >> "$report_file"
    
    for i in "${!INFRASTRUCTURE_SERVICES[@]}"; do
        local service="${INFRASTRUCTURE_SERVICES[$i]}"
        local port="${INFRASTRUCTURE_PORTS[$i]}"
        
        if docker-compose ps | grep -q "$service.*Up"; then
            echo "- $service: Running on port $port" >> "$report_file"
        else
            echo "- $service: Not running" >> "$report_file"
        fi
    done
    
    echo "" >> "$report_file"
    echo "RECOMMENDATIONS:" >> "$report_file"
    
    if [ $VALIDATION_ERRORS -gt 0 ]; then
        echo "- Fix validation errors before proceeding" >> "$report_file"
    fi
    
    if [ $VALIDATION_WARNINGS -gt 0 ]; then
        echo "- Address validation warnings for optimal setup" >> "$report_file"
    fi
    
    if [ $VALIDATION_ERRORS -eq 0 ] && [ $VALIDATION_WARNINGS -eq 0 ]; then
        echo "- Development environment is ready for use" >> "$report_file"
    fi
    
    print_success "Validation report generated: $report_file"
}

# Main validation function
main() {
    print_status "254Carbon Access Layer - Development Environment Validation"
    print_status "=========================================================="
    
    # Check prerequisites
    check_docker_compose
    validate_docker_compose_config
    check_python_dependencies
    check_file_permissions
    check_environment_variables
    
    # Check infrastructure services
    for i in "${!INFRASTRUCTURE_SERVICES[@]}"; do
        check_infrastructure_service "${INFRASTRUCTURE_SERVICES[$i]}" "${INFRASTRUCTURE_PORTS[$i]}"
    done
    
    # Check application services
    for i in "${!SERVICES[@]}"; do
        check_service_health "${SERVICES[$i]}" "${PORTS[$i]}"
    done
    
    # Check Kafka topics
    check_kafka_topics
    
    # Check service logs
    check_service_logs
    
    # Run integration tests
    run_integration_tests
    
    # Generate report
    generate_report
    
    # Print summary
    echo
    print_status "Validation Summary:"
    print_status "=================="
    
    if [ $VALIDATION_ERRORS -gt 0 ]; then
        print_error "Validation completed with $VALIDATION_ERRORS errors"
        print_error "Please fix the errors before proceeding"
    fi
    
    if [ $VALIDATION_WARNINGS -gt 0 ]; then
        print_warning "Validation completed with $VALIDATION_WARNINGS warnings"
        print_warning "Consider addressing the warnings for optimal setup"
    fi
    
    if [ $VALIDATION_ERRORS -eq 0 ] && [ $VALIDATION_WARNINGS -eq 0 ]; then
        print_success "Validation completed successfully!"
        print_success "Development environment is ready for use"
    fi
    
    # Exit with appropriate code
    if [ $VALIDATION_ERRORS -gt 0 ]; then
        exit 1
    else
        exit 0
    fi
}

# Handle command line arguments
case "${1:-}" in
    "help"|"-h"|"--help")
        echo "Usage: $0 [command]"
        echo ""
        echo "Commands:"
        echo "  (no command)  - Run full validation"
        echo "  help          - Show this help message"
        echo ""
        echo "This script validates the development environment setup."
        echo "It checks Docker Compose, services, infrastructure, and more."
        ;;
    "")
        main
        ;;
    *)
        print_error "Unknown command: $1"
        echo "Use '$0 help' for usage information"
        exit 1
        ;;
esac
