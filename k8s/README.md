# 254Carbon Access Layer - Kubernetes Deployment

This directory contains Kubernetes manifests and Helm charts for deploying the 254Carbon Access Layer to Kubernetes clusters.

## Quick Start

### Prerequisites

- Kubernetes cluster (1.19+)
- kubectl configured to access your cluster
- Helm 3.x (for Helm deployment method)
- NGINX Ingress Controller (for external access)
- cert-manager (for TLS certificates)

### Deployment Methods

#### Method 1: kubectl (Direct)

```bash
# Deploy all services
./scripts/deploy-k8s.sh

# Deploy to custom namespace
./scripts/deploy-k8s.sh -n my-namespace

# Deploy to staging environment
./scripts/deploy-k8s.sh -e staging
```

#### Method 2: Helm

```bash
# Deploy with Helm
./scripts/deploy-k8s.sh -m helm

# Dry run first
./scripts/deploy-k8s.sh -m helm -d

# Deploy to staging
./scripts/deploy-k8s.sh -m helm -e staging
```

## Architecture

The deployment includes:

### Application Services
- **Gateway Service** (3 replicas): API Gateway with rate limiting and caching
- **Streaming Service** (2 replicas): WebSocket and SSE streaming
- **Auth Service** (2 replicas): JWT verification and user management
- **Entitlements Service** (2 replicas): Access control and permissions
- **Metrics Service** (1 replica): Metrics collection and export

### Infrastructure Services
- **Redis**: Caching and rate limiting
- **PostgreSQL**: Entitlements persistence
- **Kafka + Zookeeper**: Message streaming

### Monitoring Stack
- **Prometheus**: Metrics collection
- **Grafana**: Dashboards and visualization

## Configuration

### Environment Variables

All services are configured via a ConfigMap (`access-config`):

```yaml
ACCESS_ENV: "production"
ACCESS_LOG_LEVEL: "info"
ACCESS_REDIS_URL: "redis://redis-service:6379/0"
ACCESS_POSTGRES_DSN: "postgresql://access:access@postgres-service:5432/access"
ACCESS_KAFKA_BOOTSTRAP: "kafka-service:9092"
ACCESS_JWKS_URL: "http://keycloak-service:8080/realms/254carbon/protocol/openid-connect/certs"
ACCESS_AUTH_SERVICE_URL: "http://auth-service:8010"
ACCESS_ENTITLEMENTS_SERVICE_URL: "http://entitlements-service:8011"
ACCESS_METRICS_SERVICE_URL: "http://metrics-service:8012"
ACCESS_ENABLE_TRACING: "true"
ACCESS_OTEL_EXPORTER: "http://otel-collector:4318"
```

### Resource Limits

Each service has defined resource requests and limits:

| Service | CPU Request | CPU Limit | Memory Request | Memory Limit |
|---------|-------------|-----------|----------------|--------------|
| Gateway | 250m | 500m | 256Mi | 512Mi |
| Streaming | 500m | 1000m | 512Mi | 1Gi |
| Auth | 100m | 250m | 128Mi | 256Mi |
| Entitlements | 250m | 500m | 256Mi | 512Mi |
| Metrics | 500m | 1000m | 512Mi | 1Gi |

## Networking

### Internal Communication

Services communicate internally via ClusterIP services:
- `gateway-service:8000`
- `streaming-service:8001`
- `auth-service:8010`
- `entitlements-service:8011`
- `metrics-service:8012`

### External Access

External access is provided via Ingress:

- **API Gateway**: `https://api.254carbon.local/`
- **Streaming**: `https://stream.254carbon.local/ws/` and `https://stream.254carbon.local/sse/`

### DNS Configuration

Add these entries to your DNS or `/etc/hosts`:

```
api.254carbon.local     <ingress-ip>
stream.254carbon.local  <ingress-ip>
```

## Monitoring

### Prometheus

Prometheus is available at `http://prometheus-service:9090` (internal) or via port-forward:

```bash
kubectl port-forward svc/prometheus-service 9090:9090 -n 254carbon-access
```

### Grafana

Grafana is available at `http://grafana-service:3000` (internal) or via port-forward:

```bash
kubectl port-forward svc/grafana-service 3000:3000 -n 254carbon-access
```

Default credentials:
- Username: `admin`
- Password: `admin123`

## Health Checks

All services include liveness and readiness probes:

- **Liveness**: HTTP GET `/health` (30s initial delay, 10s interval)
- **Readiness**: HTTP GET `/health` (5s initial delay, 5s interval)

## Persistent Storage

The following services use persistent volumes:

- **Redis**: 1Gi PVC for data persistence
- **PostgreSQL**: 5Gi PVC for database storage
- **Prometheus**: 10Gi PVC for metrics storage
- **Grafana**: 5Gi PVC for dashboard storage

## Security

### Pod Security

All pods run with:
- Non-root user (UID 1000)
- Read-only root filesystem
- Dropped capabilities
- Security context constraints

### Network Policies

Network policies can be enabled to restrict pod-to-pod communication:

```yaml
networkPolicy:
  enabled: true
```

### Secrets

Sensitive data is stored in Kubernetes secrets:
- `postgres-secret`: Database credentials
- `grafana-secret`: Grafana admin password

## Scaling

### Horizontal Pod Autoscaler

HPA can be enabled for each service:

```yaml
autoscaling:
  enabled: true
  minReplicas: 2
  maxReplicas: 10
  targetCPUUtilizationPercentage: 80
  targetMemoryUtilizationPercentage: 80
```

### Vertical Pod Autoscaler

VPA can be used to automatically adjust resource requests based on usage patterns.

## Troubleshooting

### Common Issues

1. **Services not starting**: Check pod logs
   ```bash
   kubectl logs -f deployment/gateway-deployment -n 254carbon-access
   ```

2. **Database connection issues**: Verify PostgreSQL is running
   ```bash
   kubectl get pods -n 254carbon-access | grep postgres
   ```

3. **Ingress not working**: Check ingress controller and DNS
   ```bash
   kubectl get ingress -n 254carbon-access
   ```

### Useful Commands

```bash
# Check all resources
kubectl get all -n 254carbon-access

# Check pod status
kubectl get pods -n 254carbon-access

# Check service endpoints
kubectl get endpoints -n 254carbon-access

# Check ingress
kubectl get ingress -n 254carbon-access

# Port forward for testing
kubectl port-forward svc/gateway-service 8000:8000 -n 254carbon-access

# View logs
kubectl logs -f deployment/gateway-deployment -n 254carbon-access

# Describe pod for debugging
kubectl describe pod <pod-name> -n 254carbon-access
```

## Customization

### Helm Values

Customize the deployment by modifying `helm/254carbon-access-layer/values.yaml`:

```yaml
# Scale services
gateway:
  replicaCount: 5

# Change resource limits
gateway:
  resources:
    requests:
      memory: "512Mi"
      cpu: "500m"
    limits:
      memory: "1Gi"
      cpu: "1000m"

# Enable autoscaling
gateway:
  autoscaling:
    enabled: true
    minReplicas: 3
    maxReplicas: 20
```

### Environment-Specific Configurations

Create environment-specific values files:

```bash
# values-dev.yaml
config:
  environment: "development"
  logLevel: "debug"

# values-staging.yaml
config:
  environment: "staging"
  logLevel: "info"

# values-prod.yaml
config:
  environment: "production"
  logLevel: "warn"
```

Deploy with specific values:

```bash
helm upgrade --install 254carbon-access-layer helm/254carbon-access-layer \
  --namespace 254carbon-access \
  --values helm/254carbon-access-layer/values-prod.yaml
```

## Backup and Recovery

### Database Backup

```bash
# Create backup
kubectl exec -it deployment/postgres-deployment -n 254carbon-access -- \
  pg_dump -U access access > backup.sql

# Restore backup
kubectl exec -i deployment/postgres-deployment -n 254carbon-access -- \
  psql -U access access < backup.sql
```

### Persistent Volume Backup

Use your cluster's backup solution (e.g., Velero) to backup persistent volumes.

## Updates and Rollbacks

### Rolling Updates

Kubernetes performs rolling updates by default:

```bash
# Update image
kubectl set image deployment/gateway-deployment gateway=ghcr.io/254carbon/gateway:v2.0.0 -n 254carbon-access

# Check rollout status
kubectl rollout status deployment/gateway-deployment -n 254carbon-access
```

### Rollbacks

```bash
# Rollback to previous version
kubectl rollout undo deployment/gateway-deployment -n 254carbon-access

# Rollback to specific revision
kubectl rollout undo deployment/gateway-deployment --to-revision=2 -n 254carbon-access
```

## Production Considerations

### High Availability

- Deploy across multiple availability zones
- Use anti-affinity rules to distribute pods
- Configure multiple replicas for each service

### Monitoring and Alerting

- Set up Prometheus alerts for critical metrics
- Configure Grafana dashboards for key performance indicators
- Implement log aggregation (e.g., ELK stack)

### Security

- Enable network policies
- Use Pod Security Standards
- Implement RBAC for service accounts
- Regular security scanning of images

### Performance

- Tune resource requests and limits based on usage
- Implement horizontal pod autoscaling
- Use cluster autoscaling for node management
- Optimize database queries and caching

## Support

For issues and questions:
- Check the troubleshooting section above
- Review pod logs and events
- Consult the main project README
- Contact the 254Carbon team
