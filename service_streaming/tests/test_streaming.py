"""
Tests for Streaming service.
"""

import pytest
from fastapi.testclient import TestClient
import sys
import os

# Add service directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from service_streaming.app.main import create_app


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
    assert data["service"] == "streaming"
    assert data["version"] == "1.0.0"


def test_health_check(client):
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "streaming"
    assert data["status"] == "ok"


def test_websocket_endpoint(client):
    """Test WebSocket endpoint placeholder."""
    response = client.get("/ws/stream")
    assert response.status_code == 200
    data = response.json()
    assert "WebSocket endpoint" in data["message"]


def test_sse_endpoint(client):
    """Test SSE endpoint placeholder."""
    response = client.get("/sse/stream")
    assert response.status_code == 200
    data = response.json()
    assert "SSE endpoint" in data["message"]
