"""
Auth Service package for the 254Carbon Access Layer.

This package exposes the FastAPI application for authenticating and
verifying client tokens. It is intentionally small and focused:

- app.main: Application entrypoint that wires routes and lifecycle.
- app.validation: Token validation utilities (JWKS, claims parsing).
- app.jwks: JWKS client helpers for fetching and caching signing keys.

Design notes:
- Keep the package import side-effects minimal; module import must not
  perform network calls. All IO should happen in route handlers or
  explicit startup hooks.
- Use the shared/ utilities for logging, metrics, tracing, and errors.
- Treat this package as stateless; rely on upstream IdP (e.g., Keycloak).
"""
