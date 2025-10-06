#!/bin/bash

# Kafka topics initialization script for 254Carbon Access Layer
# This script creates the necessary Kafka topics for the streaming service

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

# Kafka configuration
KAFKA_BOOTSTRAP_SERVER=${KAFKA_BOOTSTRAP_SERVER:-"localhost:9092"}
REPLICATION_FACTOR=${REPLICATION_FACTOR:-1}
PARTITIONS=${PARTITIONS:-3}
RETENTION_MS=${RETENTION_MS:-604800000}  # 7 days

# Topic definitions
declare -a TOPICS=(
    "254carbon.pricing.curve.updates.v1"
    "254carbon.pricing.instrument.updates.v1"
    "254carbon.market.data.v1"
    "254carbon.metrics.streaming.v1"
    "254carbon.streaming.connection.events.v1"
    "254carbon.entitlements.rule.changes.v1"
    "254carbon.auth.token.events.v1"
)

# Function to check if Kafka is available
check_kafka() {
    print_status "Checking Kafka availability..."
    
    if ! command -v kafka-topics &> /dev/null; then
        print_error "kafka-topics command not found. Please ensure Kafka is installed and in PATH."
        exit 1
    fi
    
    # Test connection to Kafka
    if ! kafka-topics --bootstrap-server "$KAFKA_BOOTSTRAP_SERVER" --list > /dev/null 2>&1; then
        print_error "Cannot connect to Kafka at $KAFKA_BOOTSTRAP_SERVER"
        print_error "Please ensure Kafka is running and accessible"
        exit 1
    fi
    
    print_success "Kafka is available at $KAFKA_BOOTSTRAP_SERVER"
}

# Function to create a topic
create_topic() {
    local topic=$1
    
    print_status "Creating topic: $topic"
    
    # Check if topic already exists
    if kafka-topics --bootstrap-server "$KAFKA_BOOTSTRAP_SERVER" --list | grep -q "^$topic$"; then
        print_warning "Topic $topic already exists, skipping creation"
        return 0
    fi
    
    # Create the topic
    kafka-topics --bootstrap-server "$KAFKA_BOOTSTRAP_SERVER" \
        --create \
        --topic "$topic" \
        --partitions "$PARTITIONS" \
        --replication-factor "$REPLICATION_FACTOR" \
        --config retention.ms="$RETENTION_MS" \
        --config cleanup.policy="delete" \
        --config compression.type="gzip"
    
    if [ $? -eq 0 ]; then
        print_success "Topic $topic created successfully"
    else
        print_error "Failed to create topic $topic"
        return 1
    fi
}

# Function to list all topics
list_topics() {
    print_status "Listing all topics..."
    kafka-topics --bootstrap-server "$KAFKA_BOOTSTRAP_SERVER" --list
}

# Function to describe a topic
describe_topic() {
    local topic=$1
    print_status "Describing topic: $topic"
    kafka-topics --bootstrap-server "$KAFKA_BOOTSTRAP_SERVER" --describe --topic "$topic"
}

# Function to delete a topic (use with caution)
delete_topic() {
    local topic=$1
    print_warning "Deleting topic: $topic"
    kafka-topics --bootstrap-server "$KAFKA_BOOTSTRAP_SERVER" --delete --topic "$topic"
}

# Main execution
main() {
    print_status "254Carbon Access Layer - Kafka Topics Initialization"
    print_status "Kafka Bootstrap Server: $KAFKA_BOOTSTRAP_SERVER"
    print_status "Replication Factor: $REPLICATION_FACTOR"
    print_status "Partitions: $PARTITIONS"
    print_status "Retention: $RETENTION_MS ms"
    
    # Check Kafka availability
    check_kafka
    
    # Create topics
    print_status "Creating topics..."
    for topic in "${TOPICS[@]}"; do
        create_topic "$topic"
    done
    
    print_success "All topics created successfully!"
    
    # List all topics
    echo
    list_topics
    
    print_status "Kafka topics initialization completed!"
}

# Handle command line arguments
case "${1:-}" in
    "list")
        check_kafka
        list_topics
        ;;
    "describe")
        if [ -z "${2:-}" ]; then
            print_error "Please specify a topic name"
            exit 1
        fi
        check_kafka
        describe_topic "$2"
        ;;
    "delete")
        if [ -z "${2:-}" ]; then
            print_error "Please specify a topic name"
            exit 1
        fi
        check_kafka
        delete_topic "$2"
        ;;
    "help"|"-h"|"--help")
        echo "Usage: $0 [command] [topic_name]"
        echo ""
        echo "Commands:"
        echo "  (no command)  - Create all default topics"
        echo "  list          - List all topics"
        echo "  describe      - Describe a specific topic"
        echo "  delete        - Delete a specific topic (use with caution)"
        echo "  help          - Show this help message"
        echo ""
        echo "Environment variables:"
        echo "  KAFKA_BOOTSTRAP_SERVER - Kafka bootstrap server (default: localhost:9092)"
        echo "  REPLICATION_FACTOR     - Replication factor (default: 1)"
        echo "  PARTITIONS             - Number of partitions (default: 3)"
        echo "  RETENTION_MS           - Retention time in milliseconds (default: 604800000)"
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
