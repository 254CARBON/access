"""
Tests for Gateway service.
"""

import types
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock
import sys
import os

# Add service directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'service_gateway', 'app'))


# Provide lightweight stubs for optional scenario clients used by the gateway during tests.
scenario_pkg = types.ModuleType("scenario")
sys.modules.setdefault("scenario", scenario_pkg)

scenario_der = types.ModuleType("scenario.der_client")


class _StubDERServiceClient:
    def __init__(self, *args, **kwargs):
        pass


scenario_der.DERServiceClient = _StubDERServiceClient
sys.modules["scenario.der_client"] = scenario_der
scenario_pkg.der_client = scenario_der

scenario_exceptions = types.ModuleType("scenario.exceptions")


class _ScenarioServiceError(Exception):
    pass


scenario_exceptions.ScenarioServiceError = _ScenarioServiceError
sys.modules["scenario.exceptions"] = scenario_exceptions
scenario_pkg.exceptions = scenario_exceptions

scenario_irp = types.ModuleType("scenario.irp_client")


class _StubIRPCaseClient:
    def __init__(self, *args, **kwargs):
        pass


scenario_irp.IRPCaseClient = _StubIRPCaseClient
sys.modules["scenario.irp_client"] = scenario_irp
scenario_pkg.irp_client = scenario_irp

from service_gateway.app.main import create_app


@pytest.fixture
def client():
    """Create test client."""
    app = create_app()
    return TestClient(app)


def test_root_endpoint(client):
    """Test root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "gateway"
    assert data["version"] == "1.0.0"


def test_health_check(client):
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "gateway"
    assert data["status"] == "ok"


def test_api_status(client):
    """Test API status endpoint."""
    response = client.get("/api/v1/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "operational"
    assert "services" in data


def test_metrics_endpoint(client):
    """Test metrics endpoint."""
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]


def test_routes_metadata_endpoint(client):
    """Gateway exposes route metadata catalog."""
    service = client.app.state.gateway_service
    service.auth_middleware.authenticate_request = AsyncMock(return_value=_mock_user_context())

    response = client.get(
        "/api/v1/metadata/routes",
        headers={"Authorization": "Bearer token"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] > 0
    assert any(route["path"] == "/api/v1/status" for route in payload["routes"])


def test_cache_catalog_endpoint(client):
    """Gateway exposes cache catalog metadata."""
    response = client.get("/api/v1/cache/catalog")
    assert response.status_code == 200
    data = response.json()
    catalog = data["cache_catalog"]
    assert "served_latest_price" in catalog
    assert "default_ttl_seconds" in catalog["served_latest_price"]


def _mock_rate_limit_ok():
    return {
        "allowed": True,
        "current_count": 1,
        "limit": 1000,
        "reset_in_seconds": 60
    }


def _mock_user_context():
    return {
        "user_id": "user-123",
        "tenant_id": "tenant-1",
        "roles": ["trader"]
    }


def test_get_served_latest_price_success(client):
    """Gateway returns served latest price when cache misses."""
    service = client.app.state.gateway_service

    service.rate_limit_middleware.check_request = AsyncMock(return_value=_mock_rate_limit_ok())
    service.auth_middleware.process_request = AsyncMock(return_value=_mock_user_context())
    service.cache_manager.get_served_latest_price = AsyncMock(return_value=None)
    service.cache_manager.set_served_latest_price = AsyncMock(return_value=True)

    projection = {
        "projection_type": "latest_price",
        "instrument_id": "INST-1",
        "data": {"price": 101.25},
        "tenant_id": "tenant-1"
    }
    service.served_client.get_latest_price = AsyncMock(return_value=projection)

    response = client.get(
        "/api/v1/served/latest-price/inst-1",
        headers={"Authorization": "Bearer fake-token"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["projection"] == projection
    assert body["cached"] is False
    service.served_client.get_latest_price.assert_awaited_with("tenant-1", "INST-1")
    service.cache_manager.set_served_latest_price.assert_awaited()


def test_get_served_latest_price_not_found(client):
    """Gateway propagates 404 when served data missing."""
    service = client.app.state.gateway_service

    service.rate_limit_middleware.check_request = AsyncMock(return_value=_mock_rate_limit_ok())
    service.auth_middleware.process_request = AsyncMock(return_value=_mock_user_context())
    service.cache_manager.get_served_latest_price = AsyncMock(return_value=None)
    service.served_client.get_latest_price = AsyncMock(return_value=None)

    response = client.get(
        "/api/v1/served/latest-price/inst-404",
        headers={"Authorization": "Bearer fake-token"}
    )

    assert response.status_code == 404
    service.served_client.get_latest_price.assert_awaited_with("tenant-1", "INST-404")


def test_get_served_curve_snapshot_success(client):
    """Gateway returns served curve snapshot when available."""
    service = client.app.state.gateway_service

    service.rate_limit_middleware.check_request = AsyncMock(return_value=_mock_rate_limit_ok())
    service.auth_middleware.process_request = AsyncMock(return_value=_mock_user_context())
    service.cache_manager.get_served_curve_snapshot = AsyncMock(return_value=None)
    service.cache_manager.set_served_curve_snapshot = AsyncMock(return_value=True)

    projection = {
        "projection_type": "curve_snapshot",
        "instrument_id": "INST-2",
        "data": {"horizon": "1m", "points": []},
        "tenant_id": "tenant-1"
    }
    service.served_client.get_curve_snapshot = AsyncMock(return_value=projection)

    response = client.get(
        "/api/v1/served/curve-snapshots/INST-2?horizon=1M",
        headers={"Authorization": "Bearer fake-token"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["projection"] == projection
    assert data["horizon"] == "1m"
    service.served_client.get_curve_snapshot.assert_awaited_with("tenant-1", "INST-2", "1m")
