"""
Token bucket rate limiter for Gateway service.
"""

import time
from typing import Dict, Any, Optional, Tuple
import redis.asyncio as redis
from fastapi import Request
import sys
import os

# Add shared directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from shared.logging import get_logger
from shared.errors import RateLimitError


class TokenBucketRateLimiter:
    """Distributed token bucket rate limiter using Redis."""

    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self.logger = get_logger("gateway.rate_limiter")
        self._redis: Optional[redis.Redis] = None

        # Default rate limits (requests per minute)
        self.default_limits = {
            "public": 100,      # 100 req/min for public endpoints
            "authenticated": 1000,  # 1000 req/min for authenticated users
            "heavy": 10,        # 10 req/min for heavy operations
            "admin": 5          # 5 req/min for admin operations
        }

    async def _get_redis(self) -> redis.Redis:
        """Get Redis connection."""
        if self._redis is None:
            self._redis = redis.from_url(self.redis_url)
        return self._redis

    def _make_key(self, client_id: str, endpoint: str) -> str:
        """Generate rate limit key."""
        return f"rate_limit:{client_id}:{endpoint}"

    async def check_rate_limit(self, client_id: str, endpoint: str, limit_type: str = "authenticated") -> Dict[str, Any]:
        """Check if request is within rate limits."""
        try:
            redis_client = await self._get_redis()
            key = self._make_key(client_id, endpoint)
            limit = self.default_limits.get(limit_type, self.default_limits["authenticated"])

            # Window size in seconds (1 minute)
            window_size = 60

            current_time = time.time()

            # Use Redis sorted set for sliding window
            # Remove old entries outside the window
            cutoff_time = current_time - window_size
            await redis_client.zremrangebyscore(key, 0, cutoff_time)

            # Count current requests in window
            current_count = await redis_client.zcard(key)

            if current_count >= limit:
                # Rate limit exceeded
                ttl = await redis_client.ttl(key) or window_size
                self.logger.warning(
                    "Rate limit exceeded",
                    client_id=client_id,
                    endpoint=endpoint,
                    current_count=current_count,
                    limit=limit
                )

                return {
                    "allowed": False,
                    "current_count": current_count,
                    "limit": limit,
                    "reset_in_seconds": int(ttl),
                    "retry_after": int(ttl)
                }

            # Add current request to the window
            await redis_client.zadd(key, {str(current_time): current_time})
            await redis_client.expire(key, window_size)

            return {
                "allowed": True,
                "current_count": current_count + 1,
                "limit": limit,
                "remaining": limit - (current_count + 1),
                "reset_in_seconds": window_size
            }

        except Exception as e:
            self.logger.error("Rate limit check error", error=str(e))
            # Allow request if rate limiter fails
            return {
                "allowed": True,
                "current_count": 0,
                "limit": self.default_limits.get(limit_type, self.default_limits["authenticated"]),
                "remaining": self.default_limits.get(limit_type, self.default_limits["authenticated"]),
                "reset_in_seconds": 60,
                "error": str(e)
            }

    async def get_rate_limit_status(self, client_id: str, endpoint: str) -> Dict[str, Any]:
        """Get current rate limit status for client and endpoint."""
        try:
            redis_client = await self._get_redis()
            key = self._make_key(client_id, endpoint)

            current_count = await redis_client.zcard(key)
            limit = self.default_limits.get("authenticated", 1000)

            return {
                "current_count": current_count,
                "limit": limit,
                "remaining": max(0, limit - current_count),
                "reset_in_seconds": 60
            }

        except Exception as e:
            self.logger.error("Rate limit status error", error=str(e))
            return {
                "error": str(e),
                "current_count": 0,
                "limit": self.default_limits.get("authenticated", 1000),
                "remaining": self.default_limits.get("authenticated", 1000)
            }

    async def reset_rate_limit(self, client_id: str, endpoint: str) -> bool:
        """Reset rate limit for client and endpoint."""
        try:
            redis_client = await self._get_redis()
            key = self._make_key(client_id, endpoint)

            await redis_client.delete(key)

            self.logger.info("Rate limit reset", client_id=client_id, endpoint=endpoint)
            return True

        except Exception as e:
            self.logger.error("Rate limit reset error", error=str(e))
            return False

    async def get_global_stats(self) -> Dict[str, Any]:
        """Get global rate limiting statistics."""
        try:
            redis_client = await self._get_redis()
            pattern = "rate_limit:*"

            keys = await redis_client.keys(pattern)

            total_keys = len(keys)
            total_requests = 0

            for key in keys:
                count = await redis_client.zcard(key)
                total_requests += count

            return {
                "total_clients": total_keys,
                "total_requests": total_requests,
                "average_requests_per_client": total_requests / max(1, total_keys)
            }

        except Exception as e:
            self.logger.error("Global stats error", error=str(e))
            return {"error": str(e)}


class RateLimitMiddleware:
    """Rate limiting middleware for FastAPI."""

    def __init__(self, rate_limiter: TokenBucketRateLimiter):
        self.rate_limiter = rate_limiter
        self.logger = get_logger("gateway.rate_limit_middleware")

    async def check_request(self, request, limit_type: str = "authenticated") -> Dict[str, Any]:
        """Check rate limit for request."""
        # Extract client ID (use IP for public, user_id for authenticated)
        client_id = self._get_client_id(request)

        # Determine endpoint category
        endpoint = self._categorize_endpoint(request.url.path)

        return await self.rate_limiter.check_rate_limit(client_id, endpoint, limit_type)

    def _get_client_id(self, request: Request) -> str:
        """Extract client ID from request."""
        # Try to get user_id from request state (set by auth middleware)
        if hasattr(request.state, 'user_info'):
            return request.state.user_info.get('user_id', 'anonymous')

        # Fall back to IP address
        forwarded_for = request.headers.get('X-Forwarded-For')
        if forwarded_for:
            return forwarded_for.split(',')[0].strip()

        real_ip = request.headers.get('X-Real-IP')
        if real_ip:
            return real_ip

        return request.client.host if request.client else 'unknown'

    def _categorize_endpoint(self, path: str) -> str:
        """Categorize endpoint for rate limiting."""
        if path.startswith('/api/v1/cache/warm') or path.startswith('/api/v1/admin'):
            return 'admin'
        elif path.startswith('/api/v1/curves/recompute') or path.startswith('/api/v1/bulk'):
            return 'heavy'
        elif path.startswith('/api/v1/'):
            return 'authenticated'
        else:
            return 'public'
