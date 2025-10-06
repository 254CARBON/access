#!/bin/bash

# 254Carbon Access Layer - Docker Compose Manager
# Manages different Docker Compose environments

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
ENVIRONMENT="dev"
ACTION="up"
SERVICES=""
DETACHED=""
BUILD=""
FORCE=""

# Help function
show_help() {
    echo "254Carbon Access Layer - Docker Compose Manager"
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -e, --env ENV        Environment (dev, test, prod) [default: dev]"
    echo "  -a, --action ACTION  Action (up, down, restart, logs, ps) [default: up]"
    echo "  -s, --services SVC   Comma-separated list of services to target"
    echo "  -d, --detached      Run in detached mode"
    echo "  -b, --build         Build images before starting"
    echo "  -f, --force         Force recreate containers"
    echo "  -h, --help          Show this help message"
    echo ""
    echo "Environments:"
    echo "  dev                 Development with mocks (docker-compose.dev.yml)"
    echo "  test                Test environment (docker-compose.test.yml)"
    echo "  prod                Production environment (docker-compose.prod.yml)"
    echo ""
    echo "Examples:"
    echo "  $0                                    # Start dev environment"
    echo "  $0 -e test -a up                     # Start test environment"
    echo "  $0 -e dev -a logs -s gateway-service # View gateway logs"
    echo "  $0 -e prod -a down                   # Stop production environment"
    echo "  $0 -e dev -a restart -b              # Restart dev with rebuild"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -e|--env)
            ENVIRONMENT="$2"
            shift 2
            ;;
        -a|--action)
            ACTION="$2"
            shift 2
            ;;
        -s|--services)
            SERVICES="$2"
            shift 2
            ;;
        -d|--detached)
            DETACHED="-d"
            shift
            ;;
        -b|--build)
            BUILD="--build"
            shift
            ;;
        -f|--force)
            FORCE="--force-recreate"
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            echo "Unknown option $1"
            show_help
            exit 1
            ;;
    esac
done

# Validate environment
case $ENVIRONMENT in
    dev|test|prod)
        ;;
    *)
        echo -e "${RED}Error: Invalid environment '$ENVIRONMENT'. Must be dev, test, or prod.${NC}"
        exit 1
        ;;
esac

# Validate action
case $ACTION in
    up|down|restart|logs|ps|exec)
        ;;
    *)
        echo -e "${RED}Error: Invalid action '$ACTION'. Must be up, down, restart, logs, ps, or exec.${NC}"
        exit 1
        ;;
esac

# Set compose file based on environment
case $ENVIRONMENT in
    dev)
        COMPOSE_FILE="docker-compose.dev.yml"
        ;;
    test)
        COMPOSE_FILE="docker-compose.test.yml"
        ;;
    prod)
        COMPOSE_FILE="docker-compose.prod.yml"
        ;;
esac

# Check if compose file exists
if [[ ! -f "$COMPOSE_FILE" ]]; then
    echo -e "${RED}Error: Compose file '$COMPOSE_FILE' not found.${NC}"
    exit 1
fi

# Build docker-compose command
COMPOSE_CMD="docker-compose -f $COMPOSE_FILE"

# Add services if specified
if [[ -n "$SERVICES" ]]; then
    COMPOSE_CMD="$COMPOSE_CMD $SERVICES"
fi

# Execute action
echo -e "${BLUE}Environment: $ENVIRONMENT${NC}"
echo -e "${BLUE}Action: $ACTION${NC}"
echo -e "${BLUE}Compose file: $COMPOSE_FILE${NC}"
echo ""

case $ACTION in
    up)
        echo -e "${GREEN}Starting services...${NC}"
        $COMPOSE_CMD up $DETACHED $BUILD $FORCE
        ;;
    down)
        echo -e "${YELLOW}Stopping services...${NC}"
        $COMPOSE_CMD down
        ;;
    restart)
        echo -e "${YELLOW}Restarting services...${NC}"
        $COMPOSE_CMD restart
        ;;
    logs)
        echo -e "${BLUE}Showing logs...${NC}"
        $COMPOSE_CMD logs -f
        ;;
    ps)
        echo -e "${BLUE}Service status:${NC}"
        $COMPOSE_CMD ps
        ;;
    exec)
        if [[ -z "$SERVICES" ]]; then
            echo -e "${RED}Error: Service name required for exec action.${NC}"
            exit 1
        fi
        echo -e "${BLUE}Executing command in $SERVICES...${NC}"
        $COMPOSE_CMD exec $SERVICES /bin/bash
        ;;
esac

echo -e "${GREEN}Done!${NC}"
