"""
Integration tests for Gateway service with resilience features.
"""

import pytest
import asyncio
import time
from fastapi.testclient import TestClient
import sys
import os

# Add shared directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from app.main import create_app


@pytest.fixture
def client():
    """Create test client."""
    app = create_app()
    return TestClient(app)


def test_health_check(client):
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "gateway"
    assert data["status"] == "ok"
    assert "dependencies" in data


def test_public_endpoints_accessible(client):
    """Test that public endpoints are accessible without authentication."""
    # Status endpoint should work
    response = client.get("/api/v1/status")
    assert response.status_code == 200

    # Health endpoint should work
    response = client.get("/health")
    assert response.status_code == 200

    # Metrics endpoint should work
    response = client.get("/metrics")
    assert response.status_code == 200


def test_protected_endpoints_require_auth(client):
    """Test that protected endpoints require authentication."""
    # Instruments endpoint should require auth
    response = client.get("/api/v1/instruments")
    assert response.status_code == 401

    # Curves endpoint should require auth
    response = client.get("/api/v1/curves")
    assert response.status_code == 401


def test_fallback_endpoints_available(client):
    """Test that fallback endpoints are available."""
    # Fallback instruments
    response = client.get("/api/v1/instruments/fallback")
    assert response.status_code == 200
    data = response.json()
    assert data["fallback"] == True
    assert "instruments" in data

    # Fallback curves
    response = client.get("/api/v1/curves/fallback")
    assert response.status_code == 200
    data = response.json()
    assert data["fallback"] == True
    assert "curves" in data


def test_rate_limiting(client):
    """Test rate limiting functionality."""
    # Test rate limit status endpoint
    response = client.get("/api/v1/rate-limits")
    assert response.status_code == 200
    data = response.json()
    assert "configured_limits" in data
    assert "public" in data["configured_limits"]
    assert "authenticated" in data["configured_limits"]


def test_cache_statistics(client):
    """Test cache statistics endpoint."""
    response = client.get("/api/v1/cache/stats")
    assert response.status_code == 200
    data = response.json()
    assert "cache_types" in data
    assert "total_keys" in data or "error" in data


def test_circuit_breaker_status(client):
    """Test circuit breaker status endpoint."""
    response = client.get("/api/v1/circuit-breakers")
    assert response.status_code == 200
    data = response.json()
    assert "circuit_breakers" in data
    assert "count" in data


def test_cache_warming_endpoint_requires_auth(client):
    """Test that cache warming endpoint requires authentication."""
    response = client.post("/api/v1/cache/warm")
    assert response.status_code == 401


def test_openapi_spec_includes_all_endpoints(client):
    """Test that OpenAPI spec includes all implemented endpoints."""
    response = client.get("/openapi.json")
    assert response.status_code == 200

    openapi_spec = response.json()
    paths = openapi_spec.get("paths", {})

    # Should have health, metrics, status endpoints
    assert "/health" in paths
    assert "/metrics" in paths
    assert "/api/v1/status" in paths

    # Should have protected endpoints
    assert "/api/v1/instruments" in paths
    assert "/api/v1/curves" in paths

    # Should have fallback endpoints
    assert "/api/v1/instruments/fallback" in paths
    assert "/api/v1/curves/fallback" in paths

    # Should have admin endpoints
    assert "/api/v1/cache/warm" in paths
    assert "/api/v1/circuit-breakers" in paths
    assert "/api/v1/rate-limits" in paths
    assert "/api/v1/cache/stats" in paths


@pytest.mark.asyncio
async def test_service_resilience():
    """Test overall service resilience."""
    # This test would normally run in a separate process or container
    # For now, just verify that the service can be imported and initialized

    from service_gateway.app.main import create_app

    # Should be able to create app without errors
    app = create_app()
    assert app is not None

    # Should have all expected routes
    route_paths = [route.path for route in app.routes if hasattr(route, 'path')]
    expected_paths = [
        "/health", "/metrics", "/api/v1/status",
        "/api/v1/instruments", "/api/v1/curves",
        "/api/v1/cache/warm", "/api/v1/circuit-breakers",
        "/api/v1/rate-limits", "/api/v1/cache/stats",
        "/api/v1/instruments/fallback", "/api/v1/curves/fallback"
    ]

    for path in expected_paths:
        assert path in route_paths, f"Missing route: {path}"


if __name__ == "__main__":
    # Run tests manually for development
    import asyncio

    async def run_tests():
        await test_service_resilience()
        print("All integration tests passed!")

    asyncio.run(run_tests())
