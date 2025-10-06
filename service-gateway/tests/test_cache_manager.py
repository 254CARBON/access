"""
Unit tests for CacheManager.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from service_gateway.app.caching.cache_manager import CacheManager


class TestCacheManager:
    """Test cases for CacheManager."""
    
    @pytest.fixture
    def cache_manager(self):
        """Create CacheManager instance."""
        with patch('service_gateway.app.caching.cache_manager.AdaptiveCache') as mock_adaptive_cache:
            mock_cache = AsyncMock()
            mock_adaptive_cache.return_value = mock_cache
            return CacheManager("redis://localhost:6379")
    
    @pytest.fixture
    def mock_instruments(self):
        """Mock instruments data."""
        return [
            {"id": "INST001", "name": "Brent Crude Oil", "type": "commodity"},
            {"id": "INST002", "name": "WTI", "type": "commodity"},
            {"id": "INST003", "name": "Natural Gas", "type": "commodity"}
        ]
    
    @pytest.fixture
    def mock_curves(self):
        """Mock curves data."""
        return [
            {"id": "CURVE001", "name": "Oil Curve", "currency": "USD"},
            {"id": "CURVE002", "name": "Gas Curve", "currency": "USD"}
        ]
    
    @pytest.fixture
    def mock_products(self):
        """Mock products data."""
        return [
            {"id": "PROD001", "name": "Oil Futures", "type": "commodity"},
            {"id": "PROD002", "name": "Gas Futures", "type": "commodity"}
        ]
    
    @pytest.fixture
    def mock_pricing(self):
        """Mock pricing data."""
        return [
            {"instrument_id": "INST001", "price": 52.50, "volume": 1000},
            {"instrument_id": "INST002", "price": 45.20, "volume": 1500}
        ]
    
    @pytest.fixture
    def mock_historical(self):
        """Mock historical data."""
        return [
            {"instrument_id": "INST001", "price": 52.50, "timestamp": "2024-01-01T12:00:00Z"},
            {"instrument_id": "INST001", "price": 52.45, "timestamp": "2024-01-01T11:00:00Z"}
        ]
    
    @pytest.mark.asyncio
    async def test_get_instruments_cache_hit(self, cache_manager, mock_instruments):
        """Test instruments retrieval with cache hit."""
        # Mock adaptive cache
        cache_manager.adaptive_cache.get = AsyncMock(return_value=mock_instruments)
        
        # Test
        result = await cache_manager.get_instruments("user1", "tenant-1")
        
        # Assertions
        assert result == mock_instruments
        cache_manager.adaptive_cache.get.assert_called_once_with("instruments", "user1:tenant-1")
    
    @pytest.mark.asyncio
    async def test_get_instruments_cache_miss(self, cache_manager):
        """Test instruments retrieval with cache miss."""
        # Mock adaptive cache
        cache_manager.adaptive_cache.get = AsyncMock(return_value=None)
        
        # Test
        result = await cache_manager.get_instruments("user1", "tenant-1")
        
        # Assertions
        assert result is None
        cache_manager.adaptive_cache.get.assert_called_once_with("instruments", "user1:tenant-1")
    
    @pytest.mark.asyncio
    async def test_set_instruments(self, cache_manager, mock_instruments):
        """Test instruments caching."""
        # Mock adaptive cache
        cache_manager.adaptive_cache.set = AsyncMock(return_value=True)
        
        # Test
        result = await cache_manager.set_instruments("user1", "tenant-1", mock_instruments)
        
        # Assertions
        assert result is True
        cache_manager.adaptive_cache.set.assert_called_once_with("instruments", mock_instruments, "user1:tenant-1")
    
    @pytest.mark.asyncio
    async def test_get_curves_cache_hit(self, cache_manager, mock_curves):
        """Test curves retrieval with cache hit."""
        # Mock adaptive cache
        cache_manager.adaptive_cache.get = AsyncMock(return_value=mock_curves)
        
        # Test
        result = await cache_manager.get_curves("user1", "tenant-1")
        
        # Assertions
        assert result == mock_curves
        cache_manager.adaptive_cache.get.assert_called_once_with("curves", "user1:tenant-1")
    
    @pytest.mark.asyncio
    async def test_set_curves(self, cache_manager, mock_curves):
        """Test curves caching."""
        # Mock adaptive cache
        cache_manager.adaptive_cache.set = AsyncMock(return_value=True)
        
        # Test
        result = await cache_manager.set_curves("user1", "tenant-1", mock_curves)
        
        # Assertions
        assert result is True
        cache_manager.adaptive_cache.set.assert_called_once_with("curves", mock_curves, "user1:tenant-1")
    
    @pytest.mark.asyncio
    async def test_get_products_cache_hit(self, cache_manager, mock_products):
        """Test products retrieval with cache hit."""
        # Mock adaptive cache
        cache_manager.adaptive_cache.get = AsyncMock(return_value=mock_products)
        
        # Test
        result = await cache_manager.get_products("user1", "tenant-1")
        
        # Assertions
        assert result == mock_products
        cache_manager.adaptive_cache.get.assert_called_once_with("products", "user1:tenant-1")
    
    @pytest.mark.asyncio
    async def test_set_products(self, cache_manager, mock_products):
        """Test products caching."""
        # Mock adaptive cache
        cache_manager.adaptive_cache.set = AsyncMock(return_value=True)
        
        # Test
        result = await cache_manager.set_products("user1", "tenant-1", mock_products)
        
        # Assertions
        assert result is True
        cache_manager.adaptive_cache.set.assert_called_once_with("products", mock_products, "user1:tenant-1")
    
    @pytest.mark.asyncio
    async def test_get_pricing_cache_hit(self, cache_manager, mock_pricing):
        """Test pricing retrieval with cache hit."""
        # Mock adaptive cache
        cache_manager.adaptive_cache.get = AsyncMock(return_value=mock_pricing)
        
        # Test
        result = await cache_manager.get_pricing("user1", "tenant-1")
        
        # Assertions
        assert result == mock_pricing
        cache_manager.adaptive_cache.get.assert_called_once_with("pricing", "user1:tenant-1")
    
    @pytest.mark.asyncio
    async def test_set_pricing(self, cache_manager, mock_pricing):
        """Test pricing caching."""
        # Mock adaptive cache
        cache_manager.adaptive_cache.set = AsyncMock(return_value=True)
        
        # Test
        result = await cache_manager.set_pricing("user1", "tenant-1", mock_pricing)
        
        # Assertions
        assert result is True
        cache_manager.adaptive_cache.set.assert_called_once_with("pricing", mock_pricing, "user1:tenant-1")
    
    @pytest.mark.asyncio
    async def test_get_historical_cache_hit(self, cache_manager, mock_historical):
        """Test historical data retrieval with cache hit."""
        # Mock adaptive cache
        cache_manager.adaptive_cache.get = AsyncMock(return_value=mock_historical)
        
        # Test
        result = await cache_manager.get_historical("user1", "tenant-1")
        
        # Assertions
        assert result == mock_historical
        cache_manager.adaptive_cache.get.assert_called_once_with("historical", "user1:tenant-1")
    
    @pytest.mark.asyncio
    async def test_set_historical(self, cache_manager, mock_historical):
        """Test historical data caching."""
        # Mock adaptive cache
        cache_manager.adaptive_cache.set = AsyncMock(return_value=True)
        
        # Test
        result = await cache_manager.set_historical("user1", "tenant-1", mock_historical)
        
        # Assertions
        assert result is True
        cache_manager.adaptive_cache.set.assert_called_once_with("historical", mock_historical, "user1:tenant-1")
    
    @pytest.mark.asyncio
    async def test_get_user_context(self, cache_manager):
        """Test user context retrieval."""
        # Mock user context
        mock_context = {"user_id": "user1", "tenant_id": "tenant-1", "roles": ["user"]}
        cache_manager.adaptive_cache.get = AsyncMock(return_value=mock_context)
        
        # Test
        result = await cache_manager.get_user_context("user1")
        
        # Assertions
        assert result == mock_context
        cache_manager.adaptive_cache.get.assert_called_once_with("user_context", "user1")
    
    @pytest.mark.asyncio
    async def test_set_user_context(self, cache_manager):
        """Test user context caching."""
        # Mock user context
        mock_context = {"user_id": "user1", "tenant_id": "tenant-1", "roles": ["user"]}
        cache_manager.adaptive_cache.set = AsyncMock(return_value=True)
        
        # Test
        result = await cache_manager.set_user_context("user1", mock_context, ttl=300)
        
        # Assertions
        assert result is True
        cache_manager.adaptive_cache.set.assert_called_once_with("user_context", mock_context, "user1", ttl=300)
    
    @pytest.mark.asyncio
    async def test_warm_cache(self, cache_manager):
        """Test cache warming."""
        # Mock adaptive cache
        cache_manager.adaptive_cache.set = AsyncMock(return_value=True)
        
        # Test
        await cache_manager.warm_cache("user1", "tenant-1")
        
        # Assertions
        assert cache_manager.adaptive_cache.set.call_count == 2  # instruments and curves
    
    @pytest.mark.asyncio
    async def test_get_cache_stats(self, cache_manager):
        """Test cache statistics retrieval."""
        # Mock adaptive cache stats
        mock_stats = {
            "total_keys": 100,
            "tracked_keys": 50,
            "pattern": "gateway:*"
        }
        cache_manager.adaptive_cache.get_stats = AsyncMock(return_value=mock_stats)
        
        # Test
        result = await cache_manager.get_cache_stats()
        
        # Assertions
        assert result["total_keys"] == 100
        assert result["tracked_keys"] == 50
        assert result["cache_types"] == ["instruments", "curves", "products", "pricing", "historical", "user_context", "rate_limit"]
        assert result["warm_cache_available"] is True
    
    @pytest.mark.asyncio
    async def test_get_cache_stats_error(self, cache_manager):
        """Test cache statistics retrieval with error."""
        # Mock adaptive cache to raise exception
        cache_manager.adaptive_cache.get_stats = AsyncMock(side_effect=Exception("Cache error"))
        
        # Test
        result = await cache_manager.get_cache_stats()
        
        # Assertions
        assert "error" in result
        assert "Cache error" in result["error"]
    
    @pytest.mark.asyncio
    async def test_clear_user_cache(self, cache_manager):
        """Test user cache clearing."""
        # Mock adaptive cache
        cache_manager.adaptive_cache.clear_pattern = AsyncMock(return_value=True)
        
        # Test
        result = await cache_manager.clear_user_cache("user1")
        
        # Assertions
        assert result is True
        assert cache_manager.adaptive_cache.clear_pattern.call_count == 2  # Two patterns
    
    @pytest.mark.asyncio
    async def test_clear_user_cache_partial_failure(self, cache_manager):
        """Test user cache clearing with partial failure."""
        # Mock adaptive cache with partial failure
        cache_manager.adaptive_cache.clear_pattern = AsyncMock(side_effect=[True, False])
        
        # Test
        result = await cache_manager.clear_user_cache("user1")
        
        # Assertions
        assert result is False
