"""
Entitlements Service package for the 254Carbon Access Layer.

This package evaluates whether a given user is entitled to perform an
action on a resource under a tenant. It provides:

- app.main: API surface for entitlement checks and health.
- app.rules: Rule model, engine, and condition evaluation utilities.
- app.cache: Redis-backed caching for decision results.
- app.persistence: Persistence (e.g., PostgreSQL) for rules storage.

Guidelines:
- The service is stateless; rely on external cache/DB.
- Optimize for low-latency evaluations; cache where possible.
- Keep rule evaluation deterministic and observable (metrics + logs).
"""
