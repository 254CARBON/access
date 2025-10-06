# Performance Tuning and Optimization Guide

This document provides comprehensive guidance for optimizing the performance of the 254Carbon Access Layer in production environments.

## Table of Contents

- [Performance Monitoring](#performance-monitoring)
- [Service-Level Optimization](#service-level-optimization)
- [Infrastructure Optimization](#infrastructure-optimization)
- [Database Optimization](#database-optimization)
- [Caching Optimization](#caching-optimization)
- [Network Optimization](#network-optimization)
- [Load Testing](#load-testing)
- [Performance Benchmarks](#performance-benchmarks)

## Performance Monitoring

### Key Performance Indicators (KPIs)

#### 1. Response Time Metrics
- **P50 (Median)**: Target < 100ms
- **P95 (95th percentile)**: Target < 500ms
- **P99 (99th percentile)**: Target < 1000ms
- **P99.9 (99.9th percentile)**: Target < 2000ms

#### 2. Throughput Metrics
- **Requests per second**: Target > 1000 RPS
- **Concurrent connections**: Target > 10,000
- **WebSocket connections**: Target > 5,000
- **Message throughput**: Target > 10,000 msg/sec

#### 3. Resource Utilization
- **CPU usage**: Target < 70%
- **Memory usage**: Target < 80%
- **Disk I/O**: Target < 80%
- **Network bandwidth**: Target < 80%

#### 4. Error Rates
- **4xx errors**: Target < 1%
- **5xx errors**: Target < 0.1%
- **Timeout errors**: Target < 0.01%

### Monitoring Queries

#### Prometheus Queries for Performance
```promql
# Response time percentiles
histogram_quantile(0.50, rate(gateway_request_duration_seconds_bucket[5m]))
histogram_quantile(0.95, rate(gateway_request_duration_seconds_bucket[5m]))
histogram_quantile(0.99, rate(gateway_request_duration_seconds_bucket[5m]))

# Request rate
rate(gateway_requests_total[5m])

# Error rate
rate(gateway_requests_total{status=~"5.."}[5m]) / rate(gateway_requests_total[5m])

# Resource utilization
100 - (avg by(instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)
(node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / node_memory_MemTotal_bytes * 100
```

## Service-Level Optimization

### Gateway Service Optimization

#### 1. Connection Pooling
```python
# Optimize HTTP client connections
import httpx

async def create_optimized_client():
    return httpx.AsyncClient(
        limits=httpx.Limits(
            max_keepalive_connections=100,
            max_connections=1000,
            keepalive_expiry=30.0
        ),
        timeout=httpx.Timeout(
            connect=5.0,
            read=30.0,
            write=30.0,
            pool=30.0
        )
    )
```

#### 2. Request Processing Optimization
```python
# Optimize request processing
from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware

app = FastAPI()

# Enable gzip compression
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Optimize JSON serialization
app.json_encoder = orjson.JSONEncoder
app.json_decoder = orjson.JSONDecoder
```

#### 3. Rate Limiting Optimization
```python
# Optimize rate limiting
class OptimizedRateLimiter:
    def __init__(self):
        self.redis_client = redis.Redis(
            host="redis-service",
            port=6379,
            db=0,
            connection_pool=redis.ConnectionPool(
                max_connections=100,
                retry_on_timeout=True
            )
        )
    
    async def check_rate_limit(self, key: str, limit: int, window: int):
        # Use Redis pipeline for batch operations
        pipe = self.redis_client.pipeline()
        pipe.incr(key)
        pipe.expire(key, window)
        results = pipe.execute()
        
        return results[0] <= limit
```

### Streaming Service Optimization

#### 1. WebSocket Connection Management
```python
# Optimize WebSocket connections
import asyncio
from websockets import WebSocketServerProtocol

class OptimizedWebSocketManager:
    def __init__(self):
        self.connections = {}
        self.connection_limit = 10000
        self.heartbeat_interval = 30
        self.heartbeat_timeout = 60
    
    async def handle_connection(self, websocket: WebSocketServerProtocol):
        # Limit concurrent connections
        if len(self.connections) >= self.connection_limit:
            await websocket.close(code=1013, reason="Server overloaded")
            return
        
        # Add connection
        connection_id = str(uuid.uuid4())
        self.connections[connection_id] = websocket
        
        try:
            # Start heartbeat task
            heartbeat_task = asyncio.create_task(
                self.heartbeat(websocket)
            )
            
            # Handle messages
            async for message in websocket:
                await self.process_message(connection_id, message)
                
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
        finally:
            # Cleanup
            heartbeat_task.cancel()
            self.connections.pop(connection_id, None)
    
    async def heartbeat(self, websocket: WebSocketServerProtocol):
        while True:
            try:
                await websocket.ping()
                await asyncio.sleep(self.heartbeat_interval)
            except Exception:
                break
```

#### 2. Message Processing Optimization
```python
# Optimize message processing
import asyncio
from concurrent.futures import ThreadPoolExecutor

class OptimizedMessageProcessor:
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=100)
        self.message_queue = asyncio.Queue(maxsize=10000)
        self.batch_size = 100
        self.batch_timeout = 0.1
    
    async def process_messages(self):
        batch = []
        last_batch_time = time.time()
        
        while True:
            try:
                # Collect messages in batches
                message = await asyncio.wait_for(
                    self.message_queue.get(),
                    timeout=self.batch_timeout
                )
                batch.append(message)
                
                # Process batch when full or timeout
                if (len(batch) >= self.batch_size or 
                    time.time() - last_batch_time >= self.batch_timeout):
                    await self.process_batch(batch)
                    batch = []
                    last_batch_time = time.time()
                    
            except asyncio.TimeoutError:
                if batch:
                    await self.process_batch(batch)
                    batch = []
                    last_batch_time = time.time()
    
    async def process_batch(self, batch):
        # Process batch in parallel
        tasks = [
            asyncio.create_task(self.process_single_message(msg))
            for msg in batch
        ]
        await asyncio.gather(*tasks, return_exceptions=True)
```

### Auth Service Optimization

#### 1. JWT Verification Optimization
```python
# Optimize JWT verification
import jwt
from functools import lru_cache

class OptimizedJWTVerifier:
    def __init__(self):
        self.jwks_cache = {}
        self.cache_ttl = 3600  # 1 hour
    
    @lru_cache(maxsize=1000)
    def verify_token_cached(self, token: str, jwks_url: str):
        """Cache verified tokens to avoid repeated verification"""
        try:
            # Decode without verification first to get header
            header = jwt.get_unverified_header(token)
            kid = header.get('kid')
            
            # Get JWKS
            jwks = self.get_jwks(jwks_url)
            key = self.get_key_from_jwks(jwks, kid)
            
            # Verify token
            payload = jwt.decode(
                token,
                key,
                algorithms=['RS256'],
                audience='access-layer',
                issuer='https://keycloak.254carbon.com/realms/254carbon'
            )
            
            return payload
        except Exception as e:
            logger.error(f"JWT verification failed: {e}")
            raise
    
    def get_jwks(self, jwks_url: str):
        """Get JWKS with caching"""
        if jwks_url in self.jwks_cache:
            cached_data, timestamp = self.jwks_cache[jwks_url]
            if time.time() - timestamp < self.cache_ttl:
                return cached_data
        
        # Fetch fresh JWKS
        response = httpx.get(jwks_url)
        jwks = response.json()
        
        # Cache JWKS
        self.jwks_cache[jwks_url] = (jwks, time.time())
        
        return jwks
```

### Entitlements Service Optimization

#### 1. Rule Engine Optimization
```python
# Optimize rule engine
import re
from functools import lru_cache

class OptimizedRuleEngine:
    def __init__(self):
        self.compiled_rules = {}
        self.rule_cache = {}
    
    def compile_rule(self, rule: dict):
        """Compile rule for faster evaluation"""
        rule_id = rule['id']
        
        if rule_id in self.compiled_rules:
            return self.compiled_rules[rule_id]
        
        compiled_rule = {
            'id': rule_id,
            'conditions': [],
            'permissions': rule['permissions']
        }
        
        # Compile conditions
        for condition in rule['conditions']:
            if condition['type'] == 'regex':
                compiled_rule['conditions'].append({
                    'type': 'regex',
                    'field': condition['field'],
                    'pattern': re.compile(condition['pattern']),
                    'operator': condition['operator']
                })
            else:
                compiled_rule['conditions'].append(condition)
        
        self.compiled_rules[rule_id] = compiled_rule
        return compiled_rule
    
    @lru_cache(maxsize=10000)
    def evaluate_rule_cached(self, rule_id: str, context_hash: str):
        """Cache rule evaluation results"""
        rule = self.compiled_rules.get(rule_id)
        if not rule:
            return False
        
        # Evaluate conditions
        for condition in rule['conditions']:
            if not self.evaluate_condition(condition, context_hash):
                return False
        
        return True
```

### Metrics Service Optimization

#### 1. Metrics Collection Optimization
```python
# Optimize metrics collection
import asyncio
from collections import defaultdict
import time

class OptimizedMetricsCollector:
    def __init__(self):
        self.metrics_buffer = defaultdict(list)
        self.buffer_size = 1000
        self.flush_interval = 10  # seconds
        self.metrics_lock = asyncio.Lock()
    
    async def collect_metric(self, name: str, value: float, labels: dict = None):
        """Collect metric with buffering"""
        async with self.metrics_lock:
            metric_data = {
                'name': name,
                'value': value,
                'labels': labels or {},
                'timestamp': time.time()
            }
            
            self.metrics_buffer[name].append(metric_data)
            
            # Flush if buffer is full
            if len(self.metrics_buffer[name]) >= self.buffer_size:
                await self.flush_metrics(name)
    
    async def flush_metrics(self, name: str):
        """Flush metrics to storage"""
        if name not in self.metrics_buffer:
            return
        
        metrics = self.metrics_buffer[name]
        if not metrics:
            return
        
        # Batch insert to database
        await self.batch_insert_metrics(metrics)
        
        # Clear buffer
        self.metrics_buffer[name] = []
    
    async def batch_insert_metrics(self, metrics: list):
        """Batch insert metrics for better performance"""
        # Use bulk insert for better performance
        query = """
        INSERT INTO metrics (name, value, labels, timestamp)
        VALUES ($1, $2, $3, $4)
        """
        
        values = [
            (m['name'], m['value'], json.dumps(m['labels']), m['timestamp'])
            for m in metrics
        ]
        
        await self.db.executemany(query, values)
```

## Infrastructure Optimization

### Kubernetes Optimization

#### 1. Resource Requests and Limits
```yaml
# Optimize resource allocation
apiVersion: apps/v1
kind: Deployment
metadata:
  name: gateway-deployment
spec:
  template:
    spec:
      containers:
      - name: gateway
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
        # Enable CPU and memory limits
        securityContext:
          runAsNonRoot: true
          allowPrivilegeEscalation: false
          readOnlyRootFilesystem: true
```

#### 2. Pod Affinity and Anti-Affinity
```yaml
# Optimize pod placement
apiVersion: apps/v1
kind: Deployment
metadata:
  name: gateway-deployment
spec:
  template:
    spec:
      affinity:
        # Spread pods across nodes
        podAntiAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
          - weight: 100
            podAffinityTerm:
              labelSelector:
                matchExpressions:
                - key: app
                  operator: In
                  values:
                  - gateway
              topologyKey: kubernetes.io/hostname
        # Prefer nodes with SSD storage
        nodeAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
          - weight: 50
            preference:
              matchExpressions:
              - key: storage-type
                operator: In
                values:
                - ssd
```

#### 3. Horizontal Pod Autoscaling
```yaml
# Enable auto-scaling
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: gateway-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: gateway-deployment
  minReplicas: 3
  maxReplicas: 20
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 60
      policies:
      - type: Percent
        value: 100
        periodSeconds: 15
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
      - type: Percent
        value: 10
        periodSeconds: 60
```

### Network Optimization

#### 1. Service Mesh Configuration
```yaml
# Optimize service mesh
apiVersion: v1
kind: ConfigMap
metadata:
  name: istio-config
data:
  mesh: |
    defaultConfig:
      proxyStatsMatcher:
        inclusionRegexps:
        - ".*circuit_breakers.*"
        - ".*upstream_rq_retry.*"
        - ".*upstream_rq_timeout.*"
        - ".*upstream_rq_pending.*"
        - ".*upstream_rq_total.*"
        - ".*upstream_cx_total.*"
        - ".*upstream_cx_active.*"
        - ".*upstream_cx_connect_timeout.*"
        - ".*upstream_cx_rx_bytes_total.*"
        - ".*upstream_cx_tx_bytes_total.*"
        - ".*upstream_http.*"
        - ".*upstream_rq.*"
        - ".*upstream_cx.*"
        - ".*circuit_breakers.*"
        - ".*upstream_rq_retry.*"
        - ".*upstream_rq_timeout.*"
        - ".*upstream_rq_pending.*"
        - ".*upstream_rq_total.*"
        - ".*upstream_cx_total.*"
        - ".*upstream_cx_active.*"
        - ".*upstream_cx_connect_timeout.*"
        - ".*upstream_cx_rx_bytes_total.*"
        - ".*upstream_cx_tx_bytes_total.*"
        - ".*upstream_http.*"
        - ".*upstream_rq.*"
        - ".*upstream_cx.*"
```

#### 2. Load Balancer Optimization
```yaml
# Optimize load balancer
apiVersion: v1
kind: Service
metadata:
  name: gateway-service
  annotations:
    service.beta.kubernetes.io/aws-load-balancer-type: "nlb"
    service.beta.kubernetes.io/aws-load-balancer-cross-zone-load-balancing-enabled: "true"
    service.beta.kubernetes.io/aws-load-balancer-connection-draining-enabled: "true"
    service.beta.kubernetes.io/aws-load-balancer-connection-draining-timeout: "60"
spec:
  type: LoadBalancer
  ports:
  - port: 80
    targetPort: 8000
    protocol: TCP
  - port: 443
    targetPort: 8000
    protocol: TCP
  selector:
    app: gateway
```

## Database Optimization

### PostgreSQL Optimization

#### 1. Connection Pooling
```python
# Optimize database connections
import asyncpg
from asyncpg import Pool

class OptimizedDatabasePool:
    def __init__(self):
        self.pool = None
    
    async def create_pool(self):
        self.pool = await asyncpg.create_pool(
            host="postgres-service",
            port=5432,
            database="access",
            user="access",
            password="access_password",
            min_size=10,
            max_size=100,
            max_queries=50000,
            max_inactive_connection_lifetime=300.0,
            command_timeout=60,
            server_settings={
                'application_name': 'access-layer',
                'tcp_keepalives_idle': '600',
                'tcp_keepalives_interval': '30',
                'tcp_keepalives_count': '3',
            }
        )
    
    async def execute_query(self, query: str, *args):
        async with self.pool.acquire() as connection:
            return await connection.fetch(query, *args)
```

#### 2. Query Optimization
```sql
-- Optimize database queries
-- Create indexes for frequently queried columns
CREATE INDEX CONCURRENTLY idx_entitlements_user_resource 
ON entitlements (user_id, resource);

CREATE INDEX CONCURRENTLY idx_entitlements_action 
ON entitlements (action);

CREATE INDEX CONCURRENTLY idx_entitlements_created_at 
ON entitlements (created_at);

-- Optimize query performance
EXPLAIN (ANALYZE, BUFFERS) 
SELECT * FROM entitlements 
WHERE user_id = $1 AND resource = $2 AND action = $3;

-- Use prepared statements
PREPARE get_entitlements AS
SELECT * FROM entitlements 
WHERE user_id = $1 AND resource = $2 AND action = $3;
```

#### 3. Database Configuration
```sql
-- Optimize PostgreSQL configuration
-- postgresql.conf optimizations
shared_buffers = 256MB
effective_cache_size = 1GB
work_mem = 4MB
maintenance_work_mem = 64MB
checkpoint_completion_target = 0.9
wal_buffers = 16MB
default_statistics_target = 100
random_page_cost = 1.1
effective_io_concurrency = 200
max_worker_processes = 8
max_parallel_workers_per_gather = 4
max_parallel_workers = 8
max_parallel_maintenance_workers = 4
```

### Redis Optimization

#### 1. Memory Optimization
```python
# Optimize Redis configuration
import redis
from redis.sentinel import Sentinel

class OptimizedRedisClient:
    def __init__(self):
        self.sentinel = Sentinel([
            ('redis-sentinel-1', 26379),
            ('redis-sentinel-2', 26379),
            ('redis-sentinel-3', 26379)
        ])
        
        self.master = self.sentinel.master_for(
            'mymaster',
            socket_timeout=0.1,
            socket_connect_timeout=0.1,
            retry_on_timeout=True,
            health_check_interval=30
        )
        
        self.slave = self.sentinel.slave_for(
            'mymaster',
            socket_timeout=0.1,
            socket_connect_timeout=0.1,
            retry_on_timeout=True,
            health_check_interval=30
        )
    
    async def get_cached_data(self, key: str):
        """Get data from cache with fallback"""
        try:
            return await self.slave.get(key)
        except Exception:
            # Fallback to master
            return await self.master.get(key)
    
    async def set_cached_data(self, key: str, value: str, ttl: int = 300):
        """Set data in cache with TTL"""
        return await self.master.setex(key, ttl, value)
```

#### 2. Redis Configuration
```redis
# redis.conf optimizations
maxmemory 2gb
maxmemory-policy allkeys-lru
tcp-keepalive 300
timeout 0
tcp-backlog 511
databases 16
save 900 1
save 300 10
save 60 10000
stop-writes-on-bgsave-error yes
rdbcompression yes
rdbchecksum yes
dbfilename dump.rdb
dir /data
slave-serve-stale-data yes
slave-read-only yes
repl-diskless-sync no
repl-diskless-sync-delay 5
repl-ping-slave-period 10
repl-timeout 60
repl-disable-tcp-nodelay no
repl-backlog-size 1mb
repl-backlog-ttl 3600
```

## Caching Optimization

### Application-Level Caching

#### 1. In-Memory Caching
```python
# Optimize in-memory caching
import asyncio
from typing import Any, Optional
import time

class OptimizedCache:
    def __init__(self, max_size: int = 10000, ttl: int = 300):
        self.max_size = max_size
        self.ttl = ttl
        self.cache = {}
        self.access_times = {}
        self.lock = asyncio.Lock()
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        async with self.lock:
            if key in self.cache:
                # Check TTL
                if time.time() - self.access_times[key] < self.ttl:
                    self.access_times[key] = time.time()
                    return self.cache[key]
                else:
                    # Expired, remove
                    del self.cache[key]
                    del self.access_times[key]
            return None
    
    async def set(self, key: str, value: Any) -> None:
        """Set value in cache"""
        async with self.lock:
            # Evict if cache is full
            if len(self.cache) >= self.max_size:
                await self._evict_lru()
            
            self.cache[key] = value
            self.access_times[key] = time.time()
    
    async def _evict_lru(self) -> None:
        """Evict least recently used item"""
        if not self.access_times:
            return
        
        lru_key = min(self.access_times.keys(), key=lambda k: self.access_times[k])
        del self.cache[lru_key]
        del self.access_times[lru_key]
```

#### 2. Distributed Caching
```python
# Optimize distributed caching
import asyncio
import json
import hashlib
from typing import Any, Optional

class OptimizedDistributedCache:
    def __init__(self, redis_client):
        self.redis = redis_client
        self.local_cache = {}
        self.local_cache_ttl = 60  # 1 minute
        self.local_cache_max_size = 1000
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from distributed cache"""
        # Try local cache first
        if key in self.local_cache:
            value, timestamp = self.local_cache[key]
            if time.time() - timestamp < self.local_cache_ttl:
                return value
            else:
                del self.local_cache[key]
        
        # Try Redis
        try:
            value = await self.redis.get(key)
            if value:
                # Cache locally
                await self._cache_locally(key, value)
                return json.loads(value)
        except Exception as e:
            logger.error(f"Redis get error: {e}")
        
        return None
    
    async def set(self, key: str, value: Any, ttl: int = 300) -> None:
        """Set value in distributed cache"""
        serialized_value = json.dumps(value)
        
        # Set in Redis
        try:
            await self.redis.setex(key, ttl, serialized_value)
        except Exception as e:
            logger.error(f"Redis set error: {e}")
        
        # Cache locally
        await self._cache_locally(key, serialized_value)
    
    async def _cache_locally(self, key: str, value: str) -> None:
        """Cache value locally"""
        if len(self.local_cache) >= self.local_cache_max_size:
            # Evict oldest
            oldest_key = min(self.local_cache.keys(), 
                           key=lambda k: self.local_cache[k][1])
            del self.local_cache[oldest_key]
        
        self.local_cache[key] = (value, time.time())
```

## Load Testing

### Load Testing Framework

#### 1. WebSocket Load Testing
```python
# Optimize WebSocket load testing
import asyncio
import websockets
import json
import time
from typing import List, Dict, Any

class WebSocketLoadTester:
    def __init__(self, url: str, max_connections: int = 1000):
        self.url = url
        self.max_connections = max_connections
        self.connections = []
        self.stats = {
            'total_connections': 0,
            'successful_connections': 0,
            'failed_connections': 0,
            'messages_sent': 0,
            'messages_received': 0,
            'errors': 0
        }
    
    async def run_load_test(self, duration: int = 300):
        """Run load test for specified duration"""
        start_time = time.time()
        
        # Create connections
        tasks = []
        for i in range(self.max_connections):
            task = asyncio.create_task(self.create_connection(i))
            tasks.append(task)
        
        # Wait for duration
        await asyncio.sleep(duration)
        
        # Close connections
        for task in tasks:
            task.cancel()
        
        # Calculate stats
        end_time = time.time()
        total_time = end_time - start_time
        
        print(f"Load test completed in {total_time:.2f} seconds")
        print(f"Total connections: {self.stats['total_connections']}")
        print(f"Successful connections: {self.stats['successful_connections']}")
        print(f"Failed connections: {self.stats['failed_connections']}")
        print(f"Messages sent: {self.stats['messages_sent']}")
        print(f"Messages received: {self.stats['messages_received']}")
        print(f"Errors: {self.stats['errors']}")
        print(f"Connection rate: {self.stats['total_connections'] / total_time:.2f} conn/sec")
        print(f"Message rate: {self.stats['messages_sent'] / total_time:.2f} msg/sec")
    
    async def create_connection(self, connection_id: int):
        """Create a single WebSocket connection"""
        try:
            self.stats['total_connections'] += 1
            
            async with websockets.connect(self.url) as websocket:
                self.stats['successful_connections'] += 1
                
                # Send authentication
                auth_message = {
                    "type": "auth",
                    "token": f"test-token-{connection_id}"
                }
                await websocket.send(json.dumps(auth_message))
                
                # Send subscription
                subscribe_message = {
                    "type": "subscribe",
                    "topic": "254carbon.pricing.curve.updates.v1"
                }
                await websocket.send(json.dumps(subscribe_message))
                self.stats['messages_sent'] += 1
                
                # Listen for messages
                async for message in websocket:
                    self.stats['messages_received'] += 1
                    
                    # Send periodic messages
                    if self.stats['messages_received'] % 10 == 0:
                        ping_message = {"type": "ping"}
                        await websocket.send(json.dumps(ping_message))
                        self.stats['messages_sent'] += 1
                
        except Exception as e:
            self.stats['failed_connections'] += 1
            self.stats['errors'] += 1
            logger.error(f"Connection {connection_id} failed: {e}")
```

#### 2. API Load Testing
```python
# Optimize API load testing
import asyncio
import aiohttp
import time
from typing import List, Dict, Any

class APILoadTester:
    def __init__(self, base_url: str, max_concurrent: int = 100):
        self.base_url = base_url
        self.max_concurrent = max_concurrent
        self.stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'total_response_time': 0,
            'errors': 0
        }
    
    async def run_load_test(self, duration: int = 300):
        """Run API load test"""
        start_time = time.time()
        
        # Create semaphore to limit concurrent requests
        semaphore = asyncio.Semaphore(self.max_concurrent)
        
        # Create tasks
        tasks = []
        for i in range(self.max_concurrent):
            task = asyncio.create_task(self.worker(semaphore, i))
            tasks.append(task)
        
        # Wait for duration
        await asyncio.sleep(duration)
        
        # Cancel tasks
        for task in tasks:
            task.cancel()
        
        # Calculate stats
        end_time = time.time()
        total_time = end_time - start_time
        
        print(f"API load test completed in {total_time:.2f} seconds")
        print(f"Total requests: {self.stats['total_requests']}")
        print(f"Successful requests: {self.stats['successful_requests']}")
        print(f"Failed requests: {self.stats['failed_requests']}")
        print(f"Average response time: {self.stats['total_response_time'] / max(self.stats['total_requests'], 1):.2f}ms")
        print(f"Request rate: {self.stats['total_requests'] / total_time:.2f} req/sec")
        print(f"Error rate: {self.stats['errors'] / max(self.stats['total_requests'], 1):.2%}")
    
    async def worker(self, semaphore: asyncio.Semaphore, worker_id: int):
        """Worker coroutine for making requests"""
        async with aiohttp.ClientSession() as session:
            while True:
                async with semaphore:
                    await self.make_request(session, worker_id)
                await asyncio.sleep(0.1)  # Small delay between requests
    
    async def make_request(self, session: aiohttp.ClientSession, worker_id: int):
        """Make a single API request"""
        try:
            self.stats['total_requests'] += 1
            start_time = time.time()
            
            async with session.get(f"{self.base_url}/health") as response:
                end_time = time.time()
                response_time = (end_time - start_time) * 1000
                
                if response.status == 200:
                    self.stats['successful_requests'] += 1
                else:
                    self.stats['failed_requests'] += 1
                    self.stats['errors'] += 1
                
                self.stats['total_response_time'] += response_time
                
        except Exception as e:
            self.stats['failed_requests'] += 1
            self.stats['errors'] += 1
            logger.error(f"Request failed: {e}")
```

## Performance Benchmarks

### Benchmark Targets

#### 1. Response Time Benchmarks
- **Gateway Service**: P95 < 100ms, P99 < 200ms
- **Auth Service**: P95 < 50ms, P99 < 100ms
- **Entitlements Service**: P95 < 100ms, P99 < 200ms
- **Streaming Service**: P95 < 50ms, P99 < 100ms
- **Metrics Service**: P95 < 50ms, P99 < 100ms

#### 2. Throughput Benchmarks
- **Gateway Service**: > 1000 RPS
- **Auth Service**: > 2000 RPS
- **Entitlements Service**: > 1000 RPS
- **Streaming Service**: > 5000 concurrent connections
- **Metrics Service**: > 10000 metrics/sec

#### 3. Resource Utilization Benchmarks
- **CPU Usage**: < 70% average
- **Memory Usage**: < 80% average
- **Network Bandwidth**: < 80% average
- **Disk I/O**: < 80% average

### Benchmarking Tools

#### 1. Automated Benchmarking
```bash
#!/bin/bash
# Performance benchmarking script

echo "Starting performance benchmarks..."

# WebSocket load test
python tests/performance/websocket_load_test.py \
  --streaming-url ws://localhost:8001/ws \
  --users 1000 \
  --duration 300 \
  --output websocket-benchmark.json

# API load test
python tests/performance/api_load_test.py \
  --gateway-url http://localhost:8000 \
  --concurrent-users 100 \
  --duration 300 \
  --output api-benchmark.json

# Database performance test
python tests/performance/database_load_test.py \
  --postgres-url postgres://access:access@localhost:5432/access \
  --concurrent-connections 50 \
  --duration 300 \
  --output database-benchmark.json

# Redis performance test
python tests/performance/redis_load_test.py \
  --redis-url redis://localhost:6379/0 \
  --concurrent-connections 100 \
  --duration 300 \
  --output redis-benchmark.json

echo "Benchmarks completed. Results saved to benchmark-*.json files."
```

#### 2. Performance Monitoring
```python
# Performance monitoring script
import asyncio
import time
import psutil
import requests
from typing import Dict, List

class PerformanceMonitor:
    def __init__(self):
        self.metrics = []
    
    async def monitor_performance(self, duration: int = 300):
        """Monitor system performance"""
        start_time = time.time()
        
        while time.time() - start_time < duration:
            # Collect system metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            network = psutil.net_io_counters()
            
            # Collect service metrics
            service_metrics = await self.collect_service_metrics()
            
            # Store metrics
            metric = {
                'timestamp': time.time(),
                'cpu_percent': cpu_percent,
                'memory_percent': memory.percent,
                'disk_percent': disk.percent,
                'network_bytes_sent': network.bytes_sent,
                'network_bytes_recv': network.bytes_recv,
                'services': service_metrics
            }
            
            self.metrics.append(metric)
            
            # Wait before next collection
            await asyncio.sleep(10)
        
        # Generate report
        self.generate_report()
    
    async def collect_service_metrics(self) -> Dict:
        """Collect metrics from services"""
        services = ['gateway', 'streaming', 'auth', 'entitlements', 'metrics']
        metrics = {}
        
        for service in services:
            try:
                response = requests.get(f"http://localhost:8000/metrics", timeout=5)
                if response.status_code == 200:
                    metrics[service] = self.parse_metrics(response.text)
                else:
                    metrics[service] = {'error': f"HTTP {response.status_code}"}
            except Exception as e:
                metrics[service] = {'error': str(e)}
        
        return metrics
    
    def parse_metrics(self, metrics_text: str) -> Dict:
        """Parse Prometheus metrics"""
        metrics = {}
        for line in metrics_text.split('\n'):
            if line.startswith('#') or not line.strip():
                continue
            
            parts = line.split(' ')
            if len(parts) >= 2:
                metric_name = parts[0]
                metric_value = float(parts[1])
                metrics[metric_name] = metric_value
        
        return metrics
    
    def generate_report(self):
        """Generate performance report"""
        if not self.metrics:
            return
        
        # Calculate averages
        avg_cpu = sum(m['cpu_percent'] for m in self.metrics) / len(self.metrics)
        avg_memory = sum(m['memory_percent'] for m in self.metrics) / len(self.metrics)
        avg_disk = sum(m['disk_percent'] for m in self.metrics) / len(self.metrics)
        
        print("Performance Report")
        print("==================")
        print(f"Average CPU Usage: {avg_cpu:.2f}%")
        print(f"Average Memory Usage: {avg_memory:.2f}%")
        print(f"Average Disk Usage: {avg_disk:.2f}%")
        print(f"Total Metrics Collected: {len(self.metrics)}")
        
        # Check against benchmarks
        if avg_cpu > 70:
            print("⚠️  CPU usage exceeds benchmark target (70%)")
        if avg_memory > 80:
            print("⚠️  Memory usage exceeds benchmark target (80%)")
        if avg_disk > 80:
            print("⚠️  Disk usage exceeds benchmark target (80%)")
```

## Optimization Checklist

### Pre-Production Optimization
- [ ] Set appropriate resource requests and limits
- [ ] Configure horizontal pod autoscaling
- [ ] Optimize database connection pooling
- [ ] Implement caching strategies
- [ ] Configure load balancing
- [ ] Set up monitoring and alerting
- [ ] Perform load testing
- [ ] Optimize application code
- [ ] Configure network policies
- [ ] Set up performance benchmarks

### Production Optimization
- [ ] Monitor performance metrics
- [ ] Analyze bottleneck areas
- [ ] Optimize slow queries
- [ ] Scale resources as needed
- [ ] Update caching strategies
- [ ] Fine-tune configuration
- [ ] Perform regular load testing
- [ ] Update performance benchmarks
- [ ] Document optimization changes
- [ ] Review and update procedures

---

**Last Updated**: 2024-01-01  
**Version**: 1.0.0  
**Maintainer**: 254Carbon Performance Team
