"""
Token validation package.

Provides helpers used by the Auth Service to validate JWTs issued by the
upstream identity provider. Typical responsibilities include:

- Fetching and caching JWKS (signing keys) to verify signatures.
- Validating token structure, signature, expiry, audience, and issuer.
- Extracting user claims and shaping a consistent `user_info` object.

Implementation is intentionally decoupled from any specific IdP; only
standard JOSE/JWT behaviors are assumed so the IdP can be switched with
configuration.
"""
