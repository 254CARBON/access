"""
Gateway cache manager for different cache types.
"""

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
            "rate_limit": "rate_limit"
        }

    async def get_instruments(self, user_id: str, tenant_id: str) -> Optional[List[Dict[str, Any]]]:
        """Get cached instruments for user."""
        cache_key = f"{user_id}:{tenant_id}"
        cached_data = await self.adaptive_cache.get("instruments", cache_key)

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
        cached_data = await self.adaptive_cache.get("curves", cache_key)

        if cached_data:
            return cached_data
        return None

    async def set_curves(self, user_id: str, tenant_id: str, curves: List[Dict[str, Any]]) -> bool:
        """Cache curves for user."""
        cache_key = f"{user_id}:{tenant_id}"
        return await self.adaptive_cache.set("curves", curves, cache_key)

    async def get_user_context(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get cached user context."""
        return await self.adaptive_cache.get("user_context", user_id)

    async def set_user_context(self, user_id: str, context: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """Cache user context."""
        return await self.adaptive_cache.set("user_context", context, user_id, ttl=ttl)

    async def get_rate_limit_status(self, client_id: str, endpoint: str) -> Optional[Dict[str, Any]]:
        """Get rate limit status."""
        return await self.adaptive_cache.get("rate_limit", client_id, endpoint)

    async def set_rate_limit_status(self, client_id: str, endpoint: str, status: Dict[str, Any]) -> bool:
        """Cache rate limit status."""
        return await self.adaptive_cache.set("rate_limit", status, client_id, endpoint, ttl=60)

    async def warm_cache(self, user_id: str, tenant_id: str):
        """Warm cache for user (pre-load common data)."""
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

    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics."""
        try:
            stats = await self.adaptive_cache.get_stats()

            # Add cache manager specific stats
            stats.update({
                "cache_types": list(self.CACHE_PREFIXES.keys()),
                "warm_cache_available": True
            })

            return stats

        except Exception as e:
            self.logger.error("Cache stats error", error=str(e))
            return {"error": str(e)}

    async def get_products(self, user_id: str, tenant_id: str) -> Optional[List[Dict[str, Any]]]:
        """Get cached products for user."""
        cache_key = f"{user_id}:{tenant_id}"
        cached_data = await self.adaptive_cache.get("products", cache_key)

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
        cached_data = await self.adaptive_cache.get("pricing", cache_key)

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
        cached_data = await self.adaptive_cache.get("historical", cache_key)

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
