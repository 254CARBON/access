# Production Deployment Guide

This document provides comprehensive instructions for deploying the 254Carbon Access Layer to production environments.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Environment Setup](#environment-setup)
- [Infrastructure Provisioning](#infrastructure-provisioning)
- [Application Deployment](#application-deployment)
- [Configuration Management](#configuration-management)
- [Security Configuration](#security-configuration)
- [Monitoring Setup](#monitoring-setup)
- [Backup and Recovery](#backup-and-recovery)
- [Disaster Recovery](#disaster-recovery)
- [Maintenance Procedures](#maintenance-procedures)

## Prerequisites

### Infrastructure Requirements

#### 1. Kubernetes Cluster
- **Version**: 1.28+
- **Nodes**: Minimum 3 worker nodes
- **CPU**: 8+ cores per node
- **Memory**: 32+ GB per node
- **Storage**: 100+ GB SSD per node
- **Network**: 10+ Gbps bandwidth

#### 2. External Dependencies
- **PostgreSQL**: 15+ (managed service recommended)
- **Redis**: 7+ (managed service recommended)
- **Kafka**: 3.5+ (managed service recommended)
- **Keycloak**: 22+ (managed service recommended)

#### 3. Tools and CLI
- **kubectl**: 1.28+
- **helm**: 3.12+
- **docker**: 20.10+
- **git**: 2.40+

### Security Requirements

#### 1. Network Security
- VPC with private subnets
- Security groups/firewall rules
- Network ACLs
- VPN or bastion host access

#### 2. Access Control
- RBAC configuration
- Service accounts
- Secret management
- Certificate management

#### 3. Compliance
- SOC 2 Type II
- ISO 27001
- GDPR compliance
- Data encryption at rest and in transit

## Environment Setup

### 1. Cluster Configuration

#### Create Namespace
```bash
# Create production namespace
kubectl create namespace 254carbon-access

# Label namespace
kubectl label namespace 254carbon-access environment=production
kubectl label namespace 254carbon-access tier=application
```

#### Configure Resource Quotas
```yaml
# resource-quotas.yaml
apiVersion: v1
kind: ResourceQuota
metadata:
  name: access-layer-quota
  namespace: 254carbon-access
spec:
  hard:
    requests.cpu: "20"
    requests.memory: "40Gi"
    limits.cpu: "40"
    limits.memory: "80Gi"
    persistentvolumeclaims: "10"
    services: "20"
    secrets: "20"
    configmaps: "20"
```

#### Apply Resource Quotas
```bash
kubectl apply -f resource-quotas.yaml
```

### 2. Storage Configuration

#### Create Storage Classes
```yaml
# storage-classes.yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: fast-ssd
provisioner: kubernetes.io/aws-ebs
parameters:
  type: gp3
  iops: "3000"
  throughput: "125"
  encrypted: "true"
volumeBindingMode: WaitForFirstConsumer
allowVolumeExpansion: true
---
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: standard-ssd
provisioner: kubernetes.io/aws-ebs
parameters:
  type: gp3
  iops: "1000"
  throughput: "125"
  encrypted: "true"
volumeBindingMode: WaitForFirstConsumer
allowVolumeExpansion: true
```

#### Apply Storage Classes
```bash
kubectl apply -f storage-classes.yaml
```

### 3. Network Configuration

#### Create Network Policies
```yaml
# network-policies.yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: access-layer-network-policy
  namespace: 254carbon-access
spec:
  podSelector: {}
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          name: ingress-nginx
    - podSelector:
        matchLabels:
          app: gateway
    ports:
    - protocol: TCP
      port: 8000
    - protocol: TCP
      port: 8001
    - protocol: TCP
      port: 8010
    - protocol: TCP
      port: 8011
    - protocol: TCP
      port: 8012
  egress:
  - to:
    - podSelector:
        matchLabels:
          app: postgres
    ports:
    - protocol: TCP
      port: 5432
  - to:
    - podSelector:
        matchLabels:
          app: redis
    ports:
    - protocol: TCP
      port: 6379
  - to:
    - podSelector:
        matchLabels:
          app: kafka
    ports:
    - protocol: TCP
      port: 9092
  - to:
    - podSelector:
        matchLabels:
          app: keycloak
    ports:
    - protocol: TCP
      port: 8080
  - to: []
    ports:
    - protocol: UDP
      port: 53
    - protocol: TCP
      port: 53
```

#### Apply Network Policies
```bash
kubectl apply -f network-policies.yaml
```

## Infrastructure Provisioning

### 1. Database Setup

#### PostgreSQL Configuration
```yaml
# postgres-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: postgres-deployment
  namespace: 254carbon-access
  labels:
    app: postgres
    component: database
spec:
  replicas: 1
  selector:
    matchLabels:
      app: postgres
  template:
    metadata:
      labels:
        app: postgres
    spec:
      containers:
      - name: postgres
        image: postgres:15-alpine
        ports:
        - containerPort: 5432
        env:
        - name: POSTGRES_DB
          value: "access"
        - name: POSTGRES_USER
          value: "access"
        - name: POSTGRES_PASSWORD
          valueFrom:
            secretKeyRef:
              name: postgres-secret
              key: password
        - name: POSTGRES_INITDB_ARGS
          value: "--auth-host=scram-sha-256"
        resources:
          requests:
            memory: "2Gi"
            cpu: "1000m"
          limits:
            memory: "4Gi"
            cpu: "2000m"
        volumeMounts:
        - name: postgres-storage
          mountPath: /var/lib/postgresql/data
        - name: postgres-config
          mountPath: /etc/postgresql/postgresql.conf
          subPath: postgresql.conf
        livenessProbe:
          exec:
            command:
            - pg_isready
            - -U
            - access
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          exec:
            command:
            - pg_isready
            - -U
            - access
          initialDelaySeconds: 5
          periodSeconds: 5
      volumes:
      - name: postgres-storage
        persistentVolumeClaim:
          claimName: postgres-storage
      - name: postgres-config
        configMap:
          name: postgres-config
---
apiVersion: v1
kind: Service
metadata:
  name: postgres-service
  namespace: 254carbon-access
  labels:
    app: postgres
spec:
  selector:
    app: postgres
  ports:
  - port: 5432
    targetPort: 5432
  type: ClusterIP
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: postgres-storage
  namespace: 254carbon-access
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 100Gi
  storageClassName: fast-ssd
```

#### PostgreSQL Configuration
```yaml
# postgres-config.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: postgres-config
  namespace: 254carbon-access
data:
  postgresql.conf: |
    # Connection Settings
    listen_addresses = '*'
    port = 5432
    max_connections = 200
    
    # Memory Settings
    shared_buffers = 256MB
    effective_cache_size = 1GB
    work_mem = 4MB
    maintenance_work_mem = 64MB
    
    # Checkpoint Settings
    checkpoint_completion_target = 0.9
    wal_buffers = 16MB
    
    # Query Planner
    default_statistics_target = 100
    random_page_cost = 1.1
    effective_io_concurrency = 200
    
    # Parallel Processing
    max_worker_processes = 8
    max_parallel_workers_per_gather = 4
    max_parallel_workers = 8
    max_parallel_maintenance_workers = 4
    
    # Logging
    log_destination = 'stderr'
    logging_collector = on
    log_directory = 'pg_log'
    log_filename = 'postgresql-%Y-%m-%d_%H%M%S.log'
    log_rotation_age = 1d
    log_rotation_size = 100MB
    log_min_duration_statement = 1000
    log_line_prefix = '%t [%p]: [%l-1] user=%u,db=%d,app=%a,client=%h '
    log_checkpoints = on
    log_connections = on
    log_disconnections = on
    log_lock_waits = on
    log_temp_files = 0
    
    # Security
    ssl = on
    ssl_cert_file = '/etc/ssl/certs/server.crt'
    ssl_key_file = '/etc/ssl/private/server.key'
    
    # Performance
    shared_preload_libraries = 'pg_stat_statements'
    track_activity_query_size = 2048
    pg_stat_statements.track = all
```

### 2. Redis Setup

#### Redis Configuration
```yaml
# redis-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: redis-deployment
  namespace: 254carbon-access
  labels:
    app: redis
    component: cache
spec:
  replicas: 1
  selector:
    matchLabels:
      app: redis
  template:
    metadata:
      labels:
        app: redis
    spec:
      containers:
      - name: redis
        image: redis:7-alpine
        ports:
        - containerPort: 6379
        command:
        - redis-server
        - /etc/redis/redis.conf
        resources:
          requests:
            memory: "1Gi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "1000m"
        volumeMounts:
        - name: redis-storage
          mountPath: /data
        - name: redis-config
          mountPath: /etc/redis/redis.conf
          subPath: redis.conf
        livenessProbe:
          exec:
            command:
            - redis-cli
            - ping
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          exec:
            command:
            - redis-cli
            - ping
          initialDelaySeconds: 5
          periodSeconds: 5
      volumes:
      - name: redis-storage
        persistentVolumeClaim:
          claimName: redis-storage
      - name: redis-config
        configMap:
          name: redis-config
---
apiVersion: v1
kind: Service
metadata:
  name: redis-service
  namespace: 254carbon-access
  labels:
    app: redis
spec:
  selector:
    app: redis
  ports:
  - port: 6379
    targetPort: 6379
  type: ClusterIP
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: redis-storage
  namespace: 254carbon-access
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 50Gi
  storageClassName: fast-ssd
```

#### Redis Configuration
```yaml
# redis-config.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: redis-config
  namespace: 254carbon-access
data:
  redis.conf: |
    # Network
    bind 0.0.0.0
    port 6379
    tcp-keepalive 300
    timeout 0
    tcp-backlog 511
    
    # General
    daemonize no
    supervised no
    pidfile /var/run/redis_6379.pid
    loglevel notice
    logfile ""
    databases 16
    
    # Snapshotting
    save 900 1
    save 300 10
    save 60 10000
    stop-writes-on-bgsave-error yes
    rdbcompression yes
    rdbchecksum yes
    dbfilename dump.rdb
    dir /data
    
    # Replication
    replica-serve-stale-data yes
    replica-read-only yes
    repl-diskless-sync no
    repl-diskless-sync-delay 5
    repl-ping-replica-period 10
    repl-timeout 60
    repl-disable-tcp-nodelay no
    repl-backlog-size 1mb
    repl-backlog-ttl 3600
    
    # Security
    requirepass redis_password
    
    # Memory Management
    maxmemory 2gb
    maxmemory-policy allkeys-lru
    maxmemory-samples 5
    
    # Lazy Freeing
    lazyfree-lazy-eviction no
    lazyfree-lazy-expire no
    lazyfree-lazy-server-del no
    replica-lazy-flush no
    
    # Append Only File
    appendonly yes
    appendfilename "appendonly.aof"
    appendfsync everysec
    no-appendfsync-on-rewrite no
    auto-aof-rewrite-percentage 100
    auto-aof-rewrite-min-size 64mb
    aof-load-truncated yes
    aof-use-rdb-preamble yes
    
    # Lua Scripting
    lua-time-limit 5000
    
    # Slow Log
    slowlog-log-slower-than 10000
    slowlog-max-len 128
    
    # Latency Monitor
    latency-monitor-threshold 100
    
    # Event Notification
    notify-keyspace-events ""
    
    # Hash Configuration
    hash-max-ziplist-entries 512
    hash-max-ziplist-value 64
    
    # List Configuration
    list-max-ziplist-size -2
    list-compress-depth 0
    
    # Set Configuration
    set-max-intset-entries 512
    
    # Sorted Set Configuration
    zset-max-ziplist-entries 128
    zset-max-ziplist-value 64
    
    # HyperLogLog Configuration
    hll-sparse-max-bytes 3000
    
    # Streams Configuration
    stream-node-max-bytes 4096
    stream-node-max-entries 100
    
    # Active Rehashing
    activerehashing yes
    
    # Client Output Buffer Limits
    client-output-buffer-limit normal 0 0 0
    client-output-buffer-limit replica 256mb 64mb 60
    client-output-buffer-limit pubsub 32mb 8mb 60
    
    # Client Query Buffer Limit
    client-query-buffer-limit 1gb
    
    # Protocol Buffer Limit
    proto-max-bulk-len 512mb
    
    # Frequency
    hz 10
    
    # Dynamic HZ
    dynamic-hz yes
    
    # AOF Rewrite Incremental Fsync
    aof-rewrite-incremental-fsync yes
    
    # RDB Save Incremental Fsync
    rdb-save-incremental-fsync yes
    
    # Jemalloc Background Thread
    jemalloc-bg-thread yes
```

### 3. Kafka Setup

#### Kafka Configuration
```yaml
# kafka-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: kafka-deployment
  namespace: 254carbon-access
  labels:
    app: kafka
    component: messaging
spec:
  replicas: 3
  selector:
    matchLabels:
      app: kafka
  template:
    metadata:
      labels:
        app: kafka
    spec:
      containers:
      - name: kafka
        image: confluentinc/cp-kafka:latest
        ports:
        - containerPort: 9092
        env:
        - name: KAFKA_BROKER_ID
          valueFrom:
            fieldRef:
              fieldPath: metadata.uid
        - name: KAFKA_ZOOKEEPER_CONNECT
          value: "zookeeper-service:2181"
        - name: KAFKA_ADVERTISED_LISTENERS
          value: "PLAINTEXT://kafka-service:9092"
        - name: KAFKA_LISTENER_SECURITY_PROTOCOL_MAP
          value: "PLAINTEXT:PLAINTEXT"
        - name: KAFKA_INTER_BROKER_LISTENER_NAME
          value: "PLAINTEXT"
        - name: KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR
          value: "3"
        - name: KAFKA_TRANSACTION_STATE_LOG_REPLICATION_FACTOR
          value: "3"
        - name: KAFKA_TRANSACTION_STATE_LOG_MIN_ISR
          value: "2"
        - name: KAFKA_AUTO_CREATE_TOPICS_ENABLE
          value: "false"
        - name: KAFKA_NUM_PARTITIONS
          value: "3"
        - name: KAFKA_DEFAULT_REPLICATION_FACTOR
          value: "3"
        - name: KAFKA_MIN_INSYNC_REPLICAS
          value: "2"
        - name: KAFKA_LOG_RETENTION_HOURS
          value: "168"
        - name: KAFKA_LOG_SEGMENT_BYTES
          value: "1073741824"
        - name: KAFKA_LOG_RETENTION_CHECK_INTERVAL_MS
          value: "300000"
        resources:
          requests:
            memory: "2Gi"
            cpu: "1000m"
          limits:
            memory: "4Gi"
            cpu: "2000m"
        volumeMounts:
        - name: kafka-storage
          mountPath: /var/lib/kafka/data
        livenessProbe:
          exec:
            command:
            - kafka-topics
            - --bootstrap-server
            - localhost:9092
            - --list
          initialDelaySeconds: 60
          periodSeconds: 30
        readinessProbe:
          exec:
            command:
            - kafka-topics
            - --bootstrap-server
            - localhost:9092
            - --list
          initialDelaySeconds: 30
          periodSeconds: 10
      volumes:
      - name: kafka-storage
        persistentVolumeClaim:
          claimName: kafka-storage
---
apiVersion: v1
kind: Service
metadata:
  name: kafka-service
  namespace: 254carbon-access
  labels:
    app: kafka
spec:
  selector:
    app: kafka
  ports:
  - port: 9092
    targetPort: 9092
  type: ClusterIP
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: kafka-storage
  namespace: 254carbon-access
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 100Gi
  storageClassName: fast-ssd
```

## Application Deployment

### 1. Deploy Infrastructure Services

#### Deploy Database
```bash
# Deploy PostgreSQL
kubectl apply -f k8s/postgres-deployment.yaml
kubectl apply -f k8s/postgres-config.yaml

# Wait for PostgreSQL to be ready
kubectl wait --for=condition=ready pod -l app=postgres -n 254carbon-access --timeout=300s
```

#### Deploy Redis
```bash
# Deploy Redis
kubectl apply -f k8s/redis-deployment.yaml
kubectl apply -f k8s/redis-config.yaml

# Wait for Redis to be ready
kubectl wait --for=condition=ready pod -l app=redis -n 254carbon-access --timeout=300s
```

#### Deploy Kafka
```bash
# Deploy Zookeeper first
kubectl apply -f k8s/zookeeper-deployment.yaml

# Wait for Zookeeper
kubectl wait --for=condition=ready pod -l app=zookeeper -n 254carbon-access --timeout=300s

# Deploy Kafka
kubectl apply -f k8s/kafka-deployment.yaml

# Wait for Kafka to be ready
kubectl wait --for=condition=ready pod -l app=kafka -n 254carbon-access --timeout=300s
```

### 2. Deploy Application Services

#### Deploy Configuration
```bash
# Deploy ConfigMap
kubectl apply -f k8s/configmap.yaml

# Deploy Secrets
kubectl apply -f k8s/secrets.yaml
```

#### Deploy Services
```bash
# Deploy Gateway Service
kubectl apply -f k8s/gateway-deployment.yaml

# Deploy Streaming Service
kubectl apply -f k8s/streaming-deployment.yaml

# Deploy Auth Service
kubectl apply -f k8s/auth-deployment.yaml

# Deploy Entitlements Service
kubectl apply -f k8s/entitlements-deployment.yaml

# Deploy Metrics Service
kubectl apply -f k8s/metrics-deployment.yaml
```

#### Wait for Services
```bash
# Wait for all services to be ready
kubectl wait --for=condition=ready pod -l app=gateway -n 254carbon-access --timeout=300s
kubectl wait --for=condition=ready pod -l app=streaming -n 254carbon-access --timeout=300s
kubectl wait --for=condition=ready pod -l app=auth -n 254carbon-access --timeout=300s
kubectl wait --for=condition=ready pod -l app=entitlements -n 254carbon-access --timeout=300s
kubectl wait --for=condition=ready pod -l app=metrics -n 254carbon-access --timeout=300s
```

### 3. Deploy Monitoring

#### Deploy Monitoring Stack
```bash
# Deploy Prometheus
kubectl apply -f k8s/monitoring.yaml

# Wait for monitoring to be ready
kubectl wait --for=condition=ready pod -l app=prometheus -n 254carbon-access --timeout=300s
kubectl wait --for=condition=ready pod -l app=alertmanager -n 254carbon-access --timeout=300s
kubectl wait --for=condition=ready pod -l app=grafana -n 254carbon-access --timeout=300s
```

## Configuration Management

### 1. Environment Variables

#### Production Environment Variables
```bash
# Set production environment variables
export ACCESS_ENV=production
export ACCESS_LOG_LEVEL=info
export ACCESS_LOG_FORMAT=json
export ACCESS_ENABLE_TRACING=true
export ACCESS_ENABLE_METRICS=true

# Database configuration
export ACCESS_POSTGRES_HOST=postgres-service
export ACCESS_POSTGRES_PORT=5432
export ACCESS_POSTGRES_DB=access
export ACCESS_POSTGRES_SSLMODE=require

# Redis configuration
export ACCESS_REDIS_HOST=redis-service
export ACCESS_REDIS_PORT=6379
export ACCESS_REDIS_DB=0

# Kafka configuration
export ACCESS_KAFKA_BOOTSTRAP=kafka-service:9092
export ACCESS_KAFKA_SECURITY_PROTOCOL=PLAINTEXT

# Keycloak configuration
export ACCESS_KEYCLOAK_BASE_URL=http://keycloak-service:8080
export ACCESS_KEYCLOAK_REALM=254carbon
export ACCESS_KEYCLOAK_CLIENT_ID=access-layer
```

### 2. Secret Management

#### Create Secrets
```bash
# Create database secret
kubectl create secret generic postgres-secret \
  --from-literal=password=secure_postgres_password \
  -n 254carbon-access

# Create Redis secret
kubectl create secret generic redis-secret \
  --from-literal=password=secure_redis_password \
  -n 254carbon-access

# Create JWT secret
kubectl create secret generic jwt-secret \
  --from-literal=secret-key=secure_jwt_secret_key \
  -n 254carbon-access

# Create API keys
kubectl create secret generic api-keys \
  --from-literal=admin-key=secure_admin_api_key \
  --from-literal=service-key=secure_service_api_key \
  --from-literal=readonly-key=secure_readonly_api_key \
  -n 254carbon-access
```

### 3. Configuration Updates

#### Update Configuration
```bash
# Update ConfigMap
kubectl apply -f k8s/configmap.yaml

# Restart services to pick up new configuration
kubectl rollout restart deployment/gateway-deployment -n 254carbon-access
kubectl rollout restart deployment/streaming-deployment -n 254carbon-access
kubectl rollout restart deployment/auth-deployment -n 254carbon-access
kubectl rollout restart deployment/entitlements-deployment -n 254carbon-access
kubectl rollout restart deployment/metrics-deployment -n 254carbon-access
```

## Security Configuration

### 1. Network Security

#### Configure Ingress
```yaml
# ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: access-layer-ingress
  namespace: 254carbon-access
  annotations:
    kubernetes.io/ingress.class: "nginx"
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    nginx.ingress.kubernetes.io/force-ssl-redirect: "true"
    nginx.ingress.kubernetes.io/ssl-protocols: "TLSv1.2 TLSv1.3"
    nginx.ingress.kubernetes.io/ssl-ciphers: "ECDHE-RSA-AES128-GCM-SHA256,ECDHE-RSA-AES256-GCM-SHA384"
    nginx.ingress.kubernetes.io/rate-limit: "1000"
    nginx.ingress.kubernetes.io/rate-limit-window: "1m"
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
spec:
  tls:
  - hosts:
    - api.254carbon.com
    - ws.254carbon.com
    secretName: access-layer-tls
  rules:
  - host: api.254carbon.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: gateway-service
            port:
              number: 8000
  - host: ws.254carbon.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: streaming-service
            port:
              number: 8001
```

#### Apply Ingress
```bash
kubectl apply -f k8s/ingress.yaml
```

### 2. Certificate Management

#### Create Certificate Issuer
```yaml
# certificate-issuer.yaml
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: admin@254carbon.com
    privateKeySecretRef:
      name: letsencrypt-prod
    solvers:
    - http01:
        ingress:
          class: nginx
```

#### Apply Certificate Issuer
```bash
kubectl apply -f k8s/certificate-issuer.yaml
```

### 3. Security Policies

#### Pod Security Policy
```yaml
# pod-security-policy.yaml
apiVersion: policy/v1beta1
kind: PodSecurityPolicy
metadata:
  name: access-layer-psp
  namespace: 254carbon-access
spec:
  privileged: false
  allowPrivilegeEscalation: false
  requiredDropCapabilities:
    - ALL
  volumes:
    - 'configMap'
    - 'emptyDir'
    - 'projected'
    - 'secret'
    - 'downwardAPI'
    - 'persistentVolumeClaim'
  runAsUser:
    rule: 'MustRunAsNonRoot'
  seLinux:
    rule: 'RunAsAny'
  fsGroup:
    rule: 'RunAsAny'
```

#### Apply Security Policy
```bash
kubectl apply -f k8s/pod-security-policy.yaml
```

## Monitoring Setup

### 1. Deploy Monitoring Stack

#### Deploy Prometheus
```bash
# Deploy Prometheus
kubectl apply -f k8s/monitoring.yaml

# Wait for Prometheus to be ready
kubectl wait --for=condition=ready pod -l app=prometheus -n 254carbon-access --timeout=300s
```

#### Deploy Grafana
```bash
# Deploy Grafana
kubectl apply -f k8s/grafana-deployment.yaml

# Wait for Grafana to be ready
kubectl wait --for=condition=ready pod -l app=grafana -n 254carbon-access --timeout=300s
```

### 2. Configure Alerting

#### Alertmanager Configuration
```yaml
# alertmanager-config.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: alertmanager-config
  namespace: 254carbon-access
data:
  alertmanager.yml: |
    global:
      smtp_smarthost: 'smtp.company.com:587'
      smtp_from: 'alerts@254carbon.com'
      smtp_auth_username: 'alerts@254carbon.com'
      smtp_auth_password: 'alert_password'
    
    route:
      group_by: ['alertname', 'service']
      group_wait: 10s
      group_interval: 10s
      repeat_interval: 1h
      receiver: 'default'
      routes:
      - match:
          severity: critical
        receiver: 'critical-alerts'
        group_wait: 5s
        repeat_interval: 30m
      - match:
          severity: warning
        receiver: 'warning-alerts'
        group_wait: 10s
        repeat_interval: 1h
    
    receivers:
    - name: 'default'
      email_configs:
      - to: 'devops@254carbon.com'
        subject: '[254Carbon] Alert: {{ .GroupLabels.alertname }}'
        body: |
          {{ range .Alerts }}
          Alert: {{ .Annotations.summary }}
          Description: {{ .Annotations.description }}
          Labels: {{ range .Labels.SortedPairs }}{{ .Name }}={{ .Value }} {{ end }}
          {{ end }}
    
    - name: 'critical-alerts'
      email_configs:
      - to: 'oncall@254carbon.com'
        subject: '[CRITICAL] 254Carbon Alert: {{ .GroupLabels.alertname }}'
        body: |
          CRITICAL ALERT: {{ .GroupLabels.alertname }}
          {{ range .Alerts }}
          Description: {{ .Annotations.description }}
          Labels: {{ range .Labels.SortedPairs }}{{ .Name }}={{ .Value }} {{ end }}
          {{ end }}
      slack_configs:
      - api_url: 'https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK'
        channel: '#alerts-critical'
        title: 'Critical Alert: {{ .GroupLabels.alertname }}'
        text: |
          {{ range .Alerts }}
          {{ .Annotations.description }}
          {{ end }}
```

#### Apply Alertmanager Configuration
```bash
kubectl apply -f k8s/alertmanager-config.yaml
```

### 3. Configure Dashboards

#### Grafana Dashboards
```bash
# Import dashboards
kubectl apply -f k8s/grafana-dashboards.yaml

# Check dashboard status
kubectl get configmap grafana-dashboards -n 254carbon-access
```

## Backup and Recovery

### 1. Database Backup

#### Automated Backup
```yaml
# database-backup.yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: database-backup
  namespace: 254carbon-access
spec:
  schedule: "0 2 * * *"  # Daily at 2 AM
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: backup
            image: postgres:15-alpine
            command:
            - /bin/bash
            - -c
            - |
              pg_dump -h postgres-service -U access -d access > /backup/backup-$(date +%Y%m%d-%H%M%S).sql
              aws s3 cp /backup/backup-$(date +%Y%m%d-%H%M%S).sql s3://254carbon-backups/database/
            env:
            - name: PGPASSWORD
              valueFrom:
                secretKeyRef:
                  name: postgres-secret
                  key: password
            volumeMounts:
            - name: backup-storage
              mountPath: /backup
          volumes:
          - name: backup-storage
            persistentVolumeClaim:
              claimName: backup-storage
          restartPolicy: OnFailure
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: backup-storage
  namespace: 254carbon-access
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 50Gi
  storageClassName: standard-ssd
```

#### Apply Backup Configuration
```bash
kubectl apply -f k8s/database-backup.yaml
```

### 2. Configuration Backup

#### Backup Script
```bash
#!/bin/bash
# backup-config.sh

# Backup Kubernetes manifests
kubectl get all -n 254carbon-access -o yaml > backup/k8s-backup-$(date +%Y%m%d-%H%M%S).yaml

# Backup ConfigMaps
kubectl get configmaps -n 254carbon-access -o yaml > backup/configmaps-backup-$(date +%Y%m%d-%H%M%S).yaml

# Backup Secrets (without sensitive data)
kubectl get secrets -n 254carbon-access -o yaml > backup/secrets-backup-$(date +%Y%m%d-%H%M%S).yaml

# Upload to backup storage
aws s3 cp backup/ s3://254carbon-backups/config/ --recursive
```

#### Schedule Backup
```bash
# Add to crontab
echo "0 3 * * * /path/to/backup-config.sh" | crontab -
```

## Disaster Recovery

### 1. Recovery Procedures

#### Database Recovery
```bash
# Restore from backup
kubectl exec -i deployment/postgres-deployment -n 254carbon-access -- psql -U access access < backup-20240101-120000.sql

# Verify restoration
kubectl exec -it deployment/postgres-deployment -n 254carbon-access -- psql -U access -d access -c "SELECT COUNT(*) FROM entitlements;"
```

#### Service Recovery
```bash
# Restore services
kubectl apply -f backup/k8s-backup-20240101-120000.yaml

# Wait for services to be ready
kubectl wait --for=condition=ready pod -l app=gateway -n 254carbon-access --timeout=300s
kubectl wait --for=condition=ready pod -l app=streaming -n 254carbon-access --timeout=300s
kubectl wait --for=condition=ready pod -l app=auth -n 254carbon-access --timeout=300s
kubectl wait --for=condition=ready pod -l app=entitlements -n 254carbon-access --timeout=300s
kubectl wait --for=condition=ready pod -l app=metrics -n 254carbon-access --timeout=300s
```

### 2. Failover Procedures

#### Multi-Region Setup
```yaml
# multi-region-config.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: multi-region-config
  namespace: 254carbon-access
data:
  primary-region: "us-west-2"
  secondary-region: "us-east-1"
  failover-threshold: "5"
  health-check-interval: "30"
  failover-timeout: "300"
```

#### Failover Script
```bash
#!/bin/bash
# failover.sh

# Check primary region health
if ! kubectl get pods -n 254carbon-access --context=primary-region | grep -q "Running"; then
    echo "Primary region unhealthy, initiating failover..."
    
    # Update DNS to point to secondary region
    aws route53 change-resource-record-sets --hosted-zone-id Z123456789 --change-batch file://failover-dns.json
    
    # Scale up secondary region
    kubectl scale deployment gateway-deployment --replicas=5 --context=secondary-region
    kubectl scale deployment streaming-deployment --replicas=5 --context=secondary-region
    
    # Notify team
    curl -X POST -H 'Content-type: application/json' \
      --data '{"text":"Failover initiated to secondary region"}' \
      https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK
fi
```

## Maintenance Procedures

### 1. Regular Maintenance

#### Health Checks
```bash
#!/bin/bash
# health-check.sh

# Check service health
services=("gateway" "streaming" "auth" "entitlements" "metrics")

for service in "${services[@]}"; do
    if kubectl get pods -n 254carbon-access -l app=$service | grep -q "Running"; then
        echo "✅ $service is healthy"
    else
        echo "❌ $service is unhealthy"
        # Send alert
        curl -X POST -H 'Content-type: application/json' \
          --data "{\"text\":\"$service service is unhealthy\"}" \
          https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK
    fi
done
```

#### Performance Monitoring
```bash
#!/bin/bash
# performance-check.sh

# Check resource usage
kubectl top nodes
kubectl top pods -n 254carbon-access

# Check service metrics
curl -s http://gateway-service:8000/metrics | grep -E "(request_rate|error_rate|response_time)"

# Check database performance
kubectl exec -it deployment/postgres-deployment -n 254carbon-access -- psql -U access -d access -c "SELECT * FROM pg_stat_activity;"
```

### 2. Update Procedures

#### Rolling Updates
```bash
# Update service image
kubectl set image deployment/gateway-deployment gateway=ghcr.io/254carbon/access-layer-gateway:v1.0.1 -n 254carbon-access

# Monitor rollout
kubectl rollout status deployment/gateway-deployment -n 254carbon-access

# Verify update
kubectl get pods -n 254carbon-access -l app=gateway
```

#### Blue-Green Deployment
```bash
# Deploy green version
kubectl apply -f k8s/green-deployment.yaml

# Wait for green deployment
kubectl wait --for=condition=ready pod -l app=gateway,version=green -n 254carbon-access --timeout=300s

# Switch traffic
kubectl patch service gateway-service -n 254carbon-access -p '{"spec":{"selector":{"version":"green"}}}'

# Verify traffic switch
kubectl get pods -n 254carbon-access -l app=gateway

# Remove blue version
kubectl delete deployment gateway-blue -n 254carbon-access
```

## Troubleshooting

### 1. Common Issues

#### Service Not Starting
```bash
# Check pod status
kubectl get pods -n 254carbon-access

# Check pod logs
kubectl logs -f deployment/gateway-deployment -n 254carbon-access

# Check events
kubectl get events -n 254carbon-access --sort-by='.lastTimestamp'
```

#### Database Connection Issues
```bash
# Check database status
kubectl get pods -n 254carbon-access -l app=postgres

# Test database connection
kubectl exec -it deployment/postgres-deployment -n 254carbon-access -- psql -U access -d access -c "SELECT 1;"

# Check database logs
kubectl logs -f deployment/postgres-deployment -n 254carbon-access
```

#### Performance Issues
```bash
# Check resource usage
kubectl top pods -n 254carbon-access

# Check service metrics
curl -s http://gateway-service:8000/metrics | grep -E "(request_rate|error_rate|response_time)"

# Check database performance
kubectl exec -it deployment/postgres-deployment -n 254carbon-access -- psql -U access -d access -c "SELECT * FROM pg_stat_activity;"
```

### 2. Emergency Procedures

#### Service Restart
```bash
# Restart service
kubectl rollout restart deployment/gateway-deployment -n 254carbon-access

# Monitor restart
kubectl rollout status deployment/gateway-deployment -n 254carbon-access
```

#### Scale Up Services
```bash
# Scale up service
kubectl scale deployment/gateway-deployment --replicas=5 -n 254carbon-access

# Check scaling
kubectl get pods -n 254carbon-access -l app=gateway
```

#### Rollback Deployment
```bash
# Check deployment history
kubectl rollout history deployment/gateway-deployment -n 254carbon-access

# Rollback to previous version
kubectl rollout undo deployment/gateway-deployment -n 254carbon-access

# Monitor rollback
kubectl rollout status deployment/gateway-deployment -n 254carbon-access
```

## Contact Information

### Emergency Contacts
- **On-Call Engineer**: @oncall
- **Team Lead**: @team-lead
- **DevOps Team**: @devops
- **Security Team**: @security

### Escalation Procedures
1. **Level 1**: On-call engineer (0-15 minutes)
2. **Level 2**: Team lead (15-30 minutes)
3. **Level 3**: Engineering manager (30-60 minutes)
4. **Level 4**: CTO (60+ minutes)

### Communication Channels
- **Incidents**: #incidents
- **Deployments**: #deployments
- **Monitoring**: #monitoring
- **Security**: #security

---

**Last Updated**: 2024-01-01  
**Version**: 1.0.0  
**Maintainer**: 254Carbon DevOps Team
