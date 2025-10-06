#!/bin/bash

# Development cluster startup script for 254Carbon Access Layer
# This script starts all services in development mode

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Service configurations
declare SERVICES=(
    ["gateway"]="8000"
    ["streaming"]="8001"
    ["auth"]="8010"
    ["entitlements"]="8011"
    ["metrics"]="8012"
)

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

# Function to check if port is available
check_port() {
    local port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        return 1
    else
        return 0
    fi
}

# Function to start a service
start_service() {
    local service=$1
    local port=$2
    
    print_status "Starting $service service on port $port..."
    
    # Check if port is available
    if ! check_port $port; then
        print_warning "Port $port is already in use. Skipping $service service."
        return 1
    fi
    
    # Change to service directory
    cd "service-$service"
    
    # Start the service in background
    nohup python -m uvicorn app.main:app --reload --port $port --host 0.0.0.0 > "../logs/$service.log" 2>&1 &
    local pid=$!
    
    # Save PID for cleanup
    echo $pid > "../logs/$service.pid"
    
    # Wait a moment and check if service started successfully
    sleep 2
    if kill -0 $pid 2>/dev/null; then
        print_success "$service service started successfully (PID: $pid)"
    else
        print_error "Failed to start $service service"
        return 1
    fi
    
    cd ..
    return 0
}

# Function to cleanup services
cleanup() {
    print_status "Cleaning up services..."
    
    for service in "${!SERVICES[@]}"; do
        local pid_file="logs/$service.pid"
        if [ -f "$pid_file" ]; then
            local pid=$(cat "$pid_file")
            if kill -0 $pid 2>/dev/null; then
                print_status "Stopping $service service (PID: $pid)..."
                kill $pid
                rm "$pid_file"
            fi
        fi
    done
    
    print_success "Cleanup completed"
    exit 0
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM

# Create logs directory
mkdir -p logs

# Check if we're in the right directory
if [ ! -f "Makefile" ]; then
    print_error "Please run this script from the project root directory"
    exit 1
fi

print_status "Starting 254Carbon Access Layer development cluster..."

# Start services
for service in "${!SERVICES[@]}"; do
    port=${SERVICES[$service]}
    start_service $service $port
done

print_success "All services started successfully!"
print_status "Service endpoints:"
for service in "${!SERVICES[@]}"; do
    port=${SERVICES[$service]}
    echo "  - $service: http://localhost:$port"
done

print_status "Health check endpoints:"
for service in "${!SERVICES[@]}"; do
    port=${SERVICES[$service]}
    echo "  - $service: http://localhost:$port/health"
done

print_status "Press Ctrl+C to stop all services"

# Keep script running and monitor services
while true; do
    sleep 10
    
    # Check if any service has died
    for service in "${!SERVICES[@]}"; do
        local pid_file="logs/$service.pid"
        if [ -f "$pid_file" ]; then
            local pid=$(cat "$pid_file")
            if ! kill -0 $pid 2>/dev/null; then
                print_error "$service service has stopped unexpectedly"
                cleanup
                exit 1
            fi
        fi
    done
done
