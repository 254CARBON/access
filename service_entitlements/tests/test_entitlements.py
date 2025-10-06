"""
Tests for Entitlements service.
"""

import pytest
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


def test_root_endpoint(client):
    """Test root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "entitlements"
    assert data["version"] == "1.0.0"


def test_health_check(client):
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "entitlements"
    assert data["status"] == "ok"


def test_check_entitlements_endpoint(client):
    """Test entitlements check endpoint placeholder."""
    response = client.post("/entitlements/check")
    assert response.status_code == 200
    data = response.json()
    assert "Entitlements check" in data["message"]


def test_get_rules_endpoint(client):
    """Test get rules endpoint placeholder."""
    response = client.get("/entitlements/rules")
    assert response.status_code == 200
    data = response.json()
    assert "Get entitlement rules" in data["message"]
