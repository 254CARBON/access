# Access Layer (`254carbon-access`)

> REST, WebSocket/SSE, and cross-cutting auth/entitlement/metrics services exposed at the platform edge.

Reference: [Platform Overview](../PLATFORM_OVERVIEW.md)

---

## Scope
- Gateway routes REST traffic, handles auth, caches hot reads, and enforces rate limits.
- Streaming service multiplexes Kafka topics to client sessions with entitlement guardrails.
- Auth & Entitlements services federate with Keycloak and Postgres-backed policy stores.
- Metrics service ingests custom metrics from edge services and exposes Prometheus scrape endpoints.

Out of scope: downstream data processing/analytics logic, infrastructure bootstrap (see `../data-processing`, `../infra`).

---

## Components
- `service-gateway/` – FastAPI REST gateway with caching, rate limiting, and OpenAPI contracts synced from `specs/`.
- `service-streaming/` – WebSocket/SSE fanout with Kafka consumers and session registry.
- `service-auth/`, `service-entitlements/` – JWT verification and authorization checks.
- `service-metrics/` – Aggregates request counters and emits `/metrics` for Prometheus.
- `shared/` – Config, tracing, and shared clients.
- `scripts/` – Spec sync, smoke tests, docker/k8s helpers.

---

## Environments

| Environment | Bootstrap | Entry Points | Notes |
|-------------|-----------|--------------|-------|
| `local` | `make docker-up` or `make dev-all` | Gateway `http://localhost:8000`, Streaming `ws://localhost:8001/ws/stream` | Uses mock Keycloak and local Redis/Postgres. |
| `dev` | `../infra` cluster + `kubectl apply -k k8s/overlays/dev` | Ingress `https://api.dev.254carbon.local` | Shared integration; contract checks must pass. |
| `staging` | GitOps-controlled (Flux) referencing `k8s/overlays/staging` | Ingress `https://api.stg.254carbon.local` | Mirrors prod SLO/alerts. |
| `production` | GitOps merge after approval; sealed secrets provide credentials | Ingress `https://api.254carbon.com` | Strict change window and error budget tracking. |

Secrets and environment values live in the respective `k8s/overlays/*` directories and `docs/development-setup.md`.

---

## Runbook

### Daily Checks
- `make smoke` (local) or `kubectl get pods -n 254carbon-access` – verify gateway, streaming, auth, entitlements, metrics pods healthy.
- Grafana dashboard `../observability/dashboards/access/gateway_overview.json` – confirm p95 latency <150 ms, 5xx rate near zero, cache hit ratio healthy.
- Confirm Keycloak JWKS freshness: `curl $ACCESS_JWKS_URL` should return current keys.
- Inspect Redis connection stats: `redis-cli info clients` (port-forward if remote).

### Cache Warm & Served Replay
- Pre-seed Redis for hot served queries after deploys or cache flushes:
  ```
  ./scripts/warm_served_cache.py --tenant tenant-1 --user deploy-bot \
    --redis-url $ACCESS_REDIS_URL \
    --projection-url $ACCESS_PROJECTION_SERVICE_URL
  ```
  Use `--dry-run` to view the plan without writing keys and `--hot-queries-file` to test alternate rankings.
- Monitor warm effectiveness via Grafana dashboard `gateway_served_cache.json` (see Observability) and Prometheus metric `gateway_served_cache_warm_total`.
- Run historical replay/backfill when a tenant misses projections:
  ```
  ../data-processing/scripts/backfill_window.py --from 2025-09-01 --to 2025-09-07 --tenant tenant-1
  ```
  Follow with a cache warm to avoid cold-start latency on newly backfilled curves.

### Deployments
1. Sync contracts: `make spec-sync`; run `make contract-check`.
2. Run test suite and lint: `make test && make lint`.
3. Build images: `make buildx SERVICE=<svc> VERSION=<tag>` for each changed service.
4. Update corresponding `service-*/service-manifest.yaml` with new version.
5. Apply changes: `kubectl apply -k k8s/overlays/<env>` or merge into GitOps repo.
6. Post-deploy verification: `kubectl rollout status deployment/gateway -n 254carbon-access` and confirm `/health` includes the new version.

### Incident Response
- **Auth Failures (401/403 spikes)**  
  - Check JWKS endpoint (`curl $ACCESS_JWKS_URL`).  
  - Flush entitlements cache: `redis-cli --scan --pattern 'entitlement:*' | xargs redis-cli DEL`.  
  - If Keycloak outage persists, enable fallback signing keys (`ACCESS_JWKS_FALLBACK_ENABLED=true`) and restart auth.
- **Gateway Latency Regression**  
  - Verify Redis availability (`kubectl exec deployment/gateway -n 254carbon-access -- redis-cli PING`).  
  - Scale gateway: `kubectl scale deployment/gateway --replicas=3 -n 254carbon-access`.  
  - Coordinate with downstream ClickHouse owners if DB latency is root cause.
- **Streaming Disconnect Storm**  
  - Inspect consumer lag: `kafka-consumer-groups --describe --group streaming-service`.  
  - Increase pods: `kubectl scale deployment/streaming --replicas=4 -n 254carbon-access`.  
  - Adjust connection limits (`ACCESS_MAX_WS_CONNECTIONS`, `ACCESS_HEARTBEAT_TIMEOUT`) and redeploy.
- **Emergency Rollback**  
  - `kubectl rollout undo deployment/<svc> -n 254carbon-access`.  
  - Validate previous image tag via `/health` response.  
  - Update GitOps manifests to prevent redeploying the bad revision.

### On-call Utilities
- Restart service: `kubectl rollout restart deployment/<svc> -n 254carbon-access`.
- Flush rate-limit counters: `redis-cli --scan --pattern 'rl:*' | xargs redis-cli DEL`.
- Rotate API keys: follow `docs/runbooks.md#jwt-rotation` and re-apply `k8s/secrets.yaml`.

---

## Configuration

| Variable | Description | Default | Notes |
|----------|-------------|---------|-------|
| `ACCESS_ENV` | Environment label for logging/tracing | `local` | Propagated to OTEL attributes. |
| `ACCESS_JWKS_URL` | Keycloak JWKS endpoint | `http://keycloak:8080/...` | Mandatory for auth and streaming. |
| `ACCESS_POSTGRES_DSN` | Entitlements metadata store | `postgres://access:access@postgres:5432/access` | Provide via secret in non-local envs. |
| `ACCESS_REDIS_URL` | Cache for sessions, entitlements, rate limits | `redis://redis:6379/0` | TLS supported with `ACCESS_REDIS_SSL_ENABLED=true`. |
| `ACCESS_CACHE_WARM_CONCURRENCY` | Concurrent served cache warm operations | `5` | Increase if projection service can tolerate higher fan-out. |
| `ACCESS_HOT_SERVED_QUERIES_FILE` | Override path for curated hot query rankings | `app/caching/data/hot_served_queries.json` | Accepts absolute path; useful for experiments. |
| `ACCESS_KAFKA_BOOTSTRAP` | Kafka brokers for streaming service | `kafka:9092` | Configure SASL/TLS if required. |
| `ACCESS_METRICS_SERVICE_URL` | Metrics ingestion endpoint | `http://metrics-service:8012` | Gateway/streaming push counters here. |
| `ACCESS_ENABLE_TRACING` | Enable OTEL instrumentation | `false` (local) | Exporter set via `ACCESS_OTEL_EXPORTER`. |
| `ACCESS_RATE_LIMITS_FILE` | Rate-limit configuration path | `config/rate_limits.yaml` | Hot-reload supported via SIGHUP. |

Secrets such as `ACCESS_JWT_SECRET_KEY`, `ACCESS_API_*`, and Keycloak client credentials are defined in `k8s/secrets.yaml` templates; rotate using the runbook referenced above.

---

## Observability
- Metrics exposed via `/metrics` on each service; Prometheus targets configured in `k8s/monitoring/`.
- Grafana dashboards stored at `../observability/dashboards/access/gateway_overview.json` and `../observability/dashboards/access/gateway_served_cache.json`.
- Alerts managed in `../observability/alerts/RED/gateway_red.yaml` and `../observability/alerts/SLO/api_latency_slo.yaml`.
- Logs are structured JSON (stdout). Access with `kubectl logs -l app=gateway -n 254carbon-access`. Loki integration is pending.
- Traces tagged with `service.name=254carbon-gateway` / `254carbon-streaming`; view in Tempo/Jaeger filtered by `client.address`.
- Key metrics for served performance: `gateway_served_cache_warm_total`, `gateway_served_cache_warm_duration_seconds`, and `gateway_served_projection_age_seconds`.

---

## Troubleshooting

### Gateway Returns 500 Errors
1. `kubectl logs deployment/gateway -n 254carbon-access` – check stack trace.
2. Confirm dependencies (Redis, ClickHouse) are reachable.
3. Run smoke tests: `make smoke`.

### Clients Receive 401 Responses
1. Ensure JWKS reachable (`curl $ACCESS_JWKS_URL`).
2. Inspect auth logs for `JWKS_REFRESH_FAILED`.
3. Rotate Keycloak client secret if signature mismatch persists.

### Streaming Connection Flapping
- Review metrics `streaming_active_connections` and `streaming_send_errors`.
- Confirm Kafka lag manageable; run `kafka-consumer-groups --describe`.
- Restart streaming pods (`kubectl rollout restart deployment/streaming -n 254carbon-access`) to clear sessions.

### Metrics Dashboard Empty
- `kubectl logs deployment/metrics -n 254carbon-access` to confirm ingestion healthy.
- Validate Prometheus targets (`/prometheus/targets?search=254carbon-access`).
- Ensure `ACCESS_METRICS_SERVICE_URL` set for gateway/streaming deployments.

---

## Reference
- `Makefile` – automation for development, testing, build, and manifest validation.
- `scripts/dev_cluster.sh` – local multi-service dev environment.
- `docs/runbooks.md` – deep-dive operational playbooks (JWT rotation, cache purges, rate-limit tuning).
- `service-*/service-manifest.yaml` – metadata consumed by `../meta`.
- `k8s/` – Kubernetes overlays per environment.

For cross-repo relationships, SLOs, and shared environment details, rely on the [Platform Overview](../PLATFORM_OVERVIEW.md).
