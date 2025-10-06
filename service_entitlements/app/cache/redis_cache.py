"""
Redis caching layer for Entitlements Service.
"""

import json
import time
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import sys
import os

# Add shared directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..'))

import redis.asyncio as redis
from shared.logging import get_logger
from shared.errors import AccessLayerException
from ..rules.models import EntitlementCheckResponse, EvaluationResult


class RedisCache:
    """Redis caching layer for entitlements."""
    
    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self.logger = get_logger("entitlements.cache.redis")
        self.redis: Optional[redis.Redis] = None
        
        # Cache configuration
        self.default_ttl = 300  # 5 minutes
        self.max_ttl = 3600     # 1 hour
        self.min_ttl = 30       # 30 seconds
        
        # Cache key prefixes
        self.ENTITLEMENT_PREFIX = "entitlement:"
        self.RULE_PREFIX = "rule:"
        self.STATS_PREFIX = "stats:"
    
    async def start(self):
        """Start the Redis cache."""
        try:
            self.redis = redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30
            )
            
            # Test connection
            await self.redis.ping()
            
            self.logger.info("Redis cache started")
            
        except Exception as e:
            self.logger.error("Failed to start Redis cache", error=str(e))
            raise AccessLayerException("REDIS_START_FAILED", str(e))
    
    async def stop(self):
        """Stop the Redis cache."""
        if self.redis:
            await self.redis.close()
            self.logger.info("Redis cache stopped")
    
    async def get_entitlement_result(
        self,
        user_id: str,
        tenant_id: Optional[str],
        resource: str,
        action: str,
        context_hash: str
    ) -> Optional[EntitlementCheckResponse]:
        """Get cached entitlement result."""
        try:
            cache_key = self._get_entitlement_key(user_id, tenant_id, resource, action, context_hash)
            
            cached_data = await self.redis.get(cache_key)
            if not cached_data:
                return None
            
            # Deserialize response
            data = json.loads(cached_data)
            
            # Check if expired
            if data.get("expires_at"):
                expires_at = datetime.fromisoformat(data["expires_at"])
                if expires_at < datetime.now():
                    await self.redis.delete(cache_key)
                    return None
            
            # Reconstruct response
            response = EntitlementCheckResponse(
                allowed=data["allowed"],
                reason=data.get("reason"),
                matched_rules=data.get("matched_rules", []),
                expires_at=expires_at if data.get("expires_at") else None,
                ttl_seconds=data.get("ttl_seconds")
            )
            
            self.logger.debug("Cache hit for entitlement", cache_key=cache_key)
            return response
            
        except Exception as e:
            self.logger.error("Error getting cached entitlement", error=str(e))
            return None
    
    async def set_entitlement_result(
        self,
        user_id: str,
        tenant_id: Optional[str],
        resource: str,
        action: str,
        context_hash: str,
        response: EntitlementCheckResponse,
        ttl_seconds: Optional[int] = None
    ) -> bool:
        """Cache entitlement result."""
        try:
            cache_key = self._get_entitlement_key(user_id, tenant_id, resource, action, context_hash)
            
            # Calculate TTL
            if ttl_seconds is None:
                ttl_seconds = self._calculate_adaptive_ttl(response)
            
            # Ensure TTL is within bounds
            ttl_seconds = max(self.min_ttl, min(self.max_ttl, ttl_seconds))
            
            # Serialize response
            data = {
                "allowed": response.allowed,
                "reason": response.reason,
                "matched_rules": response.matched_rules,
                "expires_at": response.expires_at.isoformat() if response.expires_at else None,
                "ttl_seconds": ttl_seconds,
                "cached_at": datetime.now().isoformat()
            }
            
            await self.redis.setex(
                cache_key,
                ttl_seconds,
                json.dumps(data)
            )
            
            self.logger.debug("Cached entitlement result", cache_key=cache_key, ttl=ttl_seconds)
            return True
            
        except Exception as e:
            self.logger.error("Error caching entitlement", error=str(e))
            return False
    
    async def invalidate_user_entitlements(self, user_id: str) -> int:
        """Invalidate all cached entitlements for a user."""
        try:
            pattern = f"{self.ENTITLEMENT_PREFIX}*:user:{user_id}:*"
            keys = await self.redis.keys(pattern)
            
            if keys:
                await self.redis.delete(*keys)
                self.logger.info("Invalidated user entitlements", user_id=user_id, count=len(keys))
                return len(keys)
            
            return 0
            
        except Exception as e:
            self.logger.error("Error invalidating user entitlements", user_id=user_id, error=str(e))
            return 0
    
    async def invalidate_tenant_entitlements(self, tenant_id: str) -> int:
        """Invalidate all cached entitlements for a tenant."""
        try:
            pattern = f"{self.ENTITLEMENT_PREFIX}*:tenant:{tenant_id}:*"
            keys = await self.redis.keys(pattern)
            
            if keys:
                await self.redis.delete(*keys)
                self.logger.info("Invalidated tenant entitlements", tenant_id=tenant_id, count=len(keys))
                return len(keys)
            
            return 0
            
        except Exception as e:
            self.logger.error("Error invalidating tenant entitlements", tenant_id=tenant_id, error=str(e))
            return 0
    
    async def invalidate_resource_entitlements(self, resource: str) -> int:
        """Invalidate all cached entitlements for a resource."""
        try:
            pattern = f"{self.ENTITLEMENT_PREFIX}*:resource:{resource}:*"
            keys = await self.redis.keys(pattern)
            
            if keys:
                await self.redis.delete(*keys)
                self.logger.info("Invalidated resource entitlements", resource=resource, count=len(keys))
                return len(keys)
            
            return 0
            
        except Exception as e:
            self.logger.error("Error invalidating resource entitlements", resource=resource, error=str(e))
            return 0
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        try:
            info = await self.redis.info()
            
            # Count entitlement keys
            entitlement_keys = await self.redis.keys(f"{self.ENTITLEMENT_PREFIX}*")
            
            return {
                "redis_version": info.get("redis_version"),
                "used_memory": info.get("used_memory_human"),
                "connected_clients": info.get("connected_clients"),
                "total_commands_processed": info.get("total_commands_processed"),
                "keyspace_hits": info.get("keyspace_hits"),
                "keyspace_misses": info.get("keyspace_misses"),
                "entitlement_keys": len(entitlement_keys),
                "hit_rate": self._calculate_hit_rate(info)
            }
            
        except Exception as e:
            self.logger.error("Error getting cache stats", error=str(e))
            return {}
    
    async def clear_cache(self) -> bool:
        """Clear all cache entries."""
        try:
            # Clear entitlement cache
            entitlement_keys = await self.redis.keys(f"{self.ENTITLEMENT_PREFIX}*")
            if entitlement_keys:
                await self.redis.delete(*entitlement_keys)
            
            # Clear rule cache
            rule_keys = await self.redis.keys(f"{self.RULE_PREFIX}*")
            if rule_keys:
                await self.redis.delete(*rule_keys)
            
            # Clear stats cache
            stats_keys = await self.redis.keys(f"{self.STATS_PREFIX}*")
            if stats_keys:
                await self.redis.delete(*stats_keys)
            
            self.logger.info("Cache cleared")
            return True
            
        except Exception as e:
            self.logger.error("Error clearing cache", error=str(e))
            return False
    
    def _get_entitlement_key(
        self,
        user_id: str,
        tenant_id: Optional[str],
        resource: str,
        action: str,
        context_hash: str
    ) -> str:
        """Generate cache key for entitlement result."""
        tenant_part = f":tenant:{tenant_id}" if tenant_id else ""
        return f"{self.ENTITLEMENT_PREFIX}user:{user_id}{tenant_part}:resource:{resource}:action:{action}:ctx:{context_hash}"
    
    def _calculate_adaptive_ttl(self, response: EntitlementCheckResponse) -> int:
        """Calculate adaptive TTL based on response characteristics."""
        base_ttl = self.default_ttl
        
        # Shorter TTL for denied requests (they might change more frequently)
        if not response.allowed:
            base_ttl = base_ttl // 2
        
        # Shorter TTL if no specific expiration time
        if not response.expires_at:
            base_ttl = base_ttl // 2
        
        # Longer TTL for high-priority rules (indicated by multiple matched rules)
        if len(response.matched_rules) > 1:
            base_ttl = int(base_ttl * 1.5)
        
        return base_ttl
    
    def _calculate_hit_rate(self, info: Dict[str, Any]) -> float:
        """Calculate cache hit rate."""
        hits = info.get("keyspace_hits", 0)
        misses = info.get("keyspace_misses", 0)
        total = hits + misses
        
        if total == 0:
            return 0.0
        
        return hits / total
    
    async def health_check(self) -> bool:
        """Check Redis health."""
        try:
            await self.redis.ping()
            return True
        except Exception:
            return False