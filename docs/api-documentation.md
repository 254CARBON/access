# API Documentation

This document provides comprehensive documentation for all APIs in the 254Carbon Access Layer.

## Table of Contents

- [Gateway Service API](#gateway-service-api)
- [Streaming Service API](#streaming-service-api)
- [Auth Service API](#auth-service-api)
- [Entitlements Service API](#entitlements-service-api)
- [Metrics Service API](#metrics-service-api)
- [Authentication](#authentication)
- [Error Handling](#error-handling)
- [Rate Limiting](#rate-limiting)
- [Examples](#examples)

## Gateway Service API

The Gateway Service acts as the main entry point for all client requests, providing routing, authentication, authorization, rate limiting, and caching.

### Base URL
```
http://localhost:8000
```

### Authentication
All endpoints require authentication unless otherwise specified. Use JWT tokens or API keys.

### Endpoints

#### Health Check
```http
GET /health
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-01T00:00:00Z",
  "version": "1.0.0"
}
```

#### API Information
```http
GET /api/v1/info
```

**Response:**
```json
{
  "name": "254Carbon Access Layer Gateway",
  "version": "1.0.0",
  "description": "API Gateway for 254Carbon Access Layer",
  "endpoints": [
    {
      "path": "/api/v1/auth/verify",
      "method": "POST",
      "description": "Verify JWT token"
    },
    {
      "path": "/api/v1/entitlements/check",
      "method": "POST",
      "description": "Check user entitlements"
    }
  ]
}
```

#### Token Verification
```http
POST /api/v1/auth/verify
```

**Request Body:**
```json
{
  "token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response:**
```json
{
  "valid": true,
  "user_id": "user123",
  "expires_at": "2024-01-01T01:00:00Z",
  "permissions": ["read:pricing", "write:orders"]
}
```

#### Entitlement Check
```http
POST /api/v1/entitlements/check
```

**Request Body:**
```json
{
  "resource": "pricing",
  "action": "read",
  "user_id": "user123"
}
```

**Response:**
```json
{
  "allowed": true,
  "reason": "User has read access to pricing data",
  "conditions": {
    "market": "US",
    "time_range": "business_hours"
  }
}
```

#### Rate Limit Status
```http
GET /api/v1/rate-limit/status
```

**Response:**
```json
{
  "limit": 1000,
  "remaining": 950,
  "reset_time": "2024-01-01T01:00:00Z",
  "window": "1h"
}
```

## Streaming Service API

The Streaming Service provides real-time data streaming via WebSocket and Server-Sent Events (SSE).

### Base URL
```
http://localhost:8001
```

### WebSocket Endpoint
```
ws://localhost:8001/ws
```

### WebSocket Protocol

#### Connection
```javascript
const ws = new WebSocket('ws://localhost:8001/ws');
```

#### Authentication
```json
{
  "type": "auth",
  "token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

#### Subscription
```json
{
  "type": "subscribe",
  "topic": "254carbon.pricing.curve.updates.v1",
  "filters": {
    "market": "US",
    "instrument_type": "bond"
  }
}
```

#### Unsubscription
```json
{
  "type": "unsubscribe",
  "topic": "254carbon.pricing.curve.updates.v1"
}
```

#### Message Format
```json
{
  "type": "data",
  "topic": "254carbon.pricing.curve.updates.v1",
  "data": {
    "instrument_id": "US-TREASURY-10Y",
    "price": 98.5,
    "timestamp": "2024-01-01T00:00:00Z"
  },
  "sequence": 12345
}
```

### Server-Sent Events (SSE)

#### SSE Endpoint
```http
GET /sse?topic=254carbon.pricing.curve.updates.v1
```

#### SSE Response
```
data: {"type": "data", "topic": "254carbon.pricing.curve.updates.v1", "data": {...}}

data: {"type": "heartbeat", "timestamp": "2024-01-01T00:00:00Z"}

```

### Available Topics

- `254carbon.pricing.curve.updates.v1` - Pricing curve updates
- `254carbon.pricing.instrument.updates.v1` - Instrument price updates
- `254carbon.market.data.v1` - General market data
- `254carbon.metrics.streaming.v1` - Streaming metrics
- `254carbon.streaming.connection.events.v1` - Connection events
- `254carbon.entitlements.rule.changes.v1` - Entitlement rule changes
- `254carbon.auth.token.events.v1` - Authentication events

## Auth Service API

The Auth Service handles JWT token verification and management.

### Base URL
```
http://localhost:8010
```

### Endpoints

#### Health Check
```http
GET /health
```

#### Token Verification
```http
POST /api/v1/tokens/verify
```

**Request Body:**
```json
{
  "token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response:**
```json
{
  "valid": true,
  "payload": {
    "sub": "user123",
    "exp": 1640995200,
    "iat": 1640991600,
    "permissions": ["read:pricing", "write:orders"]
  }
}
```

#### JWKS Endpoint
```http
GET /api/v1/jwks
```

**Response:**
```json
{
  "keys": [
    {
      "kty": "RSA",
      "kid": "key1",
      "use": "sig",
      "n": "0vx7agoebGcQSuuPiLJXZptN9nndrQmbP...",
      "e": "AQAB"
    }
  ]
}
```

## Entitlements Service API

The Entitlements Service manages fine-grained access control using a rule engine.

### Base URL
```
http://localhost:8011
```

### Endpoints

#### Health Check
```http
GET /health
```

#### Entitlement Check
```http
POST /api/v1/entitlements/check
```

**Request Body:**
```json
{
  "user_id": "user123",
  "resource": "pricing",
  "action": "read",
  "context": {
    "market": "US",
    "time": "2024-01-01T10:00:00Z"
  }
}
```

**Response:**
```json
{
  "allowed": true,
  "reason": "User has read access to pricing data",
  "rule_id": "rule_001",
  "conditions": {
    "market": "US",
    "time_range": "business_hours"
  }
}
```

#### Rule Management
```http
POST /api/v1/rules
```

**Request Body:**
```json
{
  "name": "pricing_read_rule",
  "description": "Allow read access to pricing data",
  "conditions": {
    "user_role": "trader",
    "market": "US"
  },
  "permissions": ["read:pricing"]
}
```

**Response:**
```json
{
  "rule_id": "rule_001",
  "name": "pricing_read_rule",
  "status": "active",
  "created_at": "2024-01-01T00:00:00Z"
}
```

#### List Rules
```http
GET /api/v1/rules
```

**Response:**
```json
{
  "rules": [
    {
      "rule_id": "rule_001",
      "name": "pricing_read_rule",
      "status": "active",
      "created_at": "2024-01-01T00:00:00Z"
    }
  ],
  "total": 1
}
```

## Metrics Service API

The Metrics Service collects, aggregates, and exposes custom metrics.

### Base URL
```
http://localhost:8012
```

### Endpoints

#### Health Check
```http
GET /health
```

#### Prometheus Metrics
```http
GET /metrics
```

**Response:**
```
# HELP gateway_requests_total Total number of requests
# TYPE gateway_requests_total counter
gateway_requests_total{method="GET",endpoint="/health"} 100

# HELP gateway_request_duration_seconds Request duration in seconds
# TYPE gateway_request_duration_seconds histogram
gateway_request_duration_seconds_bucket{le="0.1"} 50
gateway_request_duration_seconds_bucket{le="0.5"} 80
gateway_request_duration_seconds_bucket{le="1.0"} 95
gateway_request_duration_seconds_bucket{le="+Inf"} 100
```

#### Custom Metrics
```http
POST /api/v1/metrics
```

**Request Body:**
```json
{
  "name": "custom_business_metric",
  "value": 42,
  "labels": {
    "market": "US",
    "instrument": "BOND"
  },
  "timestamp": "2024-01-01T00:00:00Z"
}
```

**Response:**
```json
{
  "status": "success",
  "metric_id": "metric_001"
}
```

## Authentication

### JWT Tokens

The system uses JWT tokens for authentication. Tokens are issued by Keycloak and verified by the Auth Service.

#### Token Structure
```json
{
  "header": {
    "alg": "RS256",
    "typ": "JWT",
    "kid": "key1"
  },
  "payload": {
    "sub": "user123",
    "exp": 1640995200,
    "iat": 1640991600,
    "permissions": ["read:pricing", "write:orders"]
  }
}
```

#### Token Usage
```bash
# Include token in Authorization header
curl -H "Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9..." \
  http://localhost:8000/api/v1/entitlements/check
```

### API Keys

For service-to-service communication, API keys can be used:

```bash
# Include API key in X-API-Key header
curl -H "X-API-Key: your-api-key" \
  http://localhost:8000/api/v1/auth/verify
```

## Error Handling

### Error Response Format
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid request parameters",
    "details": {
      "field": "token",
      "reason": "Token is required"
    },
    "timestamp": "2024-01-01T00:00:00Z",
    "request_id": "req_123"
  }
}
```

### HTTP Status Codes

- `200 OK` - Request successful
- `201 Created` - Resource created
- `400 Bad Request` - Invalid request
- `401 Unauthorized` - Authentication required
- `403 Forbidden` - Access denied
- `404 Not Found` - Resource not found
- `429 Too Many Requests` - Rate limit exceeded
- `500 Internal Server Error` - Server error
- `502 Bad Gateway` - Upstream service error
- `503 Service Unavailable` - Service temporarily unavailable

### Error Codes

- `VALIDATION_ERROR` - Request validation failed
- `AUTHENTICATION_ERROR` - Authentication failed
- `AUTHORIZATION_ERROR` - Authorization failed
- `RATE_LIMIT_EXCEEDED` - Rate limit exceeded
- `SERVICE_UNAVAILABLE` - Service unavailable
- `INTERNAL_ERROR` - Internal server error

## Rate Limiting

### Rate Limit Headers
```http
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 950
X-RateLimit-Reset: 1640995200
X-RateLimit-Window: 3600
```

### Rate Limit Types

1. **Public Endpoints**: 1000 requests/hour
2. **Authenticated Endpoints**: 5000 requests/hour
3. **Heavy Operations**: 100 requests/hour
4. **Admin Operations**: 10000 requests/hour

### Rate Limit Exceeded Response
```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Rate limit exceeded",
    "details": {
      "limit": 1000,
      "remaining": 0,
      "reset_time": "2024-01-01T01:00:00Z"
    }
  }
}
```

## Examples

### Complete Authentication Flow

```bash
# 1. Get JWT token from Keycloak
TOKEN=$(curl -X POST http://localhost:8080/realms/254carbon/protocol/openid-connect/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=client_credentials&client_id=access-layer&client_secret=your-secret" | jq -r '.access_token')

# 2. Verify token through Gateway
curl -X POST http://localhost:8000/api/v1/auth/verify \
  -H "Content-Type: application/json" \
  -d "{\"token\": \"$TOKEN\"}"

# 3. Check entitlements
curl -X POST http://localhost:8000/api/v1/entitlements/check \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"resource": "pricing", "action": "read", "user_id": "user123"}'
```

### WebSocket Connection Example

```javascript
const ws = new WebSocket('ws://localhost:8001/ws');

ws.onopen = function() {
  // Authenticate
  ws.send(JSON.stringify({
    type: 'auth',
    token: 'your-jwt-token'
  }));
  
  // Subscribe to topic
  ws.send(JSON.stringify({
    type: 'subscribe',
    topic: '254carbon.pricing.curve.updates.v1'
  }));
};

ws.onmessage = function(event) {
  const data = JSON.parse(event.data);
  console.log('Received:', data);
};

ws.onclose = function() {
  console.log('Connection closed');
};
```

### SSE Connection Example

```javascript
const eventSource = new EventSource('http://localhost:8001/sse?topic=254carbon.pricing.curve.updates.v1');

eventSource.onmessage = function(event) {
  const data = JSON.parse(event.data);
  console.log('Received:', data);
};

eventSource.onerror = function(event) {
  console.error('SSE error:', event);
};
```

### Python Client Example

```python
import requests
import websocket
import json

# API Client
class AccessLayerClient:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.session = requests.Session()
    
    def verify_token(self, token):
        response = self.session.post(
            f"{self.base_url}/api/v1/auth/verify",
            json={"token": token}
        )
        return response.json()
    
    def check_entitlements(self, token, resource, action, user_id):
        response = self.session.post(
            f"{self.base_url}/api/v1/entitlements/check",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "resource": resource,
                "action": action,
                "user_id": user_id
            }
        )
        return response.json()

# WebSocket Client
class StreamingClient:
    def __init__(self, ws_url="ws://localhost:8001/ws"):
        self.ws_url = ws_url
        self.ws = None
    
    def connect(self, token):
        self.ws = websocket.WebSocket()
        self.ws.connect(self.ws_url)
        
        # Authenticate
        self.ws.send(json.dumps({
            "type": "auth",
            "token": token
        }))
    
    def subscribe(self, topic):
        self.ws.send(json.dumps({
            "type": "subscribe",
            "topic": topic
        }))
    
    def listen(self):
        while True:
            data = self.ws.recv()
            message = json.loads(data)
            print(f"Received: {message}")
```

## SDKs and Libraries

### JavaScript/Node.js
```bash
npm install @254carbon/access-layer-sdk
```

### Python
```bash
pip install 254carbon-access-layer-sdk
```

### Go
```bash
go get github.com/254carbon/access-layer-sdk
```

## Support

For API support and questions:

- **Documentation**: [API Documentation](https://docs.254carbon.com/api)
- **Support Email**: api-support@254carbon.com
- **GitHub Issues**: [GitHub Repository](https://github.com/254carbon/access-layer)
- **Slack**: #api-support channel
