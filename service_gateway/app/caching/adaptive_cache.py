"""
Adaptive TTL caching for Gateway service.
"""

import time
import hashlib
from typing import Dict, Any, Optional, Tuple
import redis.asyncio as redis
import sys
import os

# Add shared directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from shared.logging import get_logger


class AdaptiveCache:
    """Adaptive TTL cache with hit ratio monitoring."""

    def __init__(self, redis_url: str, base_ttl: int = 300, max_ttl: int = 3600, min_ttl: int = 60):
        self.redis_url = redis_url
        self.base_ttl = base_ttl
        self.max_ttl = max_ttl
        self.min_ttl = min_ttl
        self.logger = get_logger("gateway.cache")

        self._redis: Optional[redis.Redis] = None
        self._hit_stats: Dict[str, Tuple[int, int, float]] = {}  # key -> (hits, misses, last_update)

    async def _get_redis(self) -> redis.Redis:
        """Get Redis connection."""
        if self._redis is None:
            self._redis = redis.from_url(self.redis_url)
        return self._redis

    def _make_key(self, prefix: str, *args) -> str:
        """Generate cache key."""
        key_parts = [prefix] + [str(arg) for arg in args]
        key_string = ":".join(key_parts)
        return f"gateway:{hashlib.md5(key_string.encode()).hexdigest()}"

    async def get(self, prefix: str, *args) -> Optional[Any]:
        """Get value from cache."""
        try:
            redis_client = await self._get_redis()
            key = self._make_key(prefix, *args)

            cached_data = await redis_client.get(key)
            if cached_data:
                # Record hit
                self._record_access(key, hit=True)
                return cached_data.decode('utf-8') if isinstance(cached_data, bytes) else cached_data
            else:
                # Record miss
                self._record_access(key, hit=False)
                return None

        except Exception as e:
            self.logger.error("Cache get error", error=str(e))
            return None

    async def set(self, prefix: str, value: Any, *args, ttl: Optional[int] = None) -> bool:
        """Set value in cache with adaptive TTL."""
        try:
            redis_client = await self._get_redis()
            key = self._make_key(prefix, *args)

            # Calculate adaptive TTL
            cache_ttl = await self._calculate_adaptive_ttl(key) if ttl is None else ttl

            await redis_client.setex(key, cache_ttl, str(value))
            self.logger.debug("Cached value", key=key, ttl=cache_ttl)
            return True

        except Exception as e:
            self.logger.error("Cache set error", error=str(e))
            return False

    async def _record_access(self, key: str, hit: bool):
        """Record cache access for adaptive TTL calculation."""
        current_time = time.time()

        if key not in self._hit_stats:
            self._hit_stats[key] = (0, 0, current_time)

        hits, misses, last_update = self._hit_stats[key]

        if hit:
            hits += 1
        else:
            misses += 1

        self._hit_stats[key] = (hits, misses, current_time)

    async def _calculate_adaptive_ttl(self, key: str) -> int:
        """Calculate adaptive TTL based on access patterns."""
        if key not in self._hit_stats:
            return self.base_ttl

        hits, misses, last_update = self._hit_stats[key]
        current_time = time.time()

        # Calculate hit ratio
        total_accesses = hits + misses
        if total_accesses == 0:
            return self.base_ttl

        hit_ratio = hits / total_accesses

        # Calculate time since last access
        time_since_access = current_time - last_update

        # Adaptive TTL calculation:
        # - Higher hit ratio = longer TTL
        # - More recent access = slightly longer TTL
        # - Recent misses = shorter TTL

        if misses > hits * 0.3 and time_since_access < 300:  # Recent misses
            adaptive_ttl = max(self.min_ttl, self.base_ttl * 0.5)
        elif hit_ratio > 0.8:  # High hit ratio
            adaptive_ttl = min(self.max_ttl, self.base_ttl * 2)
        elif hit_ratio > 0.5:  # Medium hit ratio
            adaptive_ttl = self.base_ttl
        else:  # Low hit ratio
            adaptive_ttl = max(self.min_ttl, self.base_ttl * 0.7)

        # Apply time factor (recently accessed = slightly longer TTL)
        if time_since_access < 60:
            adaptive_ttl = int(adaptive_ttl * 1.2)

        self.logger.debug(
            "Adaptive TTL calculated",
            key=key,
            hit_ratio=hit_ratio,
            time_since_access=time_since_access,
            calculated_ttl=adaptive_ttl
        )

        return int(adaptive_ttl)

    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        try:
            redis_client = await self._get_redis()
            pattern = "gateway:*"

            keys = await redis_client.keys(pattern)

            return {
                "total_keys": len(keys),
                "tracked_keys": len(self._hit_stats),
                "pattern": pattern
            }

        except Exception as e:
            self.logger.error("Cache stats error", error=str(e))
            return {"error": str(e)}

    async def clear_pattern(self, pattern: str) -> bool:
        """Clear cache keys matching pattern."""
        try:
            redis_client = await self._get_redis()
            keys = await redis_client.keys(pattern)

            if keys:
                await redis_client.delete(*keys)
                self.logger.info("Cleared cache pattern", pattern=pattern, keys_count=len(keys))

            return True

        except Exception as e:
            self.logger.error("Cache clear error", error=str(e))
            return False
