# Production Runbooks

This document provides step-by-step procedures for common production operations and incident response for the 254Carbon Access Layer.

## Table of Contents

- [Emergency Procedures](#emergency-procedures)
- [Service Management](#service-management)
- [Deployment Procedures](#deployment-procedures)
- [Monitoring and Alerting](#monitoring-and-alerting)
- [Troubleshooting](#troubleshooting)
- [Maintenance Procedures](#maintenance-procedures)
- [Security Procedures](#security-procedures)

## Emergency Procedures

### Service Outage Response

#### 1. Initial Assessment (0-5 minutes)

**Check Service Status**
```bash
# Check all services
kubectl get pods -n 254carbon-access

# Check service health
kubectl get services -n 254carbon-access

# Check recent events
kubectl get events -n 254carbon-access --sort-by='.lastTimestamp'
```

**Check Monitoring Dashboards**
- Access Grafana: https://grafana.254carbon.com
- Check Prometheus: https://prometheus.254carbon.com
- Review alert notifications in Slack: #alerts-critical

#### 2. Identify Affected Services (5-10 minutes)

**Check Service Logs**
```bash
# Gateway service
kubectl logs -f deployment/gateway-deployment -n 254carbon-access

# Streaming service
kubectl logs -f deployment/streaming-deployment -n 254carbon-access

# Auth service
kubectl logs -f deployment/auth-deployment -n 254carbon-access

# Entitlements service
kubectl logs -f deployment/entitlements-deployment -n 254carbon-access

# Metrics service
kubectl logs -f deployment/metrics-deployment -n 254carbon-access
```

**Check Infrastructure Services**
```bash
# PostgreSQL
kubectl logs -f deployment/postgres-deployment -n 254carbon-access

# Redis
kubectl logs -f deployment/redis-deployment -n 254carbon-access

# Kafka
kubectl logs -f deployment/kafka-deployment -n 254carbon-access

# Keycloak
kubectl logs -f deployment/keycloak-deployment -n 254carbon-access
```

#### 3. Immediate Response Actions (10-15 minutes)

**Restart Affected Services**
```bash
# Restart specific service
kubectl rollout restart deployment/<service-name> -n 254carbon-access

# Check rollout status
kubectl rollout status deployment/<service-name> -n 254carbon-access
```

**Scale Up Services**
```bash
# Scale up service
kubectl scale deployment/<service-name> --replicas=5 -n 254carbon-access

# Check scaling status
kubectl get pods -n 254carbon-access -l app=<service-name>
```

**Check Resource Usage**
```bash
# Check node resources
kubectl top nodes

# Check pod resources
kubectl top pods -n 254carbon-access
```

#### 4. Communication and Escalation (15-30 minutes)

**Internal Communication**
- Update incident channel: #incidents
- Notify on-call engineer: @oncall
- Update status page: https://status.254carbon.com

**External Communication**
- Send customer notification if needed
- Update support tickets
- Document incident timeline

### Database Outage Response

#### 1. Check Database Status
```bash
# Check PostgreSQL pods
kubectl get pods -n 254carbon-access -l app=postgres

# Check database connectivity
kubectl exec -it deployment/postgres-deployment -n 254carbon-access -- psql -U access -d access -c "SELECT 1;"

# Check database logs
kubectl logs -f deployment/postgres-deployment -n 254carbon-access
```

#### 2. Database Recovery Actions
```bash
# Restart PostgreSQL
kubectl rollout restart deployment/postgres-deployment -n 254carbon-access

# Check persistent volume
kubectl get pvc -n 254carbon-access

# Check storage usage
kubectl exec -it deployment/postgres-deployment -n 254carbon-access -- df -h
```

#### 3. Data Recovery Procedures
```bash
# Create backup before recovery
kubectl exec -it deployment/postgres-deployment -n 254carbon-access -- pg_dump -U access access > backup-$(date +%Y%m%d-%H%M%S).sql

# Restore from backup if needed
kubectl exec -i deployment/postgres-deployment -n 254carbon-access -- psql -U access access < backup-20240101-120000.sql
```

### Redis Outage Response

#### 1. Check Redis Status
```bash
# Check Redis pods
kubectl get pods -n 254carbon-access -l app=redis

# Check Redis connectivity
kubectl exec -it deployment/redis-deployment -n 254carbon-access -- redis-cli ping

# Check Redis logs
kubectl logs -f deployment/redis-deployment -n 254carbon-access
```

#### 2. Redis Recovery Actions
```bash
# Restart Redis
kubectl rollout restart deployment/redis-deployment -n 254carbon-access

# Check Redis memory usage
kubectl exec -it deployment/redis-deployment -n 254carbon-access -- redis-cli info memory

# Clear Redis cache if needed
kubectl exec -it deployment/redis-deployment -n 254carbon-access -- redis-cli flushall
```

### Kafka Outage Response

#### 1. Check Kafka Status
```bash
# Check Kafka pods
kubectl get pods -n 254carbon-access -l app=kafka

# Check Kafka connectivity
kubectl exec -it deployment/kafka-deployment -n 254carbon-access -- kafka-topics --bootstrap-server localhost:9092 --list

# Check Kafka logs
kubectl logs -f deployment/kafka-deployment -n 254carbon-access
```

#### 2. Kafka Recovery Actions
```bash
# Restart Kafka
kubectl rollout restart deployment/kafka-deployment -n 254carbon-access

# Check Kafka topics
kubectl exec -it deployment/kafka-deployment -n 254carbon-access -- kafka-topics --bootstrap-server localhost:9092 --describe

# Check consumer groups
kubectl exec -it deployment/kafka-deployment -n 254carbon-access -- kafka-consumer-groups --bootstrap-server localhost:9092 --list
```

## Service Management

### Service Deployment

#### 1. Pre-deployment Checklist
- [ ] Review change request
- [ ] Check current service status
- [ ] Verify backup procedures
- [ ] Notify stakeholders
- [ ] Prepare rollback plan

#### 2. Deployment Procedure
```bash
# Update image tag
kubectl set image deployment/<service-name> <service-name>=ghcr.io/254carbon/access-layer-<service-name>:v1.0.1 -n 254carbon-access

# Monitor deployment
kubectl rollout status deployment/<service-name> -n 254carbon-access

# Verify deployment
kubectl get pods -n 254carbon-access -l app=<service-name>
```

#### 3. Post-deployment Verification
```bash
# Check service health
kubectl get pods -n 254carbon-access -l app=<service-name>

# Check service logs
kubectl logs -f deployment/<service-name> -n 254carbon-access

# Test service endpoints
curl -f http://<service-name>-service:8000/health
```

### Service Scaling

#### 1. Horizontal Scaling
```bash
# Scale up service
kubectl scale deployment/<service-name> --replicas=5 -n 254carbon-access

# Check scaling status
kubectl get pods -n 254carbon-access -l app=<service-name>

# Monitor resource usage
kubectl top pods -n 254carbon-access -l app=<service-name>
```

#### 2. Vertical Scaling
```bash
# Update resource limits
kubectl patch deployment/<service-name> -n 254carbon-access -p '{"spec":{"template":{"spec":{"containers":[{"name":"<service-name>","resources":{"limits":{"memory":"2Gi","cpu":"1000m"}}}]}}}}'

# Restart deployment
kubectl rollout restart deployment/<service-name> -n 254carbon-access
```

### Service Rollback

#### 1. Rollback Procedure
```bash
# Check deployment history
kubectl rollout history deployment/<service-name> -n 254carbon-access

# Rollback to previous version
kubectl rollout undo deployment/<service-name> -n 254carbon-access

# Monitor rollback
kubectl rollout status deployment/<service-name> -n 254carbon-access
```

#### 2. Rollback Verification
```bash
# Check service status
kubectl get pods -n 254carbon-access -l app=<service-name>

# Check service logs
kubectl logs -f deployment/<service-name> -n 254carbon-access

# Test service functionality
curl -f http://<service-name>-service:8000/health
```

## Deployment Procedures

### Blue-Green Deployment

#### 1. Prepare Green Environment
```bash
# Deploy green version
kubectl apply -f k8s/green-deployment.yaml -n 254carbon-access

# Wait for green deployment to be ready
kubectl wait --for=condition=ready pod -l app=<service-name>,version=green -n 254carbon-access --timeout=300s
```

#### 2. Switch Traffic
```bash
# Update service to point to green deployment
kubectl patch service <service-name>-service -n 254carbon-access -p '{"spec":{"selector":{"version":"green"}}}'

# Verify traffic switch
kubectl get pods -n 254carbon-access -l app=<service-name>
```

#### 3. Cleanup Blue Environment
```bash
# Remove blue deployment
kubectl delete deployment <service-name>-blue -n 254carbon-access

# Verify cleanup
kubectl get pods -n 254carbon-access -l app=<service-name>
```

### Canary Deployment

#### 1. Deploy Canary Version
```bash
# Deploy canary version
kubectl apply -f k8s/canary-deployment.yaml -n 254carbon-access

# Wait for canary deployment to be ready
kubectl wait --for=condition=ready pod -l app=<service-name>,version=canary -n 254carbon-access --timeout=300s
```

#### 2. Monitor Canary Performance
```bash
# Check canary metrics
kubectl logs -f deployment/<service-name>-canary -n 254carbon-access

# Monitor error rates
kubectl exec -it deployment/<service-name>-canary -n 254carbon-access -- curl -s http://localhost:8000/metrics | grep error_rate
```

#### 3. Promote Canary to Production
```bash
# Scale up canary
kubectl scale deployment/<service-name>-canary --replicas=3 -n 254carbon-access

# Scale down stable
kubectl scale deployment/<service-name>-stable --replicas=0 -n 254carbon-access

# Update service selector
kubectl patch service <service-name>-service -n 254carbon-access -p '{"spec":{"selector":{"version":"canary"}}}'
```

## Monitoring and Alerting

### Alert Response Procedures

#### 1. Critical Alerts
- **Response Time**: < 5 minutes
- **Escalation**: Immediate notification to on-call engineer
- **Communication**: Update incident channel

#### 2. Warning Alerts
- **Response Time**: < 15 minutes
- **Escalation**: Notify team lead if not resolved
- **Communication**: Update team channel

#### 3. Alert Acknowledgment
```bash
# Acknowledge alert in Alertmanager
curl -X POST http://alertmanager-service:9093/api/v1/alerts \
  -H "Content-Type: application/json" \
  -d '[{"labels":{"alertname":"ServiceDown","instance":"service-1"}}]'
```

### Monitoring Dashboard Access

#### 1. Grafana Dashboards
- **URL**: https://grafana.254carbon.com
- **Credentials**: Check password manager
- **Dashboards**: 
  - Gateway Service Dashboard
  - Streaming Service Dashboard
  - Microservices Overview Dashboard

#### 2. Prometheus Queries
```bash
# Check service uptime
up{job="gateway"}

# Check error rate
rate(gateway_requests_total{status=~"5.."}[5m])

# Check response time
histogram_quantile(0.95, rate(gateway_request_duration_seconds_bucket[5m]))
```

## Troubleshooting

### Common Issues and Solutions

#### 1. High Memory Usage
```bash
# Check memory usage
kubectl top pods -n 254carbon-access

# Check memory limits
kubectl describe pod <pod-name> -n 254carbon-access

# Restart service if needed
kubectl rollout restart deployment/<service-name> -n 254carbon-access
```

#### 2. High CPU Usage
```bash
# Check CPU usage
kubectl top pods -n 254carbon-access

# Check CPU limits
kubectl describe pod <pod-name> -n 254carbon-access

# Scale up service
kubectl scale deployment/<service-name> --replicas=5 -n 254carbon-access
```

#### 3. Network Connectivity Issues
```bash
# Check service endpoints
kubectl get endpoints -n 254carbon-access

# Check network policies
kubectl get networkpolicies -n 254carbon-access

# Test connectivity
kubectl exec -it <pod-name> -n 254carbon-access -- curl -f http://<service-name>-service:8000/health
```

#### 4. Storage Issues
```bash
# Check persistent volumes
kubectl get pv

# Check persistent volume claims
kubectl get pvc -n 254carbon-access

# Check storage usage
kubectl exec -it <pod-name> -n 254carbon-access -- df -h
```

### Log Analysis

#### 1. Service Logs
```bash
# Get recent logs
kubectl logs --tail=100 <pod-name> -n 254carbon-access

# Follow logs
kubectl logs -f <pod-name> -n 254carbon-access

# Get logs from previous container
kubectl logs --previous <pod-name> -n 254carbon-access
```

#### 2. Log Filtering
```bash
# Filter by error level
kubectl logs <pod-name> -n 254carbon-access | grep -i error

# Filter by time range
kubectl logs <pod-name> -n 254carbon-access --since=1h

# Filter by specific text
kubectl logs <pod-name> -n 254carbon-access | grep "specific_text"
```

## Maintenance Procedures

### Regular Maintenance Tasks

#### 1. Daily Tasks
- [ ] Check service health
- [ ] Review alert notifications
- [ ] Monitor resource usage
- [ ] Check backup status

#### 2. Weekly Tasks
- [ ] Review performance metrics
- [ ] Check security updates
- [ ] Verify backup integrity
- [ ] Update documentation

#### 3. Monthly Tasks
- [ ] Security audit
- [ ] Performance optimization
- [ ] Capacity planning
- [ ] Disaster recovery testing

<a name="gateway-cache-warm"></a>
### Cache Warm & Served Replay

#### 1. Trigger Cache Warm After Deploy or Flush
```bash
cd access
./scripts/warm_served_cache.py \
  --tenant tenant-1 \
  --user oncall-cache-warm \
  --redis-url $ACCESS_REDIS_URL \
  --projection-url $ACCESS_PROJECTION_SERVICE_URL
```
- Use `--dry-run` to inspect the warm plan without writing to Redis.
- Override the query ranking for experiments with `--hot-queries-file /tmp/hot_queries.json`.

#### 2. Verify Warm Completion
- Check CLI summary output for `errors: []` and warmed counts > 0.
- Grafana Dashboard: **Gateway Served Cache** (`gateway_served_cache.json`) panels should show:
  - `gateway_served_cache_warm_total` increasing with `result="hit"`.
  - `gateway_served_projection_age_seconds` p95 below 60 s for latest prices and 10 min for curves.
- Prometheus query to spot failures:
  ```
  increase(gateway_served_cache_warm_total{result="error"}[5m])
  ```

#### 3. Historical Replay / Backfill
Wenn projections are stale for a tenant:
```bash
../data-processing/scripts/backfill_window.py \
  --from 2025-09-01 \
  --to 2025-09-07 \
  --tenant tenant-1
```
- Wait for backfill jobs to complete (monitor Kafka topic lag).
- Re-run the cache warm script for the affected tenant to refresh Redis entries.

#### 4. Update Hot Query Rankings (Optional)
```bash
cp access/service_gateway/app/caching/data/hot_served_queries.json /tmp/hot_queries.json
# edit weights / add instruments as required
./scripts/warm_served_cache.py --tenant tenant-1 --hot-queries-file /tmp/hot_queries.json --dry-run
```
- Submit changes to the canonical JSON file via PR once validated.

### Backup Procedures

#### 1. Database Backup
```bash
# Create database backup
kubectl exec -it deployment/postgres-deployment -n 254carbon-access -- pg_dump -U access access > backup-$(date +%Y%m%d-%H%M%S).sql

# Verify backup
ls -la backup-*.sql

# Upload to backup storage
aws s3 cp backup-$(date +%Y%m%d-%H%M%S).sql s3://254carbon-backups/database/
```

#### 2. Configuration Backup
```bash
# Backup Kubernetes manifests
kubectl get all -n 254carbon-access -o yaml > k8s-backup-$(date +%Y%m%d-%H%M%S).yaml

# Backup ConfigMaps
kubectl get configmaps -n 254carbon-access -o yaml > configmaps-backup-$(date +%Y%m%d-%H%M%S).yaml

# Backup Secrets
kubectl get secrets -n 254carbon-access -o yaml > secrets-backup-$(date +%Y%m%d-%H%M%S).yaml
```

### Update Procedures

#### 1. Security Updates
```bash
# Check for security updates
kubectl get pods -n 254carbon-access -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.containers[*].image}{"\n"}{end}'

# Update base images
kubectl set image deployment/<service-name> <service-name>=ghcr.io/254carbon/access-layer-<service-name>:v1.0.2 -n 254carbon-access

# Monitor update
kubectl rollout status deployment/<service-name> -n 254carbon-access
```

#### 2. Dependency Updates
```bash
# Update Python dependencies
kubectl exec -it deployment/<service-name> -n 254carbon-access -- pip list --outdated

# Update system packages
kubectl exec -it deployment/<service-name> -n 254carbon-access -- apt update && apt upgrade -y
```

## Security Procedures

### JWT Rotation

Use this procedure to rotate JWT signing keys and JWKS for the access layer.

1. Update identity provider keys
   - Rotate the Keycloak client secret or update the JWKS key set as required.
   - Confirm JWKS publishes the new key: `curl -s $ACCESS_JWKS_URL | jq '.'`.

2. Update Kubernetes secrets
```bash
kubectl create secret generic access-secrets-rotated \
  --from-literal=ACCESS_JWKS_URL="$ACCESS_JWKS_URL" \
  --from-literal=ACCESS_JWT_SECRET_KEY="<optional-fallback-secret>" \
  -n 254carbon-access --dry-run=client -o yaml | kubectl apply -f -
```

3. Restart edge services to pick up new keys
```bash
kubectl rollout restart deployment/auth -n 254carbon-access
kubectl rollout restart deployment/gateway -n 254carbon-access
kubectl rollout restart deployment/streaming -n 254carbon-access
```

4. Verify
```bash
# Validate JWKS fetch succeeded (look for refresh logs)
kubectl logs deploy/auth -n 254carbon-access | tail -n 200 | grep -i jwks

# Exercise a signed token against the gateway
curl -s -H "Authorization: Bearer <new-token>" http://<gateway>/health | jq '.'
```

### Security Incident Response

#### 1. Initial Assessment
- [ ] Identify affected services
- [ ] Assess impact scope
- [ ] Notify security team
- [ ] Document incident details

#### 2. Containment Actions
```bash
# Isolate affected pods
kubectl delete pod <affected-pod-name> -n 254carbon-access

# Update network policies
kubectl apply -f k8s/emergency-network-policy.yaml -n 254carbon-access

# Rotate secrets
kubectl create secret generic access-secrets-new --from-literal=ACCESS_JWT_SECRET_KEY=<new-key> -n 254carbon-access
```

#### 3. Recovery Actions
```bash
# Deploy clean version
kubectl apply -f k8s/clean-deployment.yaml -n 254carbon-access

# Verify security
kubectl exec -it <pod-name> -n 254carbon-access -- security-scan

# Update monitoring
kubectl apply -f k8s/security-monitoring.yaml -n 254carbon-access
```

### Access Control

#### 1. Service Account Management
```bash
# Check service accounts
kubectl get serviceaccounts -n 254carbon-access

# Check RBAC permissions
kubectl get rolebindings -n 254carbon-access

# Check cluster role bindings
kubectl get clusterrolebindings | grep 254carbon-access
```

#### 2. Secret Management
```bash
# List secrets
kubectl get secrets -n 254carbon-access

# Check secret contents
kubectl get secret access-secrets -n 254carbon-access -o yaml

# Rotate secrets
kubectl create secret generic access-secrets-rotated --from-literal=ACCESS_JWT_SECRET_KEY=<new-key> -n 254carbon-access
```

### Compliance Procedures

#### 1. Audit Logging
```bash
# Check audit logs
kubectl get events -n 254carbon-access --sort-by='.lastTimestamp'

# Check service logs
kubectl logs -f deployment/<service-name> -n 254carbon-access

# Check access logs
kubectl exec -it deployment/<service-name> -n 254carbon-access -- cat /var/log/access.log
```

#### 2. Compliance Checks
```bash
# Run security scan
kubectl exec -it deployment/<service-name> -n 254carbon-access -- security-scan

# Check compliance status
kubectl exec -it deployment/<service-name> -n 254carbon-access -- compliance-check

# Generate compliance report
kubectl exec -it deployment/<service-name> -n 254carbon-access -- compliance-report > compliance-report-$(date +%Y%m%d).txt
```

## Contact Information

### Emergency Contacts
- **On-Call Engineer**: @oncall
- **Team Lead**: @team-lead
- **Security Team**: @security
- **DevOps Team**: @devops

### Escalation Procedures
1. **Level 1**: On-call engineer (0-15 minutes)
2. **Level 2**: Team lead (15-30 minutes)
3. **Level 3**: Engineering manager (30-60 minutes)
4. **Level 4**: CTO (60+ minutes)

### Communication Channels
- **Incidents**: #incidents
- **Alerts**: #alerts-critical, #alerts-warning
- **Team**: #devops-team
- **Security**: #security-team

---

**Last Updated**: 2024-01-01  
**Version**: 1.0.0  
**Maintainer**: 254Carbon DevOps Team
