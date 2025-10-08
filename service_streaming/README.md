# Streaming Service

The Streaming Service provides real-time data distribution capabilities for the 254Carbon Access Layer, supporting both WebSocket and Server-Sent Events (SSE) protocols.

## Overview

The Streaming Service handles:
- **WebSocket Connections** - Full-duplex real-time communication
- **Server-Sent Events (SSE)** - Server-to-client streaming
- **Kafka Integration** - Message consumption and distribution
- **Subscription Management** - Topic-based message filtering
- **Connection Management** - WebSocket and SSE connection lifecycle
- **Authentication** - JWT token validation for streaming connections
- **Rate Limiting** - Connection and message rate controls

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   WebSocket     │───▶│  Streaming      │───▶│     Kafka       │
│   Clients       │    │   Service       │    │   Broker        │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌─────────────────┐
                       │   SSE Clients   │
                       └─────────────────┘
                              │
                              ▼
                       ┌─────────────────┐
                       │  Auth Service   │
                       └─────────────────┘
```

## Features

### WebSocket Support
- Full-duplex real-time communication
- Connection management with heartbeat
- Topic-based subscriptions
- Message filtering and routing
- Connection pooling and scaling

### Server-Sent Events (SSE)
- Server-to-client streaming
- HTTP-based protocol
- Automatic reconnection support
- Topic subscriptions via REST API
- Browser-native support

### Kafka Integration
- Message consumption from Kafka topics
- Real-time message distribution
- Topic subscription management
- Message filtering and routing
- Offset management

### Authentication & Authorization
- JWT token validation
- User context extraction
- Entitlement checks for topics
- Multi-tenant support
- Connection-level security

### Connection Management
- WebSocket connection lifecycle
- SSE connection management
- Heartbeat monitoring
- Automatic cleanup
- Connection statistics

### Observability
- Connection monitoring
- Message throughput tracking
- Performance metrics
- Distributed tracing
- Health checks

## API Endpoints

### WebSocket Endpoint

#### WebSocket Connection
```
ws://localhost:8001/ws/stream?token=<jwt-token>
```

**Connection Flow:**
1. Client connects with JWT token
2. Server validates token and establishes connection
3. Server sends connection confirmation
4. Client can subscribe to topics
5. Server broadcasts messages to subscribed clients

### SSE Endpoints

#### SSE Stream
```http
GET /sse/stream?token=<jwt-token>
```

**Response:** Server-Sent Events stream

#### Subscribe to Topic
```http
POST /sse/subscribe
Content-Type: application/x-www-form-urlencoded

connection_id=conn-12345&topic=served.market.latest_prices.v1&filters={"commodity":"oil"}
```

**Response:**
```json
{
  "success": true,
  "topic": "served.market.latest_prices.v1",
  "filters": {
    "commodity": "oil"
  },
  "connection_id": "conn-12345"
}
```

### Administrative Endpoints

#### Service Status
```http
GET /health
```

**Response:**
```json
{
  "service": "streaming",
  "status": "ok",
  "uptime_seconds": 5231,
  "dependencies": {
    "kafka": "ok",
    "auth": "ok",
    "entitlements": "ok"
  },
  "version": "1.0.0",
  "commit": "abc1234"
}
```

#### Connection Statistics
```http
GET /stats
```

**Response:**
```json
{
  "websocket": {
    "total_connections": 150,
    "active_connections": 145,
    "total_messages": 10000,
    "messages_per_second": 50
  },
  "sse": {
    "total_connections": 75,
    "active_connections": 70,
    "total_messages": 5000,
    "messages_per_second": 25
  },
  "subscriptions": {
    "total_topics": 10,
    "active_subscriptions": 200,
    "topics": {
      "pricing.updates": 50,
      "curve.changes": 30,
      "instruments.new": 20
    }
  },
  "kafka": {
    "consumers": 2,
    "topics": ["pricing.updates", "curve.changes"],
    "messages_consumed": 15000
  }
}
```

## Supported Topics

The streaming service enforces entitlements per topic. Built-in topics include:

- `served.market.latest_prices.v1` — Served latest price projections (default subscription)
- `pricing.curve.updates.v1` — Curve pricing updates
- `market.data.updates.v1` — Normalized market data feeds

Additional topics can be onboarded by extending the topic registry and updating entitlement rules.

## Message Formats

### WebSocket Messages

#### Client → Server

**Subscribe to Topics**
```json
{
  "action": "subscribe",
  "data": {
    "topics": ["pricing.updates", "curve.changes"],
    "filters": {
      "commodity": "oil",
      "region": "north_sea"
    }
  }
}
```

**Unsubscribe from Topics**
```json
{
  "action": "unsubscribe",
  "data": {
    "topics": ["pricing.updates"]
  }
}
```

**Ping/Heartbeat**
```json
{
  "action": "ping",
  "data": {}
}
```

#### Server → Client

**Connection Established**
```json
{
  "type": "connection_established",
  "connection_id": "conn-12345",
  "user_id": "user-123",
  "tenant_id": "tenant-1"
}
```

**Data Message**
```json
{
  "type": "data",
  "topic": "pricing.updates",
  "data": {
    "instrument_id": "BRENT_CRUDE",
    "price": 75.50,
    "volume": 1000,
    "timestamp": "2024-01-15T10:30:00Z"
  },
  "timestamp": 1705312200000,
  "partition": 0,
  "offset": 12345
}
```

**Error Message**
```json
{
  "type": "error",
  "error": "SUBSCRIPTION_DENIED",
  "message": "Insufficient permissions for topic pricing.updates",
  "details": {
    "topic": "pricing.updates",
    "required_role": "analyst"
  }
}
```

### SSE Events

**Connection Established Event**
```
event: connection_established
data: {"connection_id": "conn-12345", "user_id": "user-123", "tenant_id": "tenant-1"}

```

**Data Event**
```
event: data
data: {"topic": "pricing.updates", "data": {"instrument_id": "BRENT_CRUDE", "price": 75.50}, "timestamp": 1705312200000}

```

**Error Event**
```
event: error
data: {"error": "SUBSCRIPTION_DENIED", "message": "Insufficient permissions"}

```

## Configuration

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `ACCESS_ENV` | Environment name | `local` | No |
| `ACCESS_LOG_LEVEL` | Log verbosity | `info` | No |
| `ACCESS_KAFKA_BOOTSTRAP` | Kafka bootstrap servers | `localhost:9092` | Yes |
| `ACCESS_AUTH_SERVICE_URL` | Auth service URL | `http://localhost:8010` | Yes |
| `ACCESS_ENTITLEMENTS_SERVICE_URL` | Entitlements service URL | `http://localhost:8011` | Yes |
| `ACCESS_METRICS_ENDPOINT` | Metrics service URL | `http://localhost:8012` | Yes |
| `ACCESS_MAX_WS_CONNECTIONS` | Max WebSocket connections | `1000` | No |
| `ACCESS_MAX_SSE_CONNECTIONS` | Max SSE connections | `500` | No |
| `ACCESS_HEARTBEAT_TIMEOUT` | Heartbeat timeout (seconds) | `30` | No |
| `ACCESS_ENABLE_TRACING` | Enable distributed tracing | `false` | No |

### Kafka Configuration

| Setting | Description | Default |
|---------|-------------|---------|
| `bootstrap_servers` | Kafka bootstrap servers | `localhost:9092` |
| `group_id` | Consumer group ID | `streaming-service` |
| `auto_offset_reset` | Offset reset policy | `latest` |
| `enable_auto_commit` | Auto-commit offsets | `true` |
| `max_poll_records` | Max records per poll | `100` |

### Connection Limits

| Connection Type | Default Limit | Description |
|----------------|---------------|-------------|
| WebSocket | 1000 | Total WebSocket connections |
| SSE | 500 | Total SSE connections |
| Per User | 10 | Connections per user |
| Per Tenant | 100 | Connections per tenant |

## Development

### Local Development

1. **Install dependencies:**
   ```bash
   pip install -r requirements-dev.txt
   ```

2. **Start the service:**
   ```bash
   cd service_streaming
   uvicorn app.main:app --reload --port 8001
   ```

3. **Run tests:**
   ```bash
   pytest tests/ -v
   ```

### Docker Development

1. **Build the image:**
   ```bash
   docker build -t streaming-service .
   ```

2. **Run the container:**
   ```bash
   docker run -p 8001:8001 \
     -e ACCESS_KAFKA_BOOTSTRAP=localhost:9092 \
     -e ACCESS_AUTH_SERVICE_URL=http://localhost:8010 \
     -e ACCESS_ENTITLEMENTS_SERVICE_URL=http://localhost:8011 \
     streaming-service
   ```

### Testing

#### Unit Tests
```bash
pytest tests/test_kafka_consumer.py -v
pytest tests/test_websocket_manager.py -v
pytest tests/test_main.py -v
```

#### Integration Tests
```bash
pytest tests/integration/ -v
```

#### WebSocket Testing
```bash
# Test WebSocket connection
python -c "
import asyncio
import websockets
import json

async def test_websocket():
    uri = 'ws://localhost:8001/ws/stream?token=test-token'
    async with websockets.connect(uri) as websocket:
        # Send subscription
        await websocket.send(json.dumps({
            'action': 'subscribe',
            'data': {'topics': ['pricing.updates']}
        }))
        
        # Listen for messages
        async for message in websocket:
            print(f'Received: {message}')

asyncio.run(test_websocket())
"
```

#### SSE Testing
```bash
# Test SSE connection
curl -N "http://localhost:8001/sse/stream?token=test-token"
```

## Monitoring

### Metrics

The Streaming Service exposes Prometheus metrics at `/metrics`:

- `websocket_connections_total` - Total WebSocket connections
- `sse_connections_total` - Total SSE connections
- `messages_sent_total` - Total messages sent
- `messages_received_total` - Total messages received
- `subscriptions_total` - Total active subscriptions
- `kafka_messages_consumed_total` - Total Kafka messages consumed

### Logging

Structured JSON logging with correlation IDs:

```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "level": "INFO",
  "service": "streaming",
  "trace_id": "abc123",
  "connection_id": "conn-456",
  "message": "WebSocket connection established",
  "user_id": "user-123",
  "tenant_id": "tenant-1"
}
```

### Health Checks

Health check endpoint provides service status:

```bash
curl http://localhost:8001/health
```

## Deployment

### Kubernetes

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: streaming-service
spec:
  replicas: 3
  selector:
    matchLabels:
      app: streaming-service
  template:
    metadata:
      labels:
        app: streaming-service
    spec:
      containers:
      - name: streaming-service
        image: ghcr.io/254carbon/access-layer-streaming:latest
        ports:
        - containerPort: 8001
        env:
        - name: ACCESS_KAFKA_BOOTSTRAP
          value: "kafka-service:9092"
        - name: ACCESS_AUTH_SERVICE_URL
          value: "http://auth-service:8010"
        - name: ACCESS_ENTITLEMENTS_SERVICE_URL
          value: "http://entitlements-service:8011"
        livenessProbe:
          httpGet:
            path: /health
            port: 8001
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8001
          initialDelaySeconds: 5
          periodSeconds: 5
```

### Docker Compose

```yaml
version: '3.8'
services:
  streaming-service:
    build:
      context: .
      dockerfile: service_streaming/Dockerfile
    ports:
      - "8001:8001"
    environment:
      - ACCESS_KAFKA_BOOTSTRAP=kafka:9092
      - ACCESS_AUTH_SERVICE_URL=http://auth-service:8010
      - ACCESS_ENTITLEMENTS_SERVICE_URL=http://entitlements-service:8011
    depends_on:
      - kafka
      - auth-service
      - entitlements-service
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8001/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

## Troubleshooting

### Common Issues

1. **WebSocket Connection Failures**
   - Check JWT token validity
   - Verify network connectivity
   - Check firewall settings

2. **SSE Connection Issues**
   - Verify HTTP headers
   - Check browser compatibility
   - Monitor connection limits

3. **Kafka Integration Problems**
   - Check Kafka broker connectivity
   - Verify topic existence
   - Monitor consumer lag

4. **Authentication Issues**
   - Validate JWT tokens
   - Check Auth Service connectivity
   - Verify user entitlements

### Debug Commands

```bash
# Check service health
curl http://localhost:8001/health

# Check connection statistics
curl http://localhost:8001/stats

# Test WebSocket connection
wscat -c ws://localhost:8001/ws/stream?token=test-token

# Test SSE connection
curl -N http://localhost:8001/sse/stream?token=test-token
```

### Log Analysis

```bash
# Filter for WebSocket events
docker logs streaming-service 2>&1 | grep "websocket"

# Filter for SSE events
docker logs streaming-service 2>&1 | grep "sse"

# Filter for Kafka events
docker logs streaming-service 2>&1 | grep "kafka"

# Filter for errors
docker logs streaming-service 2>&1 | grep ERROR
```

## Performance Tuning

### Optimization Tips

1. **Connection Management**
   - Implement connection pooling
   - Use appropriate connection limits
   - Monitor connection health

2. **Message Processing**
   - Batch message processing
   - Use async/await patterns
   - Implement message queuing

3. **Kafka Optimization**
   - Tune consumer settings
   - Use appropriate batch sizes
   - Monitor consumer lag

4. **Memory Management**
   - Monitor memory usage
   - Implement connection cleanup
   - Use appropriate buffer sizes

### Scaling Considerations

1. **Horizontal Scaling**
   - Deploy multiple instances
   - Use load balancer for distribution
   - Ensure stateless design

2. **Connection Distribution**
   - Distribute connections across instances
   - Use sticky sessions if needed
   - Monitor connection distribution

3. **Kafka Partitioning**
   - Use appropriate partition counts
   - Distribute consumers across partitions
   - Monitor partition distribution

## Security

### Security Features

1. **Authentication**
   - JWT token validation
   - Connection-level authentication
   - Multi-tenant support

2. **Authorization**
   - Topic-level permissions
   - Entitlement checks
   - Role-based access control

3. **Rate Limiting**
   - Connection rate limits
   - Message rate limits
   - Per-user limits

4. **Input Validation**
   - Message validation
   - Topic name validation
   - Filter validation

### Security Best Practices

1. **Token Management**
   - Use short-lived tokens
   - Implement token refresh
   - Secure token transmission

2. **Network Security**
   - Use WSS in production
   - Implement network policies
   - Use secure communication

3. **Monitoring**
   - Monitor security events
   - Implement alerting
   - Regular security audits

## Contributing

### Development Guidelines

1. **Code Style**
   - Follow PEP 8
   - Use type hints
   - Write comprehensive tests

2. **Testing**
   - Write unit tests
   - Include integration tests
   - Maintain test coverage

3. **Documentation**
   - Update API documentation
   - Include code comments
   - Update README files

### Pull Request Process

1. **Create Feature Branch**
   ```bash
   git checkout -b feature/new-feature
   ```

2. **Make Changes**
   - Implement feature
   - Add tests
   - Update documentation

3. **Submit Pull Request**
   - Include description
   - Reference issues
   - Request review

## License

This project is licensed under the MIT License - see the LICENSE file for details.
