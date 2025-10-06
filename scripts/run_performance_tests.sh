#!/bin/bash

# Performance Testing Script for 254Carbon Access Layer
# Runs comprehensive performance tests for all services

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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
            echo -e "${BLUE}ℹ️  $message${NC}"
            ;;
    esac
}

# Function to check if service is running
check_service() {
    local service_name=$1
    local url=$2
    
    if curl -f -s "$url" > /dev/null 2>&1; then
        print_status "SUCCESS" "$service_name is running"
        return 0
    else
        print_status "ERROR" "$service_name is not running at $url"
        return 1
    fi
}

# Function to wait for service to be ready
wait_for_service() {
    local service_name=$1
    local url=$2
    local max_attempts=30
    local attempt=1
    
    print_status "INFO" "Waiting for $service_name to be ready..."
    
    while [ $attempt -le $max_attempts ]; do
        if curl -f -s "$url" > /dev/null 2>&1; then
            print_status "SUCCESS" "$service_name is ready"
            return 0
        fi
        
        if [ $attempt -eq $max_attempts ]; then
            print_status "ERROR" "$service_name failed to start within timeout"
            return 1
        fi
        
        print_status "INFO" "Attempt $attempt/$max_attempts - waiting for $service_name..."
        sleep 2
        ((attempt++))
    done
}

# Function to run locust test
run_locust_test() {
    local test_name=$1
    local user_class=$2
    local host=$3
    local users=$4
    local spawn_rate=$5
    local run_time=$6
    local output_dir=$7
    
    print_status "INFO" "Running $test_name test..."
    
    local output_file="$output_dir/${test_name}_results.html"
    
    if [ -n "$user_class" ]; then
        locust -f tests/performance/locustfile.py \
            "$user_class" \
            --host="$host" \
            --users="$users" \
            --spawn-rate="$spawn_rate" \
            --run-time="$run_time" \
            --headless \
            --html="$output_file" \
            --only-summary
    else
        locust -f tests/performance/locustfile.py \
            --host="$host" \
            --users="$users" \
            --spawn-rate="$spawn_rate" \
            --run-time="$run_time" \
            --headless \
            --html="$output_file" \
            --only-summary
    fi
    
    if [ $? -eq 0 ]; then
        print_status "SUCCESS" "$test_name test completed"
        print_status "INFO" "Results saved to: $output_file"
    else
        print_status "ERROR" "$test_name test failed"
        return 1
    fi
}

# Function to run WebSocket test
run_websocket_test() {
    local test_name=$1
    local max_connections=$2
    local message_rate=$3
    local test_duration=$4
    local output_dir=$5
    
    print_status "INFO" "Running $test_name WebSocket test..."
    
    local output_file="$output_dir/${test_name}_websocket_results.txt"
    
    python tests/performance/websocket_load_test.py \
        --max-connections="$max_connections" \
        --message-rate="$message_rate" \
        --test-duration="$test_duration" \
        --log-level="INFO" \
        > "$output_file" 2>&1
    
    if [ $? -eq 0 ]; then
        print_status "SUCCESS" "$test_name WebSocket test completed"
        print_status "INFO" "Results saved to: $output_file"
    else
        print_status "ERROR" "$test_name WebSocket test failed"
        return 1
    fi
}

# Function to generate performance report
generate_report() {
    local output_dir=$1
    local report_file="$output_dir/performance_report.md"
    
    print_status "INFO" "Generating performance report..."
    
    cat > "$report_file" << EOF
# Performance Test Report

Generated on: $(date)

## Test Summary

This report contains the results of comprehensive performance tests for the 254Carbon Access Layer.

## Test Results

### Locust Tests
EOF

    # Add Locust test results
    for html_file in "$output_dir"/*_results.html; do
        if [ -f "$html_file" ]; then
            test_name=$(basename "$html_file" _results.html)
            echo "- [$test_name]($(basename "$html_file"))" >> "$report_file"
        fi
    done
    
    cat >> "$report_file" << EOF

### WebSocket Tests
EOF

    # Add WebSocket test results
    for txt_file in "$output_dir"/*_websocket_results.txt; do
        if [ -f "$txt_file" ]; then
            test_name=$(basename "$txt_file" _websocket_results.txt)
            echo "- [$test_name]($(basename "$txt_file"))" >> "$report_file"
        fi
    done
    
    cat >> "$report_file" << EOF

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

## Recommendations

Based on the test results, consider the following optimizations:

1. **Database Optimization**
   - Monitor query performance
   - Implement connection pooling
   - Add appropriate indexes

2. **Caching Strategy**
   - Implement Redis caching
   - Optimize cache TTL values
   - Monitor cache hit ratios

3. **Load Balancing**
   - Distribute load across instances
   - Implement health checks
   - Monitor instance performance

4. **Resource Scaling**
   - Monitor CPU and memory usage
   - Implement auto-scaling
   - Plan for capacity growth

## Next Steps

1. Review test results
2. Identify performance bottlenecks
3. Implement optimizations
4. Re-run tests to validate improvements
5. Monitor production performance

EOF

    print_status "SUCCESS" "Performance report generated: $report_file"
}

# Main execution
main() {
    echo "=========================================="
    echo "254Carbon Access Layer - Performance Tests"
    echo "=========================================="
    
    # Parse command line arguments
    local test_scenario="medium"
    local output_dir="performance_results"
    local skip_checks=false
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --scenario)
                test_scenario="$2"
                shift 2
                ;;
            --output-dir)
                output_dir="$2"
                shift 2
                ;;
            --skip-checks)
                skip_checks=true
                shift
                ;;
            -h|--help)
                echo "Usage: $0 [OPTIONS]"
                echo "Options:"
                echo "  --scenario SCENARIO    Test scenario (light, medium, heavy, stress)"
                echo "  --output-dir DIR       Output directory for results"
                echo "  --skip-checks          Skip service health checks"
                echo "  -h, --help             Show this help message"
                exit 0
                ;;
            *)
                echo "Unknown option: $1"
                exit 1
                ;;
        esac
    done
    
    # Create output directory
    mkdir -p "$output_dir"
    
    # Check if services are running
    if [ "$skip_checks" = false ]; then
        print_status "INFO" "Checking service health..."
        
        services=(
            "Gateway:http://localhost:8000/health"
            "Streaming:http://localhost:8001/health"
            "Auth:http://localhost:8010/health"
            "Entitlements:http://localhost:8011/health"
            "Metrics:http://localhost:8012/health"
        )
        
        for service in "${services[@]}"; do
            IFS=':' read -r name url <<< "$service"
            if ! check_service "$name" "$url"; then
                print_status "ERROR" "Please start all services before running performance tests"
                exit 1
            fi
        done
    fi
    
    # Wait for services to be ready
    print_status "INFO" "Waiting for services to be ready..."
    wait_for_service "Gateway" "http://localhost:8000/health"
    wait_for_service "Streaming" "http://localhost:8001/health"
    wait_for_service "Auth" "http://localhost:8010/health"
    wait_for_service "Entitlements" "http://localhost:8011/health"
    wait_for_service "Metrics" "http://localhost:8012/health"
    
    # Set test parameters based on scenario
    case $test_scenario in
        "light")
            print_status "INFO" "Running LIGHT load scenario"
            gateway_users=10
            auth_users=5
            entitlements_users=5
            metrics_users=10
            streaming_users=5
            websocket_connections=20
            test_duration="5m"
            websocket_duration=300
            ;;
        "medium")
            print_status "INFO" "Running MEDIUM load scenario"
            gateway_users=50
            auth_users=25
            entitlements_users=25
            metrics_users=50
            streaming_users=25
            websocket_connections=100
            test_duration="10m"
            websocket_duration=600
            ;;
        "heavy")
            print_status "INFO" "Running HEAVY load scenario"
            gateway_users=100
            auth_users=50
            entitlements_users=50
            metrics_users=100
            streaming_users=50
            websocket_connections=200
            test_duration="15m"
            websocket_duration=900
            ;;
        "stress")
            print_status "INFO" "Running STRESS test scenario"
            gateway_users=200
            auth_users=100
            entitlements_users=100
            metrics_users=200
            streaming_users=100
            websocket_connections=500
            test_duration="20m"
            websocket_duration=1200
            ;;
        *)
            print_status "ERROR" "Invalid test scenario: $test_scenario"
            print_status "INFO" "Valid scenarios: light, medium, heavy, stress"
            exit 1
            ;;
    esac
    
    print_status "INFO" "Test parameters:"
    print_status "INFO" "  Gateway users: $gateway_users"
    print_status "INFO" "  Auth users: $auth_users"
    print_status "INFO" "  Entitlements users: $entitlements_users"
    print_status "INFO" "  Metrics users: $metrics_users"
    print_status "INFO" "  Streaming users: $streaming_users"
    print_status "INFO" "  WebSocket connections: $websocket_connections"
    print_status "INFO" "  Test duration: $test_duration"
    print_status "INFO" "  Output directory: $output_dir"
    
    # Run Locust tests
    print_status "INFO" "Starting Locust tests..."
    
    # Gateway Service tests
    run_locust_test "gateway" "GatewayRESTUser" "http://localhost:8000" "$gateway_users" "5" "$test_duration" "$output_dir"
    
    # Auth Service tests
    run_locust_test "auth" "AuthServiceUser" "http://localhost:8010" "$auth_users" "3" "$test_duration" "$output_dir"
    
    # Entitlements Service tests
    run_locust_test "entitlements" "EntitlementsServiceUser" "http://localhost:8011" "$entitlements_users" "3" "$test_duration" "$output_dir"
    
    # Metrics Service tests
    run_locust_test "metrics" "MetricsServiceUser" "http://localhost:8012" "$metrics_users" "5" "$test_duration" "$output_dir"
    
    # Streaming Service tests
    run_locust_test "streaming" "StreamingUser" "http://localhost:8001" "$streaming_users" "3" "$test_duration" "$output_dir"
    
    # Run WebSocket tests
    print_status "INFO" "Starting WebSocket tests..."
    
    # Light WebSocket test
    run_websocket_test "light" "20" "1.0" "300" "$output_dir"
    
    # Medium WebSocket test
    run_websocket_test "medium" "100" "2.0" "600" "$output_dir"
    
    # Heavy WebSocket test
    run_websocket_test "heavy" "200" "5.0" "900" "$output_dir"
    
    # Generate performance report
    generate_report "$output_dir"
    
    print_status "SUCCESS" "Performance tests completed successfully!"
    print_status "INFO" "Results saved to: $output_dir"
    print_status "INFO" "Report generated: $output_dir/performance_report.md"
    
    # Display summary
    echo ""
    echo "=========================================="
    echo "PERFORMANCE TEST SUMMARY"
    echo "=========================================="
    echo "Scenario: $test_scenario"
    echo "Duration: $test_duration"
    echo "Results: $output_dir"
    echo "Report: $output_dir/performance_report.md"
    echo "=========================================="
}

# Run main function
main "$@"
