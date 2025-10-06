# Streaming Protocols Documentation

This document describes the WebSocket and Server-Sent Events (SSE) protocols used by the 254Carbon Access Layer Streaming Service.

## Table of Contents

1. [WebSocket Protocol](#websocket-protocol)
2. [Server-Sent Events (SSE) Protocol](#server-sent-events-sse-protocol)
3. [Authentication](#authentication)
4. [Message Formats](#message-formats)
5. [Error Handling](#error-handling)
6. [Rate Limiting](#rate-limiting)
7. [Examples](#examples)

## WebSocket Protocol

### Connection

**Endpoint:** `ws://localhost:8001/ws/stream`

**Authentication:** JWT token passed as query parameter

```javascript
const ws = new WebSocket('ws://localhost:8001/ws/stream?token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...');
```

### Connection Lifecycle

1. **Connection Establishment**
   - Client connects to WebSocket endpoint with JWT token
   - Server validates token and establishes connection
   - Server sends connection confirmation message

2. **Subscription Management**
   - Client sends subscription requests for topics
   - Server validates entitlements and subscribes client
   - Server sends subscription confirmation

3. **Message Flow**
   - Server broadcasts messages to subscribed clients
   - Client can send control messages (ping, unsubscribe, etc.)

4. **Connection Termination**
   - Client disconnects or server closes connection
   - Server cleans up subscriptions and resources

### Message Types

#### Client → Server Messages

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

**List Available Topics**
```json
{
  "action": "list_topics",
  "data": {}
}
```

**Get Connection Statistics**
```json
{
  "action": "get_stats",
  "data": {}
}
```

#### Server → Client Messages

**Connection Established**
```json
{
  "type": "connection_established",
  "connection_id": "conn-12345",
  "user_id": "user-123",
  "tenant_id": "tenant-1"
}
```

**Subscription Confirmation**
```json
{
  "type": "subscription_confirmed",
  "topics": ["pricing.updates", "curve.changes"],
  "filters": {
    "commodity": "oil",
    "region": "north_sea"
  }
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

**Pong Response**
```json
{
  "type": "pong",
  "timestamp": 1705312200000
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

## Server-Sent Events (SSE) Protocol

### Connection

**Endpoint:** `http://localhost:8001/sse/stream`

**Authentication:** JWT token passed as query parameter

```javascript
const eventSource = new EventSource('http://localhost:8001/sse/stream?token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...');
```

### Subscription Management

**Endpoint:** `POST http://localhost:8001/sse/subscribe`

**Parameters:**
- `connection_id`: SSE connection ID
- `topic`: Topic to subscribe to
- `filters`: Optional filters (JSON string)

```bash
curl -X POST "http://localhost:8001/sse/subscribe" \
  -d "connection_id=conn-12345&topic=pricing.updates&filters=%7B%22commodity%22%3A%22oil%22%7D"
```

### SSE Message Format

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

## Authentication

Both WebSocket and SSE connections require JWT token authentication.

### Token Requirements

- **Format:** JWT (JSON Web Token)
- **Algorithm:** RS256 or HS256
- **Claims:** Must include `user_id`, `tenant_id`, and `roles`
- **Expiration:** Tokens should have reasonable expiration times

### Token Validation

1. Server validates token signature using JWKS endpoint
2. Server extracts user information from token claims
3. Server checks user entitlements for requested topics
4. Server establishes connection if validation passes

### Example Token Claims

```json
{
  "sub": "user-123",
  "tenant_id": "tenant-1",
  "roles": ["user", "analyst"],
  "email": "user@example.com",
  "iat": 1705312200,
  "exp": 1705315800
}
```

## Message Formats

### Topic Naming Convention

Topics follow a hierarchical naming pattern:

- `pricing.updates` - Real-time pricing updates
- `curve.changes` - Yield curve changes
- `instruments.new` - New instrument additions
- `alerts.system` - System alerts
- `alerts.user` - User-specific alerts

### Filter Format

Filters are JSON objects that specify which messages to receive:

```json
{
  "commodity": "oil",
  "region": "north_sea",
  "instrument_type": "futures",
  "price_range": {
    "min": 70.0,
    "max": 80.0
  }
}
```

### Data Message Structure

All data messages follow this structure:

```json
{
  "topic": "string",
  "data": "object",
  "timestamp": "number",
  "partition": "number",
  "offset": "number"
}
```

## Error Handling

### Error Codes

- `AUTHENTICATION_FAILED` - Invalid or expired token
- `SUBSCRIPTION_DENIED` - Insufficient permissions for topic
- `INVALID_TOPIC` - Topic does not exist
- `RATE_LIMIT_EXCEEDED` - Too many requests
- `INTERNAL_ERROR` - Server error

### Error Response Format

```json
{
  "type": "error",
  "error": "ERROR_CODE",
  "message": "Human readable error message",
  "details": {
    "additional": "context"
  }
}
```

## Rate Limiting

### WebSocket Connections

- **Limit:** 30 connections per minute per IP
- **Burst:** Allow up to 50 connections in 1 minute
- **Reset:** Rate limit resets every minute

### Message Rate

- **Limit:** 1000 messages per minute per connection
- **Burst:** Allow up to 100 messages in 10 seconds
- **Reset:** Rate limit resets every minute

### SSE Connections

- **Limit:** 20 connections per minute per IP
- **Burst:** Allow up to 30 connections in 1 minute
- **Reset:** Rate limit resets every minute

## Examples

### JavaScript WebSocket Client

```javascript
class StreamingClient {
  constructor(token) {
    this.token = token;
    this.ws = null;
    this.connectionId = null;
  }

  connect() {
    this.ws = new WebSocket(`ws://localhost:8001/ws/stream?token=${this.token}`);
    
    this.ws.onopen = () => {
      console.log('WebSocket connected');
    };

    this.ws.onmessage = (event) => {
      const message = JSON.parse(event.data);
      this.handleMessage(message);
    };

    this.ws.onclose = () => {
      console.log('WebSocket disconnected');
    };

    this.ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };
  }

  handleMessage(message) {
    switch (message.type) {
      case 'connection_established':
        this.connectionId = message.connection_id;
        console.log('Connection established:', message);
        break;
      case 'data':
        this.handleDataMessage(message);
        break;
      case 'error':
        console.error('Server error:', message);
        break;
      default:
        console.log('Unknown message type:', message.type);
    }
  }

  handleDataMessage(message) {
    console.log('Data received:', message);
    // Process the data message
  }

  subscribe(topics, filters = {}) {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      throw new Error('WebSocket not connected');
    }

    this.ws.send(JSON.stringify({
      action: 'subscribe',
      data: { topics, filters }
    }));
  }

  unsubscribe(topics) {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      throw new Error('WebSocket not connected');
    }

    this.ws.send(JSON.stringify({
      action: 'unsubscribe',
      data: { topics }
    }));
  }

  ping() {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      throw new Error('WebSocket not connected');
    }

    this.ws.send(JSON.stringify({
      action: 'ping',
      data: {}
    }));
  }

  disconnect() {
    if (this.ws) {
      this.ws.close();
    }
  }
}

// Usage
const client = new StreamingClient('your-jwt-token');
client.connect();

// Wait for connection, then subscribe
setTimeout(() => {
  client.subscribe(['pricing.updates'], { commodity: 'oil' });
}, 1000);
```

### JavaScript SSE Client

```javascript
class SSEClient {
  constructor(token) {
    this.token = token;
    this.eventSource = null;
    this.connectionId = null;
  }

  connect() {
    this.eventSource = new EventSource(`http://localhost:8001/sse/stream?token=${this.token}`);
    
    this.eventSource.onopen = () => {
      console.log('SSE connected');
    };

    this.eventSource.onmessage = (event) => {
      const message = JSON.parse(event.data);
      this.handleMessage(message);
    };

    this.eventSource.addEventListener('connection_established', (event) => {
      const message = JSON.parse(event.data);
      this.connectionId = message.connection_id;
      console.log('Connection established:', message);
    });

    this.eventSource.addEventListener('data', (event) => {
      const message = JSON.parse(event.data);
      this.handleDataMessage(message);
    });

    this.eventSource.addEventListener('error', (event) => {
      const message = JSON.parse(event.data);
      console.error('Server error:', message);
    });

    this.eventSource.onerror = (error) => {
      console.error('SSE error:', error);
    };
  }

  handleMessage(message) {
    console.log('Message received:', message);
  }

  handleDataMessage(message) {
    console.log('Data received:', message);
    // Process the data message
  }

  async subscribe(topic, filters = {}) {
    if (!this.connectionId) {
      throw new Error('SSE not connected');
    }

    const params = new URLSearchParams({
      connection_id: this.connectionId,
      topic: topic
    });

    if (Object.keys(filters).length > 0) {
      params.append('filters', JSON.stringify(filters));
    }

    const response = await fetch(`http://localhost:8001/sse/subscribe?${params}`, {
      method: 'POST'
    });

    if (!response.ok) {
      throw new Error(`Subscription failed: ${response.statusText}`);
    }

    const result = await response.json();
    console.log('Subscription result:', result);
  }

  disconnect() {
    if (this.eventSource) {
      this.eventSource.close();
    }
  }
}

// Usage
const sseClient = new SSEClient('your-jwt-token');
sseClient.connect();

// Wait for connection, then subscribe
setTimeout(async () => {
  try {
    await sseClient.subscribe('pricing.updates', { commodity: 'oil' });
  } catch (error) {
    console.error('Subscription failed:', error);
  }
}, 1000);
```

### Python WebSocket Client

```python
import asyncio
import websockets
import json
from typing import Dict, Any, List

class StreamingClient:
    def __init__(self, token: str):
        self.token = token
        self.websocket = None
        self.connection_id = None

    async def connect(self):
        uri = f"ws://localhost:8001/ws/stream?token={self.token}"
        self.websocket = await websockets.connect(uri)
        print("WebSocket connected")

    async def handle_message(self, message: Dict[str, Any]):
        message_type = message.get("type")
        
        if message_type == "connection_established":
            self.connection_id = message["connection_id"]
            print(f"Connection established: {message}")
        elif message_type == "data":
            await self.handle_data_message(message)
        elif message_type == "error":
            print(f"Server error: {message}")
        else:
            print(f"Unknown message type: {message_type}")

    async def handle_data_message(self, message: Dict[str, Any]):
        print(f"Data received: {message}")
        # Process the data message

    async def subscribe(self, topics: List[str], filters: Dict[str, Any] = None):
        if not self.websocket:
            raise Exception("WebSocket not connected")

        message = {
            "action": "subscribe",
            "data": {
                "topics": topics,
                "filters": filters or {}
            }
        }
        
        await self.websocket.send(json.dumps(message))

    async def unsubscribe(self, topics: List[str]):
        if not self.websocket:
            raise Exception("WebSocket not connected")

        message = {
            "action": "unsubscribe",
            "data": {
                "topics": topics
            }
        }
        
        await self.websocket.send(json.dumps(message))

    async def ping(self):
        if not self.websocket:
            raise Exception("WebSocket not connected")

        message = {
            "action": "ping",
            "data": {}
        }
        
        await self.websocket.send(json.dumps(message))

    async def listen(self):
        async for message in self.websocket:
            data = json.loads(message)
            await self.handle_message(data)

    async def disconnect(self):
        if self.websocket:
            await self.websocket.close()

# Usage
async def main():
    client = StreamingClient("your-jwt-token")
    await client.connect()
    
    # Wait for connection, then subscribe
    await asyncio.sleep(1)
    await client.subscribe(["pricing.updates"], {"commodity": "oil"})
    
    # Listen for messages
    await client.listen()

if __name__ == "__main__":
    asyncio.run(main())
```

### Python SSE Client

```python
import asyncio
import aiohttp
import json
from typing import Dict, Any

class SSEClient:
    def __init__(self, token: str):
        self.token = token
        self.session = None
        self.connection_id = None

    async def connect(self):
        self.session = aiohttp.ClientSession()
        url = f"http://localhost:8001/sse/stream?token={self.token}"
        
        async with self.session.get(url) as response:
            async for line in response.content:
                line = line.decode('utf-8').strip()
                
                if line.startswith('event: '):
                    event_type = line[7:]
                elif line.startswith('data: '):
                    data = line[6:]
                    await self.handle_message(event_type, json.loads(data))

    async def handle_message(self, event_type: str, message: Dict[str, Any]):
        if event_type == "connection_established":
            self.connection_id = message["connection_id"]
            print(f"Connection established: {message}")
        elif event_type == "data":
            await self.handle_data_message(message)
        elif event_type == "error":
            print(f"Server error: {message}")

    async def handle_data_message(self, message: Dict[str, Any]):
        print(f"Data received: {message}")
        # Process the data message

    async def subscribe(self, topic: str, filters: Dict[str, Any] = None):
        if not self.connection_id:
            raise Exception("SSE not connected")

        params = {
            "connection_id": self.connection_id,
            "topic": topic
        }
        
        if filters:
            params["filters"] = json.dumps(filters)

        url = "http://localhost:8001/sse/subscribe"
        async with self.session.post(url, params=params) as response:
            if response.status != 200:
                raise Exception(f"Subscription failed: {response.status}")
            
            result = await response.json()
            print(f"Subscription result: {result}")

    async def disconnect(self):
        if self.session:
            await self.session.close()

# Usage
async def main():
    client = SSEClient("your-jwt-token")
    
    # Start connection in background
    connect_task = asyncio.create_task(client.connect())
    
    # Wait for connection
    await asyncio.sleep(2)
    
    try:
        await client.subscribe("pricing.updates", {"commodity": "oil"})
    except Exception as e:
        print(f"Subscription failed: {e}")
    
    # Keep running
    await connect_task

if __name__ == "__main__":
    asyncio.run(main())
```

## Best Practices

### Connection Management

1. **Implement reconnection logic** for both WebSocket and SSE clients
2. **Handle connection drops gracefully** with exponential backoff
3. **Validate connection state** before sending messages
4. **Clean up resources** when disconnecting

### Message Handling

1. **Validate message format** before processing
2. **Handle errors gracefully** with proper logging
3. **Implement message queuing** for offline scenarios
4. **Use message IDs** for deduplication if needed

### Performance Optimization

1. **Limit subscription scope** to only required topics
2. **Use filters effectively** to reduce message volume
3. **Implement message batching** for high-frequency updates
4. **Monitor connection health** with ping/pong messages

### Security Considerations

1. **Validate JWT tokens** on the client side
2. **Implement token refresh** for long-lived connections
3. **Use secure WebSocket connections** (WSS) in production
4. **Implement rate limiting** on the client side
5. **Log security events** for monitoring

## Troubleshooting

### Common Issues

1. **Connection refused**: Check if the streaming service is running
2. **Authentication failed**: Verify JWT token is valid and not expired
3. **Subscription denied**: Check user entitlements for the requested topics
4. **Message not received**: Verify subscription was successful and topic is active
5. **Connection dropped**: Implement reconnection logic with exponential backoff

### Debugging Tips

1. **Enable debug logging** in the streaming service
2. **Monitor WebSocket connection state** in browser dev tools
3. **Check server logs** for error messages
4. **Use network tab** to inspect SSE events
5. **Test with curl** for basic connectivity

### Performance Monitoring

1. **Monitor connection count** per service instance
2. **Track message throughput** and latency
3. **Monitor memory usage** for connection management
4. **Set up alerts** for connection failures
5. **Monitor rate limiting** violations
