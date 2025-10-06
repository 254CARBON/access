#!/bin/bash

# 254Carbon Access Layer - Kubernetes Deployment Script
# Deploys the Access Layer to Kubernetes using kubectl or Helm

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
NAMESPACE="254carbon-access"
METHOD="kubectl"
ENVIRONMENT="production"
DRY_RUN=""
FORCE=""

# Help function
show_help() {
    echo "254Carbon Access Layer - Kubernetes Deployment Script"
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -m, --method METHOD    Deployment method (kubectl, helm) [default: kubectl]"
    echo "  -n, --namespace NS     Kubernetes namespace [default: 254carbon-access]"
    echo "  -e, --env ENV          Environment (dev, staging, production) [default: production]"
    echo "  -d, --dry-run          Perform a dry run (helm only)"
    echo "  -f, --force            Force deployment even if resources exist"
    echo "  -h, --help             Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                                    # Deploy with kubectl to production"
    echo "  $0 -m helm -e staging                # Deploy with Helm to staging"
    echo "  $0 -m helm -d                         # Dry run with Helm"
    echo "  $0 -n my-namespace -f                 # Deploy to custom namespace with force"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -m|--method)
            METHOD="$2"
            shift 2
            ;;
        -n|--namespace)
            NAMESPACE="$2"
            shift 2
            ;;
        -e|--env)
            ENVIRONMENT="$2"
            shift 2
            ;;
        -d|--dry-run)
            DRY_RUN="--dry-run"
            shift
            ;;
        -f|--force)
            FORCE="--force"
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

# Validate method
case $METHOD in
    kubectl|helm)
        ;;
    *)
        echo -e "${RED}Error: Invalid method '$METHOD'. Must be kubectl or helm.${NC}"
        exit 1
        ;;
esac

# Validate environment
case $ENVIRONMENT in
    dev|staging|production)
        ;;
    *)
        echo -e "${RED}Error: Invalid environment '$ENVIRONMENT'. Must be dev, staging, or production.${NC}"
        exit 1
        ;;
esac

# Check if kubectl is available
if ! command -v kubectl &> /dev/null; then
    echo -e "${RED}Error: kubectl is not installed or not in PATH.${NC}"
    exit 1
fi

# Check if helm is available (if using helm method)
if [[ "$METHOD" == "helm" ]] && ! command -v helm &> /dev/null; then
    echo -e "${RED}Error: helm is not installed or not in PATH.${NC}"
    exit 1
fi

# Check if we can connect to Kubernetes
if ! kubectl cluster-info &> /dev/null; then
    echo -e "${RED}Error: Cannot connect to Kubernetes cluster.${NC}"
    exit 1
fi

echo -e "${BLUE}Deploying 254Carbon Access Layer${NC}"
echo -e "${BLUE}Method: $METHOD${NC}"
echo -e "${BLUE}Namespace: $NAMESPACE${NC}"
echo -e "${BLUE}Environment: $ENVIRONMENT${NC}"
echo ""

# Create namespace if it doesn't exist
if ! kubectl get namespace "$NAMESPACE" &> /dev/null; then
    echo -e "${YELLOW}Creating namespace $NAMESPACE...${NC}"
    kubectl create namespace "$NAMESPACE"
else
    echo -e "${GREEN}Namespace $NAMESPACE already exists.${NC}"
fi

# Deploy based on method
case $METHOD in
    kubectl)
        echo -e "${YELLOW}Deploying with kubectl...${NC}"
        
        # Apply manifests in order
        echo "Applying namespace..."
        kubectl apply -f k8s/namespace.yaml
        
        echo "Applying ConfigMap..."
        kubectl apply -f k8s/configmap.yaml
        
        echo "Applying infrastructure services..."
        kubectl apply -f k8s/redis-deployment.yaml
        kubectl apply -f k8s/postgres-deployment.yaml
        kubectl apply -f k8s/kafka-deployment.yaml
        
        echo "Waiting for infrastructure to be ready..."
        kubectl wait --for=condition=available --timeout=300s deployment/redis-deployment -n "$NAMESPACE"
        kubectl wait --for=condition=available --timeout=300s deployment/postgres-deployment -n "$NAMESPACE"
        kubectl wait --for=condition=available --timeout=300s deployment/kafka-deployment -n "$NAMESPACE"
        
        echo "Applying application services..."
        kubectl apply -f k8s/auth-deployment.yaml
        kubectl apply -f k8s/entitlements-deployment.yaml
        kubectl apply -f k8s/metrics-deployment.yaml
        kubectl apply -f k8s/streaming-deployment.yaml
        kubectl apply -f k8s/gateway-deployment.yaml
        
        echo "Applying monitoring..."
        kubectl apply -f k8s/monitoring.yaml
        
        echo "Applying ingress..."
        kubectl apply -f k8s/ingress.yaml
        
        echo "Waiting for application services to be ready..."
        kubectl wait --for=condition=available --timeout=300s deployment/auth-deployment -n "$NAMESPACE"
        kubectl wait --for=condition=available --timeout=300s deployment/entitlements-deployment -n "$NAMESPACE"
        kubectl wait --for=condition=available --timeout=300s deployment/metrics-deployment -n "$NAMESPACE"
        kubectl wait --for=condition=available --timeout=300s deployment/streaming-deployment -n "$NAMESPACE"
        kubectl wait --for=condition=available --timeout=300s deployment/gateway-deployment -n "$NAMESPACE"
        ;;
        
    helm)
        echo -e "${YELLOW}Deploying with Helm...${NC}"
        
        # Update Helm dependencies
        echo "Updating Helm dependencies..."
        helm dependency update helm/254carbon-access-layer
        
        # Deploy with Helm
        echo "Deploying with Helm..."
        helm upgrade --install 254carbon-access-layer helm/254carbon-access-layer \
            --namespace "$NAMESPACE" \
            --create-namespace \
            --set config.environment="$ENVIRONMENT" \
            $DRY_RUN $FORCE
        
        if [[ -z "$DRY_RUN" ]]; then
            echo "Waiting for deployment to be ready..."
            kubectl wait --for=condition=available --timeout=600s deployment/254carbon-access-layer-gateway -n "$NAMESPACE"
        fi
        ;;
esac

if [[ -z "$DRY_RUN" ]]; then
    echo ""
    echo -e "${GREEN}Deployment completed successfully!${NC}"
    echo ""
    echo -e "${BLUE}Service Status:${NC}"
    kubectl get pods -n "$NAMESPACE"
    echo ""
    echo -e "${BLUE}Services:${NC}"
    kubectl get services -n "$NAMESPACE"
    echo ""
    echo -e "${BLUE}Ingress:${NC}"
    kubectl get ingress -n "$NAMESPACE"
    echo ""
    echo -e "${GREEN}Access Layer is now running in namespace: $NAMESPACE${NC}"
else
    echo -e "${GREEN}Dry run completed successfully!${NC}"
fi
