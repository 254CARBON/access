# Access Layer Performance Harness

Lightweight k6 scenarios exercise the public gateway and streaming services to
enforce latency targets captured in the service manifests.

## Scenarios

- `k6/gateway_latency_smoke.js` – Executes representative program metrics reads
  against the gateway and enforces a 150 ms p95 budget.
- `k6/streaming_latency_smoke.js` – Checks streaming service control-plane
  endpoints and enforces a 250 ms p95 budget.

## Running locally

```bash
# Gateway (override env vars as needed)
k6 run access/performance/k6/gateway_latency_smoke.js

# Streaming
STREAMING_BASE_URL=http://localhost:8001 \
  k6 run access/performance/k6/streaming_latency_smoke.js
```

Both scripts honour `K6_VUS` and `K6_DURATION` for quick scale adjustments.
