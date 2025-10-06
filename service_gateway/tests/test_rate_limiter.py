"""
Unit tests for Gateway Rate Limiter.
"""

import pytest
import time
from unittest.mock import AsyncMock, patch, MagicMock
from typing import Dict, Any

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from service_gateway.app.ratelimit.token_bucket import TokenBucketRateLimiter, RateLimitMiddleware
from shared.errors import RateLimitError


class TestTokenBucketRateLimiter:
    """Test cases for TokenBucketRateLimiter."""

    @pytest.fixture
    def rate_limiter(self):
        """Create TokenBucketRateLimiter instance."""
        return TokenBucketRateLimiter("redis://localhost:6379/0")

    @pytest.fixture
    def mock_request(self):
        """Mock FastAPI Request object."""
        request = MagicMock()
        request.client.host = "127.0.0.1"
        request.url.path = "/api/v1/instruments"
        return request

    @pytest.mark.asyncio
    async def test_check_rate_limit_allowed(self, rate_limiter):
        """Test rate limit check when request is allowed."""
        client_id = "127.0.0.1"
        endpoint = "/api/v1/instruments"
        limit_type = "authenticated"

        mock_redis_response = {
            "current_count": 5,
            "limit": 1000,
            "reset_in_seconds": 45,
            "allowed": True
        }

        with patch.object(rate_limiter, '_get_redis', new_callable=AsyncMock) as mock_get_redis:
            mock_redis = AsyncMock()
            mock_get_redis.return_value = mock_redis

            # Mock Redis pipeline operations
            mock_pipeline = AsyncMock()
            mock_redis.pipeline.return_value.__aenter__.return_value = mock_pipeline
            mock_pipeline.get.return_value = None
            mock_pipeline.setex.return_value = None
            mock_pipeline.expire.return_value = None
            mock_pipeline.execute.return_value = [None, None, None]

            result = await rate_limiter.check_rate_limit(client_id, endpoint, limit_type)

            assert result["allowed"] is True
            assert result["current_count"] == 1
            assert result["limit"] == 1000

    @pytest.mark.asyncio
    async def test_check_rate_limit_exceeded(self, rate_limiter):
        """Test rate limit check when limit is exceeded."""
        client_id = "127.0.0.1"
        endpoint = "/api/v1/instruments"
        limit_type = "authenticated"

        with patch.object(rate_limiter, '_get_redis', new_callable=AsyncMock) as mock_get_redis:
            mock_redis = AsyncMock()
            mock_get_redis.return_value = mock_redis

            # Mock Redis pipeline operations - simulate limit exceeded
            mock_pipeline = AsyncMock()
            mock_redis.pipeline.return_value.__aenter__.return_value = mock_pipeline
            mock_pipeline.get.return_value = "1000"  # Already at limit
            mock_pipeline.execute.return_value = ["1000", None, None]

            result = await rate_limiter.check_rate_limit(client_id, endpoint, limit_type)

            assert result["allowed"] is False
            assert result["current_count"] == 1000
            assert result["limit"] == 1000

    @pytest.mark.asyncio
    async def test_check_rate_limit_different_types(self, rate_limiter):
        """Test rate limit check with different limit types."""
        client_id = "127.0.0.1"
        endpoint = "/api/v1/instruments"

        limit_types = ["public", "authenticated", "heavy", "admin"]
        expected_limits = [100, 1000, 10, 5]

        for limit_type, expected_limit in zip(limit_types, expected_limits):
            with patch.object(rate_limiter, '_get_redis', new_callable=AsyncMock) as mock_get_redis:
                mock_redis = AsyncMock()
                mock_get_redis.return_value = mock_redis

                mock_pipeline = AsyncMock()
                mock_redis.pipeline.return_value.__aenter__.return_value = mock_pipeline
                mock_pipeline.get.return_value = None
                mock_pipeline.setex.return_value = None
                mock_pipeline.expire.return_value = None
                mock_pipeline.execute.return_value = [None, None, None]

                result = await rate_limiter.check_rate_limit(client_id, endpoint, limit_type)

                assert result["limit"] == expected_limit

    @pytest.mark.asyncio
    async def test_make_key(self, rate_limiter):
        """Test rate limit key generation."""
        client_id = "127.0.0.1"
        endpoint = "/api/v1/instruments"
        expected_key = f"rate_limit:{client_id}:{endpoint}"

        key = rate_limiter._make_key(client_id, endpoint)
        assert key == expected_key

    @pytest.mark.asyncio
    async def test_redis_connection_error(self, rate_limiter):
        """Test handling of Redis connection errors."""
        client_id = "127.0.0.1"
        endpoint = "/api/v1/instruments"

        with patch.object(rate_limiter, '_get_redis', new_callable=AsyncMock) as mock_get_redis:
            mock_get_redis.side_effect = Exception("Redis connection failed")

            # Should handle error gracefully and allow request
            result = await rate_limiter.check_rate_limit(client_id, endpoint)

            assert result["allowed"] is True
            assert result["error"] == "Redis unavailable"

    @pytest.mark.asyncio
    async def test_get_global_stats(self, rate_limiter):
        """Test getting global rate limit statistics."""
        mock_stats = {
            "total_requests": 1000,
            "allowed_requests": 950,
            "blocked_requests": 50,
            "active_clients": 25
        }

        with patch.object(rate_limiter, '_get_redis', new_callable=AsyncMock) as mock_get_redis:
            mock_redis = AsyncMock()
            mock_get_redis.return_value = mock_redis
            mock_redis.scan_iter.return_value = [
                b"rate_limit:127.0.0.1:/api/v1/instruments",
                b"rate_limit:192.168.1.1:/api/v1/curves"
            ]
            mock_redis.get.side_effect = ["500", "300"]

            result = await rate_limiter.get_global_stats()

            assert "total_clients" in result
            assert "total_requests" in result


class TestRateLimitMiddleware:
    """Test cases for RateLimitMiddleware."""

    @pytest.fixture
    def rate_limit_middleware(self):
        """Create RateLimitMiddleware instance."""
        rate_limiter = TokenBucketRateLimiter("redis://localhost:6379/0")
        return RateLimitMiddleware(rate_limiter)

    @pytest.fixture
    def mock_request(self):
        """Mock FastAPI Request object."""
        request = MagicMock()
        request.client.host = "127.0.0.1"
        request.url.path = "/api/v1/instruments"
        return request

    @pytest.mark.asyncio
    async def test_check_request_allowed(self, rate_limit_middleware, mock_request):
        """Test middleware check when request is allowed."""
        limit_type = "authenticated"

        with patch.object(rate_limit_middleware.rate_limiter, 'check_rate_limit', new_callable=AsyncMock) as mock_check:
            mock_check.return_value = {
                "allowed": True,
                "current_count": 5,
                "limit": 1000,
                "reset_in_seconds": 45
            }

            result = await rate_limit_middleware.check_request(mock_request, limit_type)

            assert result["allowed"] is True
            assert result["current_count"] == 5
            assert result["limit"] == 1000

    @pytest.mark.asyncio
    async def test_check_request_blocked(self, rate_limit_middleware, mock_request):
        """Test middleware check when request is blocked."""
        limit_type = "authenticated"

        with patch.object(rate_limit_middleware.rate_limiter, 'check_rate_limit', new_callable=AsyncMock) as mock_check:
            mock_check.return_value = {
                "allowed": False,
                "current_count": 1000,
                "limit": 1000,
                "reset_in_seconds": 30
            }

            result = await rate_limit_middleware.check_request(mock_request, limit_type)

            assert result["allowed"] is False
            assert result["current_count"] == 1000
            assert result["limit"] == 1000

    @pytest.mark.asyncio
    async def test_check_request_different_endpoints(self, rate_limit_middleware):
        """Test middleware check for different endpoints."""
        endpoints = [
            ("/api/v1/instruments", "authenticated"),
            ("/api/v1/curves", "authenticated"),
            ("/api/v1/cache/warm", "admin"),
            ("/health", "public")
        ]

        for endpoint, limit_type in endpoints:
            request = MagicMock()
            request.client.host = "127.0.0.1"
            request.url.path = endpoint

            with patch.object(rate_limit_middleware.rate_limiter, 'check_rate_limit', new_callable=AsyncMock) as mock_check:
                mock_check.return_value = {
                    "allowed": True,
                    "current_count": 1,
                    "limit": 1000,
                    "reset_in_seconds": 60
                }

                result = await rate_limit_middleware.check_request(request, limit_type)

                assert result["allowed"] is True
                mock_check.assert_called_with("127.0.0.1", endpoint, limit_type)

    @pytest.mark.asyncio
    async def test_check_request_error_handling(self, rate_limit_middleware, mock_request):
        """Test middleware error handling."""
        limit_type = "authenticated"

        with patch.object(rate_limit_middleware.rate_limiter, 'check_rate_limit', new_callable=AsyncMock) as mock_check:
            mock_check.side_effect = Exception("Rate limiter error")

            # Should handle error gracefully and allow request
            result = await rate_limit_middleware.check_request(mock_request, limit_type)

            assert result["allowed"] is True
            assert "error" in result
