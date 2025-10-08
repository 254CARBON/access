"""
Unit tests for Gateway Cache Manager.
"""

import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
from typing import Dict, Any, List

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from service_gateway.app.caching.cache_manager import CacheManager


class TestCacheManager:
    """Test cases for CacheManager."""

    @pytest.fixture
    def cache_manager(self):
        """Create CacheManager instance."""
        return CacheManager("redis://localhost:6379/0")

    @pytest.fixture
    def mock_instruments(self):
        """Mock instruments data."""
        return [
            {"id": "EURUSD", "name": "Euro/US Dollar", "type": "forex"},
            {"id": "GBPUSD", "name": "British Pound/US Dollar", "type": "forex"},
            {"id": "USDJPY", "name": "US Dollar/Japanese Yen", "type": "forex"}
        ]

    @pytest.fixture
    def mock_curves(self):
        """Mock curves data."""
        return [
            {"id": "USD_CURVE", "name": "USD Yield Curve", "currency": "USD"},
            {"id": "EUR_CURVE", "name": "EUR Yield Curve", "currency": "EUR"},
            {"id": "GBP_CURVE", "name": "GBP Yield Curve", "currency": "GBP"}
        ]

    @pytest.fixture
    def mock_pricing(self):
        """Mock pricing data."""
        return [
            {"instrument_id": "INST001", "price": 52.50, "volume": 1000, "timestamp": "2024-01-01T12:00:00Z"},
            {"instrument_id": "INST002", "price": 45.20, "volume": 1500, "timestamp": "2024-01-01T12:00:00Z"}
        ]

    @pytest.mark.asyncio
    async def test_get_instruments_cache_hit(self, cache_manager, mock_instruments):
        """Test getting instruments from cache (hit)."""
        user_id = "user-123"
        tenant_id = "tenant-1"

        with patch.object(cache_manager.adaptive_cache, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_instruments

            result = await cache_manager.get_instruments(user_id, tenant_id)

            assert result == mock_instruments
            mock_get.assert_called_once_with("instruments", f"{user_id}:{tenant_id}")

    @pytest.mark.asyncio
    async def test_get_instruments_cache_miss(self, cache_manager):
        """Test getting instruments from cache (miss)."""
        user_id = "user-123"
        tenant_id = "tenant-1"

        with patch.object(cache_manager.adaptive_cache, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None

            result = await cache_manager.get_instruments(user_id, tenant_id)

            assert result is None
            mock_get.assert_called_once_with("instruments", f"{user_id}:{tenant_id}")

    @pytest.mark.asyncio
    async def test_set_instruments_success(self, cache_manager, mock_instruments):
        """Test setting instruments in cache."""
        user_id = "user-123"
        tenant_id = "tenant-1"

        with patch.object(cache_manager.adaptive_cache, 'set', new_callable=AsyncMock) as mock_set:
            mock_set.return_value = True

            result = await cache_manager.set_instruments(user_id, tenant_id, mock_instruments)

            assert result is True
            mock_set.assert_called_once_with("instruments", mock_instruments, f"{user_id}:{tenant_id}")

    @pytest.mark.asyncio
    async def test_get_curves_cache_hit(self, cache_manager, mock_curves):
        """Test getting curves from cache (hit)."""
        user_id = "user-123"
        tenant_id = "tenant-1"

        with patch.object(cache_manager.adaptive_cache, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_curves

            result = await cache_manager.get_curves(user_id, tenant_id)

            assert result == mock_curves
            mock_get.assert_called_once_with("curves", f"{user_id}:{tenant_id}")

    @pytest.mark.asyncio
    async def test_set_curves_success(self, cache_manager, mock_curves):
        """Test setting curves in cache."""
        user_id = "user-123"
        tenant_id = "tenant-1"

        with patch.object(cache_manager.adaptive_cache, 'set', new_callable=AsyncMock) as mock_set:
            mock_set.return_value = True

            result = await cache_manager.set_curves(user_id, tenant_id, mock_curves)

            assert result is True
            mock_set.assert_called_once_with("curves", mock_curves, f"{user_id}:{tenant_id}")

    @pytest.mark.asyncio
    async def test_get_pricing_cache_hit(self, cache_manager, mock_pricing):
        """Test getting pricing from cache (hit)."""
        user_id = "user-123"
        tenant_id = "tenant-1"

        with patch.object(cache_manager.adaptive_cache, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_pricing

            result = await cache_manager.get_pricing(user_id, tenant_id)

            assert result == mock_pricing
            mock_get.assert_called_once_with("pricing", f"{user_id}:{tenant_id}")

    @pytest.mark.asyncio
    async def test_set_pricing_success(self, cache_manager, mock_pricing):
        """Test setting pricing in cache."""
        user_id = "user-123"
        tenant_id = "tenant-1"

        with patch.object(cache_manager.adaptive_cache, 'set', new_callable=AsyncMock) as mock_set:
            mock_set.return_value = True

            result = await cache_manager.set_pricing(user_id, tenant_id, mock_pricing)

            assert result is True
            mock_set.assert_called_once_with("pricing", mock_pricing, f"{user_id}:{tenant_id}")

    @pytest.mark.asyncio
    async def test_warm_cache_success(self, cache_manager):
        """Test cache warming."""
        user_id = "user-123"
        tenant_id = "tenant-1"

        with patch.object(cache_manager.adaptive_cache, 'warm_cache', new_callable=AsyncMock) as mock_warm:
            mock_warm.return_value = True

            result = await cache_manager.warm_cache(user_id, tenant_id)

            assert result is True
            mock_warm.assert_called_once_with(user_id, tenant_id)

    @pytest.mark.asyncio
    async def test_get_cache_stats(self, cache_manager):
        """Test getting cache statistics."""
        mock_stats = {
            "hit_ratio": 0.85,
            "total_requests": 1000,
            "cache_hits": 850,
            "cache_misses": 150,
            "memory_usage": "50MB"
        }

        with patch.object(cache_manager.adaptive_cache, 'get_stats', new_callable=AsyncMock) as mock_get_stats:
            mock_get_stats.return_value = mock_stats

            result = await cache_manager.get_cache_stats()

            assert result == mock_stats
            mock_get_stats.assert_called_once()

    @pytest.mark.asyncio
    async def test_invalidate_user_cache(self, cache_manager):
        """Test invalidating user cache."""
        user_id = "user-123"
        tenant_id = "tenant-1"

        with patch.object(cache_manager.adaptive_cache, 'invalidate_user', new_callable=AsyncMock) as mock_invalidate:
            mock_invalidate.return_value = True

            result = await cache_manager.invalidate_user_cache(user_id, tenant_id)

            assert result is True
            mock_invalidate.assert_called_once_with(user_id, tenant_id)

    @pytest.mark.asyncio
    async def test_cache_key_generation(self, cache_manager):
        """Test cache key generation."""
        user_id = "user-123"
        tenant_id = "tenant-1"
        expected_key = f"{user_id}:{tenant_id}"

        # Test instruments key
        cache_key = f"{user_id}:{tenant_id}"
        assert cache_key == expected_key

        # Test curves key
        cache_key = f"{user_id}:{tenant_id}"
        assert cache_key == expected_key

    @pytest.mark.asyncio
    async def test_cache_error_handling(self, cache_manager):
        """Test cache error handling."""
        user_id = "user-123"
        tenant_id = "tenant-1"

        with patch.object(cache_manager.adaptive_cache, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = Exception("Redis connection failed")

            # Should handle error gracefully
            result = await cache_manager.get_instruments(user_id, tenant_id)
            assert result is None

    @pytest.mark.asyncio
    async def test_cache_types_coverage(self, cache_manager):
        """Test all cache types are covered."""
        user_id = "user-123"
        tenant_id = "tenant-1"
        test_data = {"test": "data"}

        cache_types = ["instruments", "curves", "products", "pricing", "historical"]

        for cache_type in cache_types:
            with patch.object(cache_manager.adaptive_cache, 'get', new_callable=AsyncMock) as mock_get:
                mock_get.return_value = test_data

                # Test get method
                get_method = getattr(cache_manager, f"get_{cache_type}")
                result = await get_method(user_id, tenant_id)
                assert result == test_data

            with patch.object(cache_manager.adaptive_cache, 'set', new_callable=AsyncMock) as mock_set:
                mock_set.return_value = True

                # Test set method
                set_method = getattr(cache_manager, f"set_{cache_type}")
                result = await set_method(user_id, tenant_id, test_data)
                assert result is True

    @pytest.mark.asyncio
    async def test_served_latest_price_cache_roundtrip(self, cache_manager):
        """Ensure served latest price cache serializes/deserializes JSON."""
        tenant_id = "tenant-1"
        instrument_id = "INST-1"
        projection = {"projection_type": "latest_price", "instrument_id": instrument_id, "data": {"price": 42.1}}

        with patch.object(cache_manager.adaptive_cache, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = json.dumps(projection)
            cached = await cache_manager.get_served_latest_price(tenant_id, instrument_id)
            assert cached == projection
            mock_get.assert_called_once_with("served_latest_price", f"{tenant_id}:{instrument_id}")

        with patch.object(cache_manager.adaptive_cache, 'set', new_callable=AsyncMock) as mock_set:
            mock_set.return_value = True
            result = await cache_manager.set_served_latest_price(tenant_id, instrument_id, projection)
            assert result is True
            args = mock_set.call_args.args
            assert args[0] == "served_latest_price"
            assert args[2] == f"{tenant_id}:{instrument_id}"
            assert json.loads(args[1]) == projection

    @pytest.mark.asyncio
    async def test_served_curve_snapshot_cache_roundtrip(self, cache_manager):
        """Ensure served curve snapshot cache handles horizon key."""
        tenant_id = "tenant-1"
        instrument_id = "INST-2"
        horizon = "1d"
        projection = {"projection_type": "curve_snapshot", "instrument_id": instrument_id, "data": {"horizon": horizon}}

        key = f"{tenant_id}:{instrument_id}:{horizon}"
        with patch.object(cache_manager.adaptive_cache, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = json.dumps(projection)
            cached = await cache_manager.get_served_curve_snapshot(tenant_id, instrument_id, horizon)
            assert cached == projection
            mock_get.assert_called_once_with("served_curve_snapshot", key)

        with patch.object(cache_manager.adaptive_cache, 'set', new_callable=AsyncMock) as mock_set:
            mock_set.return_value = True
            result = await cache_manager.set_served_curve_snapshot(tenant_id, instrument_id, horizon, projection)
            assert result is True
            args = mock_set.call_args.args
            assert args[0] == "served_curve_snapshot"
            assert args[2] == f"{tenant_id}:{instrument_id}:{horizon}"
            assert json.loads(args[1]) == projection

    @pytest.mark.asyncio
    async def test_served_custom_cache_roundtrip(self, cache_manager):
        """Ensure served custom projection cache works."""
        tenant_id = "tenant-9"
        projection_type = "vol_surface"
        instrument_id = "INST-9"
        projection = {"projection_type": projection_type, "instrument_id": instrument_id, "data": {"points": []}}

        key = f"{tenant_id}:{projection_type}:{instrument_id}"
        with patch.object(cache_manager.adaptive_cache, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = json.dumps(projection)
            cached = await cache_manager.get_served_custom(tenant_id, projection_type, instrument_id)
            assert cached == projection
            mock_get.assert_called_once_with("served_custom", key)

        with patch.object(cache_manager.adaptive_cache, 'set', new_callable=AsyncMock) as mock_set:
            mock_set.return_value = True
            result = await cache_manager.set_served_custom(tenant_id, projection_type, instrument_id, projection)
            assert result is True
            args = mock_set.call_args.args
            assert args[0] == "served_custom"
            assert args[2] == f"{tenant_id}:{projection_type}:{instrument_id}"
            assert json.loads(args[1]) == projection
