
# 254Carbon Access Layer (`254carbon-access`)

> Unified repository for the platform “edge” and cross-cutting access services:
> - API Gateway (REST)
> - Streaming Service (WebSocket + SSE)
> - Auth Service (JWT / Keycloak integration)
> - Entitlements Service (authorization & soft multi-tenancy)
> - Metrics Service (centralized metrics ingestion & export)

This repo is intentionally consolidated (early-phase) to minimize overhead for a single developer + AI coding agents while preserving clear **service boundaries**. Each service is independently deployable and versioned through its own manifest.

---

## Table of Contents
1. Philosophy & Scope  
2. Service Overview  
3. Repository Structure  
4. Service Manifests  
5. Architecture & Flows  
6. Technology Stack  
7. API Conventions & Versioning  
8. Rate Limiting Strategy  
9. Configuration & Environment Variables  
10. Local Development (Multi-Arch)  
11. Build & Multi-Arch Images  
12. Running Locally (Individual & Combined)  
13. Observability (Metrics, Traces, Logs)  
14. Security & Authorization Model  
15. Caching Strategy  
16. Performance Targets & SLOs (Draft)  
17. Dependency Graph  
18. Release & Deployment Workflow  
19. AI Agent Integration  
20. Troubleshooting Guide  
21. Testing Strategy  
22. Roadmap & Future Splits  
23. Contribution Guidelines (Repo Specific)  
24. Changelog Template  
25. License / Ownership  

---

## 1. Philosophy & Scope

The access layer is the “front door” of the 254Carbon platform. Primary goals:
- Efficient, secure exposure of REST & streaming interfaces.
- Separation of concerns: auth vs entitlements vs data routing vs metrics.
- Extensible for future protocols (GraphQL, gRPC, Graph streaming).
- Stable contract adherence to specs from `254carbon-specs`.
- Low latency and high readiness for scaling and future polyglot evolution.

Non-goals:
- Business analytics logic (belongs to analytics or data-processing repos).
- Ingestion or normalization (belongs to `254carbon-ingestion` / `data-processing`).
- Model inference (belongs to `254carbon-ml`).

---

## 2. Service Overview

| Service | Purpose | Type | Ports (default) | External Exposure | Scaling |
|---------|---------|------|-----------------|------------------|---------|
| API Gateway | REST APIs, request routing, rate limiting, caching | Stateless | 8000 | Yes (Ingress) | HPA (CPU/Latency) |
| Streaming Service | WebSocket + SSE real-time distribution | Stateful (session mgmt) | 8001 | Yes (Ingress) | HPA (connections + CPU) |
| Auth Service | JWT verification via Keycloak (JWKS caching) | Internal | 8010 | No | Small horizontal |
| Entitlements Service | Fine-grained access checks (tenant, product, instrument) | Internal | 8011 | No | Small horizontal |
| Metrics Service | Ingest custom metrics & expose /metrics for Prometheus | Internal | 8012 | Optional (/metrics) | Tiny horizontal |

All services provide:
- `/health` (liveness & readiness)
- Structured JSON logs with trace correlation
- Prometheus-compatible internal metrics (directly or via Metrics Service)

---

## 3. Repository Structure

```
/
  service-gateway/
    app/
      routes/
      domain/
      adapters/
      caching/
      config/
    tests/
    service-manifest.yaml
    openapi/ (synced from specs)
    Dockerfile
  service-streaming/
    app/
      ws/
      sse/
      subscriptions/
      kafka/
      auth/
    tests/
    service-manifest.yaml
    Dockerfile
  service-auth/
    app/
      jwks/
      validation/
    tests/
    service-manifest.yaml
    Dockerfile
  service-entitlements/
    app/
      rules/
      cache/
      persistence/
    tests/
    service-manifest.yaml
    Dockerfile
  service-metrics/
    app/
      ingestion/
      exporters/
    tests/
    service-manifest.yaml
    Dockerfile
  shared/                 (Very thin: only constants/config structs; heavy reuse → shared-libs repo)
  ci/
    workflows/            (GitHub Actions templates)
  scripts/
    dev_cluster.sh
    smoke.sh
    codegen_sync.py
  specs.lock.json         (Pinned contract versions)
  .agent/
    context.yaml
  Makefile
  README.md
  CHANGELOG.md
```

---

## 4. Service Manifests

Each `service-manifest.yaml` defines machine-readable metadata:

```yaml
service_name: gateway
domain: access
runtime: python
language_version: "3.12"
api_contracts:
  - gateway-core@1.0.0
events_in:
  - pricing.curve.updates.v1
events_out:
  - metrics.request.count.v1
dependencies:
  internal: [auth, entitlements, metrics]
  external: [redis, clickhouse]
maturity: stable
sla:
  p95_latency_ms: 150
  availability: "99.0%"
owner: platform
```

CI aggregates these to publish an index to `254carbon-meta`.

---

## 5. Architecture & Flows

### Authentication Flow
1. Client → Gateway with `Authorization: Bearer <JWT>`
2. Gateway → Auth Service `/auth/verify`
3. Auth Service → Keycloak JWKS (cached)
4. Auth Service → Gateway (claims, sub, tenant_id)
5. Gateway → Entitlements (resource check) if needed
6. Gateway → Upstream domain service or data source
7. Response → Client

### Streaming Subscription Flow
1. Client opens WS: `/ws/stream?token=<JWT>`
2. Streaming Service → Auth Service `/auth/verify-ws`
3. Streaming Service → Entitlements for subscription scope
4. Subscribed topics mapped → internal Kafka consumer(s)
5. Message fanout → client channels
6. Metrics posted periodically to Metrics Service

### Metrics Ingestion Flow
1. Gateway/Streaming → Metrics Service (`POST /metrics/track`)
2. Metrics Service aggregates in-memory or lightweight store
3. Prometheus scrapes `/metrics`
4. Alerting system consumes aggregated time series

### Entitlements Check
```
Gateway → Entitlements: { user_id, action, resource, tenant_id }
Entitlements → Postgres/Cache
Return: allow/deny + TTL
```

---

## 6. Technology Stack

| Layer | Tool |
|-------|------|
| Language | Python 3.12 (FastAPI / uvicorn) |
| Auth | Keycloak (OIDC) |
| Caching | Redis (adaptive TTL) |
| Data Access (read) | ClickHouse (historical), Postgres (metadata) |
| Messaging | Kafka (event consumption for streaming) |
| Metrics | Prometheus + Metrics Service |
| Tracing | OpenTelemetry SDK + Collector (external repo) |
| Container | Multi-arch (amd64 + arm64) |
| Deployment | Kubernetes (local cluster: 1 x86 + 2 ARM nodes) |

---

## 7. API Conventions & Versioning

- REST base path: `/api/v1/...`
- Version increments follow SemVer rules defined in `254carbon-specs`:
  - Additive: MINOR
  - Breaking: MAJOR (new `/api/v2/...` base when needed)
- Error model (uniform):
```json
{
  "trace_id": "aaa-bbb-ccc",
  "code": "ENTITLEMENT_DENIED",
  "message": "User lacks access to curve X",
  "details": {}
}
```
- Pagination: `?page=1&limit=50` + `X-Total-Count` header (or token-based for high-volume endpoints later)
- Filtering: `?filters=field:value,field2:value2`

---

## 8. Rate Limiting Strategy (Draft)

| Tier | Policy | Scope | Example Use |
|------|--------|-------|-------------|
| Public | 100 req/min/IP | Health & metadata | `/health` |
| Authenticated | 1000 req/min/user | Standard REST | `/api/v1/instruments` |
| Heavy | 10 req/min/user | Data intensive | `/api/v1/curves/recompute` |
| Cache Writes | 5 req/min/user | Admin warming | `/api/v1/cache/warm` |
| Streaming Connect | 30 conn/min/IP (burst) | WS handshakes | `/ws/stream` |

Enforced via token bucket + Redis counters in Gateway. Subject to change.

---

## 9. Configuration & Environment Variables

Common (prefix `ACCESS_`):

| Variable | Description | Example |
|----------|-------------|---------|
| ACCESS_ENV | environment name | local |
| ACCESS_LOG_LEVEL | log verbosity | info |
| ACCESS_JWKS_URL | Keycloak JWKS endpoint | http://keycloak:8080/... |
| ACCESS_REDIS_URL | Redis connection | redis://redis:6379/0 |
| ACCESS_CLICKHOUSE_URL | Analytical DB | http://clickhouse:8123 |
| ACCESS_POSTGRES_DSN | Metadata DB | postgres://... |
| ACCESS_KAFKA_BOOTSTRAP | Kafka brokers | kafka:9092 |
| ACCESS_METRICS_ENDPOINT | Metrics svc base | http://metrics-service:8012 |
| ACCESS_RATE_LIMITS_FILE | Override rate config | /config/rl.yaml |
| ACCESS_ENABLE_TRACING | Enable OTel exporter | true |
| ACCESS_OTEL_EXPORTER | OTel collector URL | http://otel-collector:4318 |
| ACCESS_TLS_ENABLED | (future) | false |

Per-service .env templates live under each service's `config/`.

---

## 10. Local Development (Multi-Arch)

Challenges:
- Mixed hardware: x86 Linux + ARM Mac
- Solution: Multi-arch images via `docker buildx`

Local modes:
1. Pure host run (venv + uvicorn) for rapid iteration.
2. Docker Compose (optional) bundling only access services.
3. Kubernetes (kind / k3d) for integration with other repos.

Requirements:
- Python 3.12
- Make
- Docker + buildx enabled
- Optional: Tilt or Skaffold for live reload

---

## 11. Build & Multi-Arch Images

Sample build command (global Make target):

```
make build SERVICE=gateway
make buildx-push SERVICE=gateway VERSION=1.0.0
```

Internally:
```
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -f service-gateway/Dockerfile \
  -t ghcr.io/254carbon/gateway:1.0.0 \
  --push .
```

---

## 12. Running Locally

### Single Service (Gateway)
```
cd service-gateway
python -m uvicorn app.main:app --reload --port 8000
```

### All Services (Host Mode)
```
make dev-all
```
(Uses a script to spawn each with its own terminal or tmux session.)

### Kubernetes (with dev helper)
```
./scripts/dev_cluster.sh
kubectl apply -f k8s/ (future: helm charts)
```

---

## 13. Observability

Metrics (Prometheus format):
- Gateway: HTTP request count, latency histogram, cache hit ratio
- Streaming: Active connections, fanout rate, delivery lag
- Auth: JWKS refresh latency, token validation counts
- Entitlements: Cache hit/miss, rule evaluation time
- Metrics Service: Ingestion queue depth, flush latency

Tracing:
- Trace IDs propagated via `traceparent`
- Inter-service calls use OTel instrumentation
- Kafka message headers carry trace context (Streaming path)

Logs:
- JSON lines:
```
{"ts":"2025-10-05T21:55:02Z","lvl":"INFO","service":"gateway","trace_id":"...","req_id":"...","msg":"GET /api/v1/instruments 200 42ms"}
```

---

## 14. Security & Authorization Model

| Layer | Responsibility |
|-------|---------------|
| Keycloak | Identity provider (realm, users, clients) |
| Auth Service | JWT signature verify, claims extraction, JWKS caching |
| Entitlements Service | Resource-level + tenant scoping decisions |
| Gateway | Enforces both auth & entitlement results |
| Streaming Service | Per-subscription entitlement revalidation on connect |

Soft Multi-Tenancy:
- `tenant_id` resolved from token claims
- Propagated in internal headers: `X-Tenant-ID`
- Used for row filtering in downstream queries (NOT implemented here)

Future Enhancements:
- mTLS between services
- OPA-based fine-grained policy evaluation

---

## 15. Caching Strategy

| Cache Type | Store | Use |
|------------|-------|-----|
| Auth JWKS | In-memory | 1h TTL refresh |
| Entitlement results | Redis | 30–120s adaptive TTL |
| Curve snapshot (hot endpoints) | Redis | 10–60s TTL |
| Instrument metadata | Local LRU + Redis | Frequent reads |
| Rate limit counters | Redis | Sliding window tokens |

Adaptive TTL (example):
- Shorter TTL on error bursts or low traffic
- Longer TTL when hit ratio stable & data freshness less critical

---

## 16. Performance Targets & SLOs (Draft)

| Metric | Target |
|--------|--------|
| Gateway P95 latency | < 150 ms |
| Gateway P99 latency | < 250 ms |
| Streaming delivery lag (Kafka→client P95) | < 250 ms |
| Auth verification P95 | < 15 ms |
| Entitlement check P95 | < 25 ms |
| Connection capacity per streaming pod | 5,000 (goal) |
| Cache hit ratio (gateway read endpoints) | 70–90% |

Error Budget (example):
- Availability SLO: 99.0% monthly → 7h 18m budget

---

## 17. Dependency Graph (Logical)

```
[ Clients ]
   |
[ Ingress ]
   |
[ API Gateway ] ----> [ Streaming Service ]
   |        \               |
   |         \              v
   |          \------> [ Metrics Service ]
   |                   /       ^
   v                  /        |
[ Auth Service ] ----/   [ Prometheus ]
   |
[ Keycloak ]

[ Entitlements Service ] <---- Redis (cache)
       |
   PostgreSQL (metadata)

[ Redis ] (caching)
[ ClickHouse / Postgres ] (data queries – downstream services, not inside repo)
[ Kafka ] (stream events for Streaming Service)
```

---

## 18. Release & Deployment Workflow

1. Feature branch → PR (CI: lint, tests, spec sync, security scan)
2. Merge → main:
   - Build multi-arch images for changed services
   - Publish SBOM, signatures (future cosign)
   - Update service manifest version if needed
3. Canary deployment (if environment supports)
4. Promoted to stable after automated smoke & basic synthetic checks
5. Meta repo ingests new manifest → updates service index

Version Bumping Rules:
- Security / bug fix → PATCH
- Add optional endpoint/field → MINOR
- Breaking change (rare; prefer additive) → MAJOR

---

## 19. AI Agent Integration

`.agent/context.yaml` example:
```yaml
repo: 254carbon-access
services:
  - gateway
  - streaming
  - auth
  - entitlements
  - metrics
contracts_from: specs.lock.json
rules:
  - Do not add cross-service imports outside shared/ boundary
  - Use provided service-manifest.yaml when updating metadata
  - Validate OpenAPI sync before committing
```

Agents can safely:
- Add new endpoints (if spec updated upstream)
- Improve caching strategies
- Extend metrics instrumentation

Agents must not:
- Embed long business logic (delegate to future domain services)
- Hardcode secrets

---

## 20. Troubleshooting Guide

| Symptom | Checks | Commands |
|---------|--------|----------|
| 401 Unauthorized everywhere | JWKS stale / Keycloak down | `curl $ACCESS_JWKS_URL` |
| 403 Unexpected | Entitlement cache stale | Flush key in Redis |
| High latency spikes | Redis unreachable / CPU throttling | `kubectl top pods` |
| Streaming disconnects | Backpressure / memory limit | Inspect logs: streaming service |
| Metrics missing | Metrics Service not scraped | `curl metrics-service:8012/metrics` |
| JWKS errors | Wrong realm URL | Check env `ACCESS_JWKS_URL` |

---

## 21. Testing Strategy

| Layer | Tool | Notes |
|-------|------|-------|
| Unit | pytest | Focus domain & adapter logic |
| Contract | OpenAPI diff vs locked version | Prevent unapproved breaks |
| Integration | Local docker/kind harness | Compose minimal stack |
| Load (future) | Locust / k6 | Streaming + REST dual scenario |
| Security (future) | Bandit, dependency scan | CI gating |
| Smoke | scripts/smoke.sh | After container build |

Run:
```
make test
make contract-check
```

---

## 22. Roadmap & Future Splits

| Milestone | Action | Trigger |
|-----------|--------|--------|
| M1 | Introduce GraphQL gateway (optional) | Demand for composite reads |
| M2 | Split Auth + Entitlements into their own repos | High iteration or separate scaling |
| M3 | mTLS + OPA policy integration | Elevated security requirements |
| M4 | Subscription Registry (external) | Streaming > 3 pods & failover complexity |
| M5 | Circuit breakers & adaptive concurrency | Elevated traffic or external latencies |
| M6 | Canary + chaos experiments | Stability objectives |

---

## 23. Contribution Guidelines (Repo Specific)

1. Update spec in `254carbon-specs` first (if API/event contract change).
2. Sync contracts: `python scripts/codegen_sync.py`
3. Add or modify code; ensure tests pass.
4. Run formatting & lint: `make lint` (or auto on commit).
5. Provide PR title with conventional prefix:  
   - `feat(gateway): add curves bulk endpoint`  
   - `fix(streaming): handle heartbeat timeout`
6. For new service logic: update `service-manifest.yaml`.
7. Do not commit vendor or generated artifacts (except manifests & lock files).

---

## 24. Changelog Template

Top-level `CHANGELOG.md` tracks aggregate; services can embed service-specific sections.

```
## [1.2.0] - 2025-10-07
### Added
- gateway: /api/v1/curves/bulk endpoint (non-breaking)
- streaming: subscription filter by commodity tag

### Changed
- entitlements: caching TTL adaptive algorithm

### Fixed
- auth: JWKS cache refresh race condition

### Deprecated
- gateway: /api/v1/legacy-instrument (remove in 1.4.0)

### Security
- Updated dependencies (fastapi minor bump)
```

---

## 25. License / Ownership

- Internal usage while platform stabilizes.
- Ownership: Platform Engineering (currently single developer + AI agents).
- Future: Some service APIs may be open-sourced or published for client SDK generation.

---

## Quick Start

```bash
# Install dev dependencies
make install

# Run gateway locally
cd service-gateway
uvicorn app.main:app --reload --port 8000

# Validate manifests
make manifest-validate

# Build multi-arch image (example gateway)
make buildx SERVICE=gateway VERSION=1.0.0
```

---

## Reference Targets (Makefile Snippets)

| Target | Description |
|--------|-------------|
| make install | Install shared dev dependencies |
| make dev-all | Run all services in dev mode |
| make test | Run tests for all services |
| make lint | Lint & format check |
| make buildx SERVICE=<svc> VERSION=<ver> | Multi-arch image |
| make push SERVICE=<svc> VERSION=<ver> | Push image to GHCR |
| make spec-sync | Pull latest specs from specs repo |
| make contract-check | Verify no breaking changes |
| make smoke | Basic liveness test across services |

---

## Appendix: Example Health Check JSON

```
GET /health
{
  "service": "gateway",
  "status": "ok",
  "uptime_seconds": 5231,
  "dependencies": {
    "redis": "ok",
    "auth": "ok",
    "entitlements": "ok"
  },
  "version": "1.0.0",
  "commit": "abc1234"
}
```

---

> “The access layer should feel invisible: fast, predictable, and boring—in the best way.”


