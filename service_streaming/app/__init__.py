"""
Streaming Service package.

Provides WebSocket/SSE endpoints and Kafka integration to deliver
real-time updates to clients. Key modules include:

- app.main: FastAPI app and protocol endpoints
- app.ws: WebSocket connection + message handling
- app.sse: Server-Sent Events streaming
- app.kafka: Kafka producer/consumer utilities
- app.auth: Lightweight client to the Auth service
- app.subscriptions: Subscription management per connection
"""
