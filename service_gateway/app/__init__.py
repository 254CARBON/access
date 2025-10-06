"""
API Gateway Service package for the 254Carbon Access Layer.

The gateway fronts client requests, enforcing:
- Authentication: via the Auth service
- Authorization/Entitlements: via the Entitlements service
- Rate limiting and caching: local adaptive cache + token bucket
- Circuit-breaking and retries for resilient downstream calls

Structure:
- app.main: FastAPI app, routes, and middleware wiring.
- app.adapters: HTTP clients for internal services.
- app.caching: Cache manager and strategies.
- app.ratelimit: Token-bucket and middleware.
- app.domain: Cross-cutting domain helpers (e.g., auth middleware).
"""
