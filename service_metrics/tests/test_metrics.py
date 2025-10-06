"""
Tests for Metrics service.
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
    assert data["service"] == "metrics"
    assert data["version"] == "1.0.0"


def test_health_check(client):
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "metrics"
    assert data["status"] == "ok"


def test_track_metric_endpoint(client):
    """Test metric tracking endpoint placeholder."""
    response = client.post("/metrics/track")
    assert response.status_code == 200
    data = response.json()
    assert "Metric tracking" in data["message"]


def test_export_metrics_endpoint(client):
    """Test metrics export endpoint placeholder."""
    response = client.get("/metrics/export")
    assert response.status_code == 200
    data = response.json()
    assert "Metrics export" in data["message"]
