"""
Gateway cache manager for different cache types.
"""

import json
import time
from typing import Dict, Any, Optional, List
import sys
import os

# Add shared directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from shared.logging import get_logger
from .adaptive_cache import AdaptiveCache


class CacheManager:
    """Manager for different types of Gateway caches."""

    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self.logger = get_logger("gateway.cache_manager")

        # Initialize adaptive cache
        self.adaptive_cache = AdaptiveCache(redis_url)

        # Cache key prefixes
        self.CACHE_PREFIXES = {
            "instruments": "instruments",
            "curves": "curves",
            "products": "products",
            "pricing": "pricing",
            "historical": "historical",
            "user_context": "user_context",
            "rate_limit": "rate_limit",
            "served_latest_price": "served_latest_price",
            "served_curve_snapshot": "served_curve_snapshot",
            "served_custom": "served_custom"
        }

    async def _safe_get(self, prefix: str, *args) -> Optional[Any]:
        """Safely get cached data, handling errors."""
        try:
            return await self.adaptive_cache.get(prefix, *args)
        except Exception as exc:
            self.logger.error("Cache fetch error", prefix=prefix, error=str(exc))
            return None

    async def get_instruments(self, user_id: str, tenant_id: str) -> Optional[List[Dict[str, Any]]]:
        """Get cached instruments for user."""
        cache_key = f"{user_id}:{tenant_id}"
        cached_data = await self._safe_get("instruments", cache_key)

        if cached_data:
            return cached_data
        return None

    async def set_instruments(self, user_id: str, tenant_id: str, instruments: List[Dict[str, Any]]) -> bool:
        """Cache instruments for user."""
        cache_key = f"{user_id}:{tenant_id}"
        return await self.adaptive_cache.set("instruments", instruments, cache_key)

    async def get_curves(self, user_id: str, tenant_id: str) -> Optional[List[Dict[str, Any]]]:
        """Get cached curves for user."""
        cache_key = f"{user_id}:{tenant_id}"
        cached_data = await self._safe_get("curves", cache_key)

        if cached_data:
            return cached_data
        return None

    async def set_curves(self, user_id: str, tenant_id: str, curves: List[Dict[str, Any]]) -> bool:
        """Cache curves for user."""
        cache_key = f"{user_id}:{tenant_id}"
        return await self.adaptive_cache.set("curves", curves, cache_key)

    async def get_user_context(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get cached user context."""
        return await self._safe_get("user_context", user_id)

    async def set_user_context(self, user_id: str, context: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """Cache user context."""
        return await self.adaptive_cache.set("user_context", context, user_id, ttl=ttl)

    async def get_rate_limit_status(self, client_id: str, endpoint: str) -> Optional[Dict[str, Any]]:
        """Get rate limit status."""
        return await self._safe_get("rate_limit", client_id, endpoint)

    async def set_rate_limit_status(self, client_id: str, endpoint: str, status: Dict[str, Any]) -> bool:
        """Cache rate limit status."""
        return await self.adaptive_cache.set("rate_limit", status, client_id, endpoint, ttl=60)

    async def warm_cache(self, user_id: str, tenant_id: str):
        """Warm cache for user (pre-load common data)."""
        if hasattr(self.adaptive_cache, "warm_cache"):
            return await self.adaptive_cache.warm_cache(user_id, tenant_id)

        self.logger.info("Warming cache", user_id=user_id, tenant_id=tenant_id)

        # Simulate loading instruments and curves
        # In a real implementation, this would call downstream services
        instruments = [
            {"id": "EURUSD", "name": "Euro/US Dollar", "type": "forex"},
            {"id": "GBPUSD", "name": "British Pound/US Dollar", "type": "forex"},
            {"id": "USDJPY", "name": "US Dollar/Japanese Yen", "type": "forex"}
        ]

        curves = [
            {"id": "USD_CURVE", "name": "USD Yield Curve", "currency": "USD"},
            {"id": "EUR_CURVE", "name": "EUR Yield Curve", "currency": "EUR"},
            {"id": "GBP_CURVE", "name": "GBP Yield Curve", "currency": "GBP"}
        ]

        # Cache the data
        await self.set_instruments(user_id, tenant_id, instruments)
        await self.set_curves(user_id, tenant_id, curves)
        return True

    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics."""
        try:
            stats = await self.adaptive_cache.get_stats()
            if not isinstance(stats, dict):
                stats = {}

            stats.setdefault("cache_types", list(self.CACHE_PREFIXES.keys()))
            stats.setdefault("warm_cache_available", hasattr(self.adaptive_cache, "warm_cache"))
            return stats

        except Exception as e:
            self.logger.error("Cache stats error", error=str(e))
            return {
                "error": str(e),
                "cache_types": list(self.CACHE_PREFIXES.keys()),
                "warm_cache_available": hasattr(self.adaptive_cache, "warm_cache")
            }

    async def get_products(self, user_id: str, tenant_id: str) -> Optional[List[Dict[str, Any]]]:
        """Get cached products for user."""
        cache_key = f"{user_id}:{tenant_id}"
        cached_data = await self._safe_get("products", cache_key)

        if cached_data:
            return cached_data
        return None

    async def set_products(self, user_id: str, tenant_id: str, products: List[Dict[str, Any]]) -> bool:
        """Cache products for user."""
        cache_key = f"{user_id}:{tenant_id}"
        return await self.adaptive_cache.set("products", products, cache_key)

    async def get_pricing(self, user_id: str, tenant_id: str) -> Optional[List[Dict[str, Any]]]:
        """Get cached pricing data for user."""
        cache_key = f"{user_id}:{tenant_id}"
        cached_data = await self._safe_get("pricing", cache_key)

        if cached_data:
            return cached_data
        return None

    async def set_pricing(self, user_id: str, tenant_id: str, pricing: List[Dict[str, Any]]) -> bool:
        """Cache pricing data for user."""
        cache_key = f"{user_id}:{tenant_id}"
        return await self.adaptive_cache.set("pricing", pricing, cache_key)

    async def get_historical(self, user_id: str, tenant_id: str) -> Optional[List[Dict[str, Any]]]:
        """Get cached historical data for user."""
        cache_key = f"{user_id}:{tenant_id}"
        cached_data = await self._safe_get("historical", cache_key)

        if cached_data:
            return cached_data
        return None

    async def set_historical(self, user_id: str, tenant_id: str, historical: List[Dict[str, Any]]) -> bool:
        """Cache historical data for user."""
        cache_key = f"{user_id}:{tenant_id}"
        return await self.adaptive_cache.set("historical", historical, cache_key)

    async def clear_user_cache(self, user_id: str) -> bool:
        """Clear all cache entries for a user."""
        patterns = [
            f"gateway:*{user_id}*",
            f"gateway:*{user_id}:*"
        ]

        success = True
        for pattern in patterns:
            if not await self.adaptive_cache.clear_pattern(pattern):
                success = False

        if success:
            self.logger.info("Cleared user cache", user_id=user_id)

        return success

    async def get_served_latest_price(self, tenant_id: str, instrument_id: str) -> Optional[Dict[str, Any]]:
        """Get cached served latest price for tenant + instrument."""
        cache_key = f"{tenant_id}:{instrument_id}"
        cached_data = await self._safe_get("served_latest_price", cache_key)
        return self._deserialize_json(cached_data)

    async def set_served_latest_price(
        self,
        tenant_id: str,
        instrument_id: str,
        projection: Dict[str, Any],
        ttl: Optional[int] = None
    ) -> bool:
        """Cache served latest price projection."""
        cache_key = f"{tenant_id}:{instrument_id}"
        payload = json.dumps(projection)
        return await self.adaptive_cache.set("served_latest_price", payload, cache_key, ttl=ttl)

    async def get_served_curve_snapshot(
        self,
        tenant_id: str,
        instrument_id: str,
        horizon: str
    ) -> Optional[Dict[str, Any]]:
        """Get cached served curve snapshot."""
        cache_key = f"{tenant_id}:{instrument_id}:{horizon}"
        cached_data = await self._safe_get("served_curve_snapshot", cache_key)
        return self._deserialize_json(cached_data)

    async def set_served_curve_snapshot(
        self,
        tenant_id: str,
        instrument_id: str,
        horizon: str,
        projection: Dict[str, Any],
        ttl: Optional[int] = None
    ) -> bool:
        """Cache served curve snapshot projection."""
        cache_key = f"{tenant_id}:{instrument_id}:{horizon}"
        payload = json.dumps(projection)
        return await self.adaptive_cache.set("served_curve_snapshot", payload, cache_key, ttl=ttl)

    async def get_served_custom(
        self,
        tenant_id: str,
        projection_type: str,
        instrument_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get cached custom served projection."""
        cache_key = f"{tenant_id}:{projection_type}:{instrument_id}"
        cached_data = await self._safe_get("served_custom", cache_key)
        return self._deserialize_json(cached_data)

    async def set_served_custom(
        self,
        tenant_id: str,
        projection_type: str,
        instrument_id: str,
        projection: Dict[str, Any],
        ttl: Optional[int] = None
    ) -> bool:
        """Cache custom served projection."""
        cache_key = f"{tenant_id}:{projection_type}:{instrument_id}"
        payload = json.dumps(projection)
        return await self.adaptive_cache.set("served_custom", payload, cache_key, ttl=ttl)

    def _deserialize_json(self, value: Any) -> Optional[Any]:
        """Deserialize cached JSON payloads."""
        if value is None:
            return None

        if isinstance(value, (dict, list)):
            return value

        try:
            return json.loads(value)
        except (TypeError, json.JSONDecodeError):
            self.logger.warning("Failed to deserialize cached served payload")
            return None

    async def invalidate_user_cache(self, user_id: str, tenant_id: str) -> bool:
        """Invalidate cache for a user."""
        if hasattr(self.adaptive_cache, "invalidate_user"):
            return await self.adaptive_cache.invalidate_user(user_id, tenant_id)
        return await self.clear_user_cache(user_id)
