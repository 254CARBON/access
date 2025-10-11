"""
Tests for reporting routes in the gateway service.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch
import json

from app.main import GatewayService


@pytest.fixture
def mock_reporting_service():
    """Mock reporting service for testing."""
    service = MagicMock()
    service.list_templates = AsyncMock(return_value=[
        {
            "template_id": "irp_caiso_standard",
            "template_name": "CAISO Standard IRP Report",
            "report_type": "irp",
            "jurisdictions": ["CA", "CAISO"],
            "document_format": "docx",
            "template_engine": "jinja2",
            "created_at": "2024-01-15T00:00:00Z",
            "updated_at": "2024-01-15T00:00:00Z",
            "version": "1.0.0",
            "author": "254Carbon Platform Team"
        }
    ])
    service.enqueue_report = AsyncMock(return_value="test-report-id-123")
    service.get_report_status = AsyncMock(return_value={
        "report_id": "test-report-id-123",
        "status": "completed",
        "created_at": "2024-01-15T00:00:00Z",
        "download_url": "http://minio:9000/reports/test-report-id-123.docx",
        "file_size_bytes": 1024000
    })
    service.get_download_url = AsyncMock(return_value={
        "report_id": "test-report-id-123",
        "download_url": "http://minio:9000/reports/test-report-id-123.docx",
        "expires_at": "2024-01-16T00:00:00Z"
    })
    return service


@pytest.fixture
def client(mock_reporting_service):
    """Test client with mocked dependencies."""
    with patch('app.main.GatewayService') as mock_service_class:
        mock_service = MagicMock()
        mock_service.reporting_service = mock_reporting_service
        mock_service.app = MagicMock()
        
        # Create actual FastAPI app
        from app.main import create_app
        app = create_app()
        
        # Patch the service instance
        app.state.gateway_service = mock_service
        
        return TestClient(app)


class TestReportingRoutes:
    """Test cases for reporting API endpoints."""

    def test_list_templates_success(self, client, mock_reporting_service):
        """Test successful template listing."""
        response = client.get("/reports/templates")
        
        assert response.status_code == 200
        data = response.json()
        assert "templates" in data
        assert len(data["templates"]) == 1
        assert data["templates"][0]["template_id"] == "irp_caiso_standard"
        
        mock_reporting_service.list_templates.assert_called_once_with(
            report_type=None, jurisdiction=None
        )

    def test_list_templates_with_filters(self, client, mock_reporting_service):
        """Test template listing with filters."""
        response = client.get("/reports/templates?report_type=irp&jurisdiction=CA")
        
        assert response.status_code == 200
        mock_reporting_service.list_templates.assert_called_once_with(
            report_type="irp", jurisdiction="CA"
        )

    def test_generate_report_success(self, client, mock_reporting_service):
        """Test successful report generation."""
        report_request = {
            "report_type": "irp",
            "jurisdiction": "CA",
            "reporting_period": {
                "start_date": "2024-01-01",
                "end_date": "2024-12-31"
            },
            "case_ids": ["case-123"],
            "format_options": {
                "include_executive_summary": True,
                "include_appendices": True
            }
        }
        
        response = client.post(
            "/reports/generate",
            json=report_request,
            headers={"x-subject": "test-user"}
        )
        
        assert response.status_code == 202
        data = response.json()
        assert data["report_id"] == "test-report-id-123"
        assert data["status"] == "queued"
        
        mock_reporting_service.enqueue_report.assert_called_once()

    def test_generate_report_missing_fields(self, client):
        """Test report generation with missing required fields."""
        report_request = {
            "report_type": "irp"
            # Missing jurisdiction and reporting_period
        }
        
        response = client.post(
            "/reports/generate",
            json=report_request,
            headers={"x-subject": "test-user"}
        )
        
        assert response.status_code == 400

    def test_get_report_status_success(self, client, mock_reporting_service):
        """Test successful report status retrieval."""
        response = client.get("/reports/test-report-id-123")
        
        assert response.status_code == 200
        data = response.json()
        assert data["report_id"] == "test-report-id-123"
        assert data["status"] == "completed"
        
        mock_reporting_service.get_report_status.assert_called_once_with("test-report-id-123")

    def test_get_report_status_not_found(self, client, mock_reporting_service):
        """Test report status retrieval for non-existent report."""
        mock_reporting_service.get_report_status.return_value = None
        
        response = client.get("/reports/non-existent-id")
        
        assert response.status_code == 404
        data = response.json()
        assert "error" in data["detail"]

    def test_download_report_success(self, client, mock_reporting_service):
        """Test successful report download."""
        response = client.get("/reports/test-report-id-123/download")
        
        assert response.status_code == 200
        data = response.json()
        assert data["report_id"] == "test-report-id-123"
        assert "download_url" in data
        
        mock_reporting_service.get_download_url.assert_called_once_with("test-report-id-123")

    def test_download_report_not_available(self, client, mock_reporting_service):
        """Test report download when report is not available."""
        mock_reporting_service.get_download_url.return_value = None
        
        response = client.get("/reports/test-report-id-123/download")
        
        assert response.status_code == 404
        data = response.json()
        assert "error" in data["detail"]


class TestReportingOpenAPISpec:
    """Test OpenAPI specification alignment."""

    def test_openapi_spec_exists(self):
        """Test that OpenAPI spec file exists and is valid."""
        import os
        spec_path = "/home/m/254/carbon/specs/openapi/reports-api/1.0.0/openapi.yaml"
        assert os.path.exists(spec_path)

    def test_openapi_spec_structure(self):
        """Test OpenAPI spec has required components."""
        import yaml
        spec_path = "/home/m/254/carbon/specs/openapi/reports-api/1.0.0/openapi.yaml"
        
        with open(spec_path, 'r') as f:
            spec = yaml.safe_load(f)
        
        # Check basic structure
        assert "openapi" in spec
        assert "info" in spec
        assert "paths" in spec
        assert "components" in spec
        
        # Check required paths
        paths = spec["paths"]
        assert "/reports/generate" in paths
        assert "/reports/{reportId}" in paths
        assert "/reports/{reportId}/download" in paths
        assert "/templates" in paths
        
        # Check required schemas
        schemas = spec["components"]["schemas"]
        assert "ReportRequest" in schemas
        assert "ReportResponse" in schemas
        assert "ReportTemplateResponse" in schemas
        assert "ErrorResponse" in schemas

    def test_openapi_spec_endpoints(self):
        """Test that all required endpoints are defined."""
        import yaml
        spec_path = "/home/m/254/carbon/specs/openapi/reports-api/1.0.0/openapi.yaml"
        
        with open(spec_path, 'r') as f:
            spec = yaml.safe_load(f)
        
        paths = spec["paths"]
        
        # Test POST /reports/generate
        assert "post" in paths["/reports/generate"]
        post_spec = paths["/reports/generate"]["post"]
        assert post_spec["operationId"] == "generateReport"
        assert "requestBody" in post_spec
        assert "responses" in post_spec
        assert "201" in post_spec["responses"]
        assert "400" in post_spec["responses"]
        
        # Test GET /reports/{reportId}
        assert "get" in paths["/reports/{reportId}"]
        get_spec = paths["/reports/{reportId}"]["get"]
        assert get_spec["operationId"] == "getReportStatus"
        assert "parameters" in get_spec
        assert "responses" in get_spec
        assert "200" in get_spec["responses"]
        assert "404" in get_spec["responses"]
        
        # Test GET /reports/{reportId}/download
        assert "get" in paths["/reports/{reportId}/download"]
        download_spec = paths["/reports/{reportId}/download"]["get"]
        assert download_spec["operationId"] == "downloadReport"
        assert "responses" in download_spec
        assert "200" in download_spec["responses"]
        assert "404" in download_spec["responses"]
        
        # Test GET /templates
        assert "get" in paths["/templates"]
        templates_spec = paths["/templates"]["get"]
        assert templates_spec["operationId"] == "listTemplates"
        assert "responses" in templates_spec
        assert "200" in templates_spec["responses"]


if __name__ == "__main__":
    pytest.main([__file__])
