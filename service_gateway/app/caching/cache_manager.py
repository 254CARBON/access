"""
Gateway cache manager for different cache types.
"""

import asyncio
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING, Union
import sys
import os

# Add shared directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from shared.logging import get_logger
from .adaptive_cache import AdaptiveCache
from .hot_query_loader import HotServedQueryLoader, HotQueryEntry

if TYPE_CHECKING:  # pragma: no cover - imported for typing only
    from ..adapters.served_data_client import ServedDataClient
    from shared.metrics import MetricsCollector


DEFAULT_LATEST_PRICE_TTL = 60
DEFAULT_CURVE_SNAPSHOT_TTL = 600
DEFAULT_CUSTOM_TTL = 900


class CacheManager:
    """Manager for different types of Gateway caches."""

    def __init__(
        self,
        redis_url: str,
        served_client: Optional["ServedDataClient"] = None,
        *,
        metrics: Optional["MetricsCollector"] = None,
        hot_queries_path: Optional[Union[str, Path]] = None,
        warm_concurrency: int = 5,
    ):
        self.redis_url = redis_url
        self.logger = get_logger("gateway.cache_manager")
        self.metrics = metrics
        self.served_client = served_client
        self.hot_query_loader = HotServedQueryLoader(hot_queries_path)
        self._warm_semaphore = asyncio.Semaphore(max(1, warm_concurrency))

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

    async def warm_cache(self, user_id: str, tenant_id: str) -> Dict[str, Any]:
        """
        Warm cache for user (pre-load common data).

        Returns a summary dictionary describing plan counts, hits, misses, and errors.
        """
        if not self.served_client:
            if hasattr(self.adaptive_cache, "warm_cache"):
                self.logger.info(
                    "Delegating cache warm to adaptive cache (served client unavailable)",
                    user_id=user_id,
                    tenant_id=tenant_id,
                )
                fallback_result = await self.adaptive_cache.warm_cache(user_id, tenant_id)
                if isinstance(fallback_result, dict):
                    return fallback_result
                return {
                    "tenant_id": tenant_id,
                    "user_id": user_id,
                    "planned": {"latest_price": 0, "curve_snapshot": 0, "custom": 0},
                    "warmed": {"latest_price": 0, "curve_snapshot": 0, "custom": 0},
                    "misses": 0,
                    "errors": [],
                }

            self.logger.warning(
                "Cache warm requested but served client is not configured; skipping",
                user_id=user_id,
                tenant_id=tenant_id,
            )
            return {
                "tenant_id": tenant_id,
                "user_id": user_id,
                "planned": {"latest_price": 0, "curve_snapshot": 0, "custom": 0},
                "warmed": {"latest_price": 0, "curve_snapshot": 0, "custom": 0},
                "misses": 0,
                "errors": [],
            }

        plan = self._build_warm_plan(tenant_id)
        summary: Dict[str, Any] = {
            "tenant_id": tenant_id,
            "user_id": user_id,
            "planned": {
                "latest_price": len(plan["latest_price"]),
                "curve_snapshot": len(plan["curve_snapshot"]),
                "custom": len(plan["custom"]),
            },
            "warmed": {"latest_price": 0, "curve_snapshot": 0, "custom": 0},
            "misses": 0,
            "errors": [],
        }

        tasks = [
            self._warm_entry(entry)
            for category_entries in plan.values()
            for entry in category_entries
        ]

        if not tasks:
            self.logger.info(
                "No hot served queries eligible for tenant; cache warm skipped",
                tenant_id=tenant_id,
                user_id=user_id,
            )
            return summary

        results = await asyncio.gather(*tasks, return_exceptions=True)
        for outcome in results:
            if isinstance(outcome, Exception):
                self.logger.error(
                    "Cache warm task failed",
                    tenant_id=tenant_id,
                    user_id=user_id,
                    error=str(outcome),
                )
                summary["errors"].append(str(outcome))
                continue

            projection_type = outcome["projection_type"]
            result = outcome["result"]
            if result == "hit":
                summary["warmed"][projection_type] += 1
            elif result == "miss":
                summary["misses"] += 1
            elif result == "error":
                summary["errors"].append(outcome.get("error", "unknown error"))

        self.logger.info(
            "Cache warm completed",
            tenant_id=tenant_id,
            user_id=user_id,
            warmed=summary["warmed"],
            misses=summary["misses"],
            errors=len(summary["errors"]),
        )
        return summary

    def _build_warm_plan(self, tenant_id: str) -> Dict[str, List[HotQueryEntry]]:
        """Construct the cache warm plan for a tenant."""
        return {
            "latest_price": self.hot_query_loader.get_entries("latest_price", tenant_id),
            "curve_snapshot": self.hot_query_loader.get_entries("curve_snapshot", tenant_id),
            "custom": self.hot_query_loader.get_entries("custom", tenant_id),
        }

    async def _warm_entry(self, entry: HotQueryEntry) -> Dict[str, Any]:
        """Warm an individual served cache entry."""
        category = entry.projection_type if entry.projection_type in ("latest_price", "curve_snapshot") else "custom"
        async with self._warm_semaphore:
            start = time.perf_counter()
            age_seconds: Optional[float] = None
            result = "miss"
            error: Optional[str] = None

            try:
                if category == "latest_price":
                    projection = await self.served_client.get_latest_price(entry.tenant_id, entry.instrument_id)  # type: ignore[union-attr]
                    if projection:
                        ttl = entry.ttl_seconds or self.hot_query_loader.default_ttl("latest_price", DEFAULT_LATEST_PRICE_TTL)
                        await self.set_served_latest_price(entry.tenant_id, entry.instrument_id, projection, ttl=ttl)
                        age_seconds = self._extract_projection_age_seconds(projection)
                        result = "hit"
                elif category == "curve_snapshot":
                    horizon = entry.horizon or entry.raw.get("horizon") or "unknown"
                    projection = await self.served_client.get_curve_snapshot(entry.tenant_id, entry.instrument_id, horizon)  # type: ignore[union-attr]
                    if projection:
                        ttl = entry.ttl_seconds or self.hot_query_loader.default_ttl("curve_snapshot", DEFAULT_CURVE_SNAPSHOT_TTL)
                        await self.set_served_curve_snapshot(entry.tenant_id, entry.instrument_id, horizon, projection, ttl=ttl)
                        age_seconds = self._extract_projection_age_seconds(projection)
                        result = "hit"
                else:
                    projection = await self.served_client.get_custom_projection(  # type: ignore[union-attr]
                        entry.tenant_id,
                        entry.instrument_id,
                        entry.projection_type,
                    )
                    if projection:
                        ttl = entry.ttl_seconds or self.hot_query_loader.default_ttl("custom", DEFAULT_CUSTOM_TTL)
                        await self.set_served_custom(entry.tenant_id, entry.projection_type, entry.instrument_id, projection, ttl=ttl)
                        age_seconds = self._extract_projection_age_seconds(projection)
                        result = "hit"
            except Exception as exc:
                error = str(exc)
                result = "error"
                self.logger.error(
                    "Failed to warm served cache entry",
                    projection_type=entry.projection_type,
                    category=category,
                    instrument_id=entry.instrument_id,
                    tenant_id=entry.tenant_id,
                    error=error,
                )
            finally:
                duration = time.perf_counter() - start
                self._record_warm_metrics(category, result, duration, age_seconds)

            if result == "miss":
                self.logger.debug(
                    "Served cache warm miss",
                    projection_type=entry.projection_type,
                    category=category,
                    instrument_id=entry.instrument_id,
                    tenant_id=entry.tenant_id,
                )

            return {
                "projection_type": category,
                "raw_projection_type": entry.projection_type,
                "instrument_id": entry.instrument_id,
                "horizon": entry.horizon,
                "result": result,
                "error": error,
            }

    def _record_warm_metrics(
        self,
        category: str,
        result: str,
        duration: float,
        age_seconds: Optional[float],
    ) -> None:
        """Record metrics for cache warm operations."""
        if not self.metrics:
            return

        try:
            self.metrics.increment_counter(
                "served_cache_warm_total",
                projection_type=category,
                result=result,
            )
            self.metrics.observe_histogram(
                "served_cache_warm_duration_seconds",
                duration,
                projection_type=category,
            )
            if age_seconds is not None and result == "hit":
                self.metrics.observe_histogram(
                    "served_projection_age_seconds",
                    age_seconds,
                    projection_type=category,
                )
        except Exception as exc:  # pragma: no cover - metrics failures should never break warming
            self.logger.debug("Failed to record warm metrics", error=str(exc))

    def _extract_projection_age_seconds(self, projection: Dict[str, Any]) -> Optional[float]:
        """Compute age of served projection based on last updated timestamps."""
        timestamp = (
            projection.get("last_updated")
            or projection.get("data", {}).get("timestamp")
            or projection.get("metadata", {}).get("snapshot_at")
        )
        if not timestamp:
            return None

        parsed = self._parse_timestamp(timestamp)
        if parsed is None:
            return None

        now = datetime.now(timezone.utc)
        return max(0.0, (now - parsed).total_seconds())

    @staticmethod
    def _parse_timestamp(value: str) -> Optional[datetime]:
        """Parse ISO timestamp strings safely."""
        try:
            if value.endswith("Z"):
                value = value.replace("Z", "+00:00")
            parsed = datetime.fromisoformat(value)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except ValueError:
            return None

    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics."""
        try:
            stats = await self.adaptive_cache.get_stats()
            if not isinstance(stats, dict):
                stats = {}

            stats.setdefault("cache_types", list(self.CACHE_PREFIXES.keys()))
            stats.setdefault("warm_cache_available", hasattr(self.adaptive_cache, "warm_cache"))
            stats.setdefault("hot_query_categories", self.hot_query_loader.categories())
            return stats

        except Exception as e:
            self.logger.error("Cache stats error", error=str(e))
            return {
                "error": str(e),
                "cache_types": list(self.CACHE_PREFIXES.keys()),
                "warm_cache_available": hasattr(self.adaptive_cache, "warm_cache"),
                "hot_query_categories": self.hot_query_loader.categories(),
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
