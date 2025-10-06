"""
Cache package for Entitlements Service.

Currently provides a Redis-backed cache that stores entitlement
decisions with adaptive TTLs to accelerate repeated checks while
maintaining correctness.
"""
