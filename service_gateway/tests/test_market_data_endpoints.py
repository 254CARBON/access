"""
Tests for the market data endpoints introduced in the Access Gateway.
"""

from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from service_gateway.app.auth import AuthContext
from service_gateway.app.market_data import TickRecord
from service_gateway.app.main import create_app
from shared.errors import AuthenticationError


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


@pytest.fixture
def service(client):
    return client.app.state.gateway_service


def _auth_context():
    return AuthContext(
        subject="user-123",
        tenant_id="tenant-1",
        roles={"marketdata:read"},
        claims={"sub": "user-123", "realm_access": {"roles": ["marketdata:read"]}},
        token="jwt-token",
    )


def test_healthz_reports_dependencies(client, service):
    service.market_data_service.check_redis = AsyncMock(return_value=True)
    service.market_data_service.check_clickhouse = AsyncMock(return_value=False)
    service.jwks_authenticator.check_health = AsyncMock(return_value="ok")

    response = client.get("/healthz")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "error"
    assert body["dependencies"]["redis"] == "ok"
    assert body["dependencies"]["clickhouse"] == "error"
    assert body["dependencies"]["jwks"] == "ok"


def test_ticks_latest_honours_cache(client, service):
    now = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    tick = TickRecord(
        tenant_id="tenant-1",
        symbol="EUA-DEC-25",
        tick_timestamp=now,
        price=49.25,
        market="EUA",
        instrument_id="EUA-DEC-25",
        volume=1000.0,
    )

    service.jwks_authenticator.authenticate = AsyncMock(return_value=_auth_context())
    service.rate_limiter.check_rate_limit = AsyncMock(
        return_value={"allowed": True, "limit": 600, "remaining": 599, "reset_in_seconds": 60}
    )
    service.market_data_service.get_latest_tick = AsyncMock(return_value=(tick, "redis"))

    response = client.get("/ticks/latest?symbol=EUA-DEC-25", headers={"Authorization": "Bearer token"})

    assert response.status_code == 200
    body = response.json()
    assert body["symbol"] == "EUA-DEC-25"
    assert body["tenant_id"] == "tenant-1"
    assert body["cached"] is True
    assert body["source"] == "redis"
    assert body["price"] == tick.price

    service.rate_limiter.check_rate_limit.assert_awaited()
    service.market_data_service.get_latest_tick.assert_awaited_with("tenant-1", "EUA-DEC-25", market=None)


def test_ticks_latest_requires_authentication(client, service):
    service.jwks_authenticator.authenticate = AsyncMock(side_effect=AuthenticationError("bad token"))

    response = client.get("/ticks/latest?symbol=EUA-DEC-25")

    assert response.status_code == 401


def test_ticks_window_returns_data(client, service):
    service.jwks_authenticator.authenticate = AsyncMock(return_value=_auth_context())
    service.rate_limiter.check_rate_limit = AsyncMock(
        return_value={"allowed": True, "limit": 600, "remaining": 598, "reset_in_seconds": 60}
    )

    start = datetime.now(timezone.utc) - timedelta(minutes=5)
    end = datetime.now(timezone.utc)

    ticks = [
        TickRecord(
            tenant_id="tenant-1",
            symbol="EUA-DEC-25",
            tick_timestamp=start.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            price=48.75,
            market="EUA",
            instrument_id="EUA-DEC-25",
            volume=500.0,
        ),
        TickRecord(
            tenant_id="tenant-1",
            symbol="EUA-DEC-25",
            tick_timestamp=end.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            price=49.95,
            market="EUA",
            instrument_id="EUA-DEC-25",
            volume=620.0,
        ),
    ]

    service.market_data_service.get_tick_window = AsyncMock(return_value=ticks)

    response = client.get(
        f"/ticks/window?symbol=EUA-DEC-25&start={start.isoformat()}&end={end.isoformat()}",
        headers={"Authorization": "Bearer token"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 2
    assert body["ticks"][0]["price"] == pytest.approx(48.75)
    assert body["source"] == "clickhouse"


def test_ticks_window_handles_empty_result(client, service):
    service.jwks_authenticator.authenticate = AsyncMock(return_value=_auth_context())
    service.rate_limiter.check_rate_limit = AsyncMock(
        return_value={"allowed": True, "limit": 600, "remaining": 597, "reset_in_seconds": 60}
    )
    service.market_data_service.get_tick_window = AsyncMock(return_value=[])

    response = client.get(
        "/ticks/window?symbol=EUA-DEC-25&start=2024-01-01T00:00:00Z&end=2024-01-01T00:05:00Z",
        headers={"Authorization": "Bearer token"},
    )

    assert response.status_code == 404


def test_ticks_latest_rate_limited(client, service):
    service.jwks_authenticator.authenticate = AsyncMock(return_value=_auth_context())
    service.rate_limiter.check_rate_limit = AsyncMock(
        return_value={"allowed": False, "limit": 600, "current_count": 601, "reset_in_seconds": 10}
    )

    response = client.get("/ticks/latest?symbol=EUA-DEC-25", headers={"Authorization": "Bearer token"})

    assert response.status_code == 429
