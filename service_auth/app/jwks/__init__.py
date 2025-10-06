"""
JWKS client package.

Contains logic for retrieving and caching JSON Web Key Sets (JWKS) used
to verify JWT signatures. This is shared by token validation routines in
the Auth Service.

Key points:
- Keep network fetches resilient (timeouts, retries, caching).
- Cache keys for a reasonable TTL to avoid hammering the IdP.
- Prefer kid (key id) selection when multiple keys are present.
"""
