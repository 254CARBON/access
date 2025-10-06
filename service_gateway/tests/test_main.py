"""
Unit tests for Gateway main service.
"""

import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from fastapi import FastAPI

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from service_gateway.app.main import GatewayService, create_app


class TestGatewayService:
    """Test cases for GatewayService."""

    @pytest.fixture
    def gateway_service(self):
        """Create GatewayService instance."""
        return GatewayService()

    @pytest.fixture
    def app(self):
        """Create FastAPI app instance."""
        return create_app()

    @pytest.fixture
    def client(self, app):
        """Create test client."""
        return TestClient(app)

    @pytest.fixture
    def mock_user_info(self):
        """Mock user info."""
        return {
            "user_id": "user-123",
            "tenant_id": "tenant-1",
            "roles": ["user", "analyst"],
            "email": "test@example.com"
        }

    @pytest.fixture
    def mock_jwt_token(self):
        """Mock JWT token."""
        return "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test.signature"

    def test_root_endpoint(self, client):
        """Test root endpoint."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "gateway"
        assert data["message"] == "254Carbon Access Layer - API Gateway"

    def test_api_status_endpoint(self, client):
        """Test API status endpoint."""
        response = client.get("/api/v1/status")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "operational"
        assert "services" in data

    def test_health_endpoint(self, client):
        """Test health endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "gateway"
        assert data["status"] == "ok"

    @patch('service_gateway.app.main.GatewayService._check_dependencies')
    def test_health_with_dependencies(self, mock_check_deps, client):
        """Test health endpoint with dependency checks."""
        mock_check_deps.return_value = {
            "redis": "ok",
            "auth": "ok",
            "entitlements": "ok"
        }

        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["dependencies"]["redis"] == "ok"
        assert data["dependencies"]["auth"] == "ok"

    def test_instruments_endpoint_unauthorized(self, client):
        """Test instruments endpoint without authorization."""
        response = client.get("/api/v1/instruments")
        assert response.status_code == 401

    @patch('service_gateway.app.main.AuthMiddleware.process_request')
    @patch('service_gateway.app.main.RateLimitMiddleware.check_request')
    @patch('service_gateway.app.main.CacheManager.get_instruments')
    def test_instruments_endpoint_success(self, mock_get_cache, mock_rate_limit, mock_auth, client, mock_user_info):
        """Test instruments endpoint with successful response."""
        # Mock rate limiting
        mock_rate_limit.return_value = {
            "allowed": True,
            "current_count": 5,
            "limit": 1000,
            "reset_in_seconds": 60
        }

        # Mock authentication
        mock_auth.return_value = mock_user_info

        # Mock cache miss
        mock_get_cache.return_value = None

        headers = {"Authorization": "Bearer test-token"}
        response = client.get("/api/v1/instruments", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert "instruments" in data
        assert data["cached"] is False
        assert data["user"] == "user-123"
        assert data["tenant"] == "tenant-1"

    @patch('service_gateway.app.main.AuthMiddleware.process_request')
    @patch('service_gateway.app.main.RateLimitMiddleware.check_request')
    @patch('service_gateway.app.main.CacheManager.get_instruments')
    def test_instruments_endpoint_cache_hit(self, mock_get_cache, mock_rate_limit, mock_auth, client, mock_user_info):
        """Test instruments endpoint with cache hit."""
        # Mock rate limiting
        mock_rate_limit.return_value = {
            "allowed": True,
            "current_count": 5,
            "limit": 1000,
            "reset_in_seconds": 60
        }

        # Mock authentication
        mock_auth.return_value = mock_user_info

        # Mock cache hit
        cached_instruments = [
            {"id": "EURUSD", "name": "Euro/US Dollar", "type": "forex"}
        ]
        mock_get_cache.return_value = cached_instruments

        headers = {"Authorization": "Bearer test-token"}
        response = client.get("/api/v1/instruments", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["instruments"] == cached_instruments
        assert data["cached"] is True

    @patch('service_gateway.app.main.RateLimitMiddleware.check_request')
    def test_instruments_endpoint_rate_limited(self, mock_rate_limit, client):
        """Test instruments endpoint when rate limited."""
        # Mock rate limiting failure
        mock_rate_limit.return_value = {
            "allowed": False,
            "current_count": 1000,
            "limit": 1000,
            "reset_in_seconds": 30
        }

        headers = {"Authorization": "Bearer test-token"}
        response = client.get("/api/v1/instruments", headers=headers)

        assert response.status_code == 429
        data = response.json()
        assert data["detail"]["error"] == "Rate limit exceeded"

    def test_curves_endpoint_unauthorized(self, client):
        """Test curves endpoint without authorization."""
        response = client.get("/api/v1/curves")
        assert response.status_code == 401

    @patch('service_gateway.app.main.AuthMiddleware.process_request')
    @patch('service_gateway.app.main.RateLimitMiddleware.check_request')
    @patch('service_gateway.app.main.CacheManager.get_curves')
    def test_curves_endpoint_success(self, mock_get_cache, mock_rate_limit, mock_auth, client, mock_user_info):
        """Test curves endpoint with successful response."""
        # Mock rate limiting
        mock_rate_limit.return_value = {
            "allowed": True,
            "current_count": 5,
            "limit": 1000,
            "reset_in_seconds": 60
        }

        # Mock authentication
        mock_auth.return_value = mock_user_info

        # Mock cache miss
        mock_get_cache.return_value = None

        headers = {"Authorization": "Bearer test-token"}
        response = client.get("/api/v1/curves", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert "curves" in data
        assert data["cached"] is False

    def test_api_key_authentication_success(self, client):
        """Test API key authentication."""
        headers = {"X-API-Key": "dev-key-123"}
        response = client.get("/api/v1/auth/api-key", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["authenticated"] is True
        assert data["user_info"]["tenant_id"] == "tenant-1"
        assert "user" in data["user_info"]["roles"]

    def test_api_key_authentication_invalid(self, client):
        """Test API key authentication with invalid key."""
        headers = {"X-API-Key": "invalid-key"}
        response = client.get("/api/v1/auth/api-key", headers=headers)

        assert response.status_code == 401
        data = response.json()
        assert data["detail"] == "Invalid API key"

    def test_circuit_breakers_endpoint(self, client):
        """Test circuit breakers endpoint."""
        response = client.get("/api/v1/circuit-breakers")
        assert response.status_code == 200
        data = response.json()
        assert "circuit_breakers" in data
        assert "count" in data

    @patch('service_gateway.app.main.TokenBucketRateLimiter.get_global_stats')
    def test_rate_limits_endpoint(self, mock_get_stats, client):
        """Test rate limits endpoint."""
        mock_get_stats.return_value = {
            "total_clients": 10,
            "total_requests": 1000,
            "blocked_requests": 50
        }

        response = client.get("/api/v1/rate-limits")
        assert response.status_code == 200
        data = response.json()
        assert "rate_limits" in data
        assert "configured_limits" in data

    @patch('service_gateway.app.main.CacheManager.get_cache_stats')
    def test_cache_stats_endpoint(self, mock_get_stats, client):
        """Test cache stats endpoint."""
        mock_get_stats.return_value = {
            "hit_ratio": 0.85,
            "total_requests": 1000,
            "cache_hits": 850
        }

        response = client.get("/api/v1/cache/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["hit_ratio"] == 0.85

    def test_fallback_instruments_endpoint(self, client):
        """Test fallback instruments endpoint."""
        response = client.get("/api/v1/instruments/fallback")
        assert response.status_code == 200
        data = response.json()
        assert "instruments" in data
        assert data["fallback"] is True
        assert "message" in data

    def test_fallback_curves_endpoint(self, client):
        """Test fallback curves endpoint."""
        response = client.get("/api/v1/curves/fallback")
        assert response.status_code == 200
        data = response.json()
        assert "curves" in data
        assert data["fallback"] is True

    @patch('service_gateway.app.main.AuthMiddleware.process_request')
    @patch('service_gateway.app.main.RateLimitMiddleware.check_request')
    @patch('service_gateway.app.main.CacheManager.warm_cache')
    def test_warm_cache_endpoint(self, mock_warm_cache, mock_rate_limit, mock_auth, client, mock_user_info):
        """Test cache warming endpoint."""
        # Mock rate limiting
        mock_rate_limit.return_value = {
            "allowed": True,
            "current_count": 1,
            "limit": 5,
            "reset_in_seconds": 60
        }

        # Mock authentication
        mock_auth.return_value = mock_user_info

        # Mock cache warming
        mock_warm_cache.return_value = True

        headers = {"Authorization": "Bearer test-token"}
        response = client.post("/api/v1/cache/warm", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Cache warmed successfully"
        assert data["user"] == "user-123"

    def test_service_initialization(self, gateway_service):
        """Test service initialization."""
        assert gateway_service.name == "gateway"
        assert gateway_service.port == 8000
        assert gateway_service.auth_client is not None
        assert gateway_service.entitlements_client is not None
        assert gateway_service.cache_manager is not None
        assert gateway_service.rate_limiter is not None

    def test_observability_setup(self, gateway_service):
        """Test observability setup."""
        assert gateway_service.observability is not None
        assert hasattr(gateway_service.observability, 'log_request')
        assert hasattr(gateway_service.observability, 'log_error')
        assert hasattr(gateway_service.observability, 'log_business_event')

    def test_api_keys_configuration(self, gateway_service):
        """Test API keys configuration."""
        assert "dev-key-123" in gateway_service.api_keys
        assert "admin-key-456" in gateway_service.api_keys
        assert "service-key-789" in gateway_service.api_keys

        dev_key_info = gateway_service.api_keys["dev-key-123"]
        assert dev_key_info["tenant_id"] == "tenant-1"
        assert "user" in dev_key_info["roles"]

    @patch('service_gateway.app.main.GatewayService._check_dependencies')
    def test_dependency_checks(self, mock_check_deps, gateway_service):
        """Test dependency checks."""
        mock_check_deps.return_value = {
            "redis": "ok",
            "auth": "ok",
            "entitlements": "ok"
        }

        dependencies = gateway_service._check_dependencies()
        assert dependencies["redis"] == "ok"
        assert dependencies["auth"] == "ok"
        assert dependencies["entitlements"] == "ok"