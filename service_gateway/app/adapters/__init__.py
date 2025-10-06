"""
Adapters package for the Gateway Service.

Contains HTTP client wrappers for internal dependencies (Auth,
Entitlements, Metrics). These adapters encapsulate:

- Base URLs and request shapes
- Retry policies and circuit breakers
- Error handling that maps to shared errors

Keep adapters thin and side-effect free outside of explicit calls.
"""
