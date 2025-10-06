"""
Tests for Auth service.
"""

import pytest
from fastapi.testclient import TestClient
import sys
import os

# Add shared directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from service_auth.app.main import create_app


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
    assert data["service"] == "auth"
    assert data["version"] == "1.0.0"


def test_health_check(client):
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "auth"
    assert data["status"] == "ok"


def test_verify_token_endpoint(client):
    """Test token verification endpoint placeholder."""
    response = client.post("/auth/verify")
    assert response.status_code == 200
    data = response.json()
    assert "Token verification" in data["message"]


def test_verify_websocket_token_endpoint(client):
    """Test WebSocket token verification endpoint placeholder."""
    response = client.post("/auth/verify-ws")
    assert response.status_code == 200
    data = response.json()
    assert "WebSocket token verification" in data["message"]
