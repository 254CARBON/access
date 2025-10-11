"""
Tests for Task Manager service.
"""

import json
import os
import sys
import uuid
from datetime import datetime, timezone
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# Add service directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(os.path.join(os.path.dirname(__file__), '.'))

from app.main import TaskManagerService, RFTPRequest, TaskProposal, TaskApproval, Task


@pytest.fixture
def task_manager_service():
    """Create TaskManagerService instance for testing."""
    return TaskManagerService()


@pytest.fixture
def client(task_manager_service):
    """Test client with TaskManagerService."""
    return TestClient(task_manager_service.app)


class TestTaskManagerService:
    """Test cases for TaskManagerService."""

    def _bootstrap_task(self, client: TestClient) -> Dict[str, Any]:
        """Create an RFTP and proposal, returning workflow identifiers."""
        rftp_payload = {
            "title": "Test IRP Analysis",
            "description": "Comprehensive IRP analysis for CAISO",
            "task_type": "irp_analysis",
            "jurisdiction": "CA",
            "estimated_hours": 200,
            "budget_ceiling": 50000.0,
            "requested_by": "test-user",
            "priority": "high",
            "due_date": "2024-12-31",
        }
        rftp_response = client.post("/rftps", json=rftp_payload)
        assert rftp_response.status_code == 201, rftp_response.text
        rftp_id = rftp_response.json()["rftp_id"]

        proposal_payload = {
            "proposal_id": f"proposal-{uuid.uuid4()}",
            "rftp_id": rftp_id,
            "rftp_request": rftp_payload,
            "proposed_hours": 180,
            "proposed_budget": 45000.0,
            "proposed_deliverables": [
                "Executive Summary",
                "Technical Analysis",
                "Recommendations",
            ],
            "proposed_timeline": {
                "start_date": "2024-02-01",
                "completion_date": "2024-05-31",
            },
            "technical_approach": "Comprehensive IRP analysis using GridPath",
            "assumptions": ["Load growth assumptions", "Technology cost projections"],
            "risks": ["Data availability", "Model complexity"],
            "created_by": "analyst-1",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        proposal_response = client.post("/proposals", json=proposal_payload)
        assert proposal_response.status_code == 201, proposal_response.text
        task_id = proposal_response.json()["task_id"]

        return {
            "rftp_id": rftp_id,
            "proposal_id": proposal_payload["proposal_id"],
            "task_id": task_id,
            "rftp_payload": rftp_payload,
            "proposal_payload": proposal_payload,
        }

    def test_create_rftp_success(self, client):
        """Test successful RFTP creation."""
        rftp_data = {
            "title": "Test IRP Analysis",
            "description": "Comprehensive IRP analysis for CAISO",
            "task_type": "irp_analysis",
            "jurisdiction": "CA",
            "estimated_hours": 200,
            "budget_ceiling": 50000.0,
            "requested_by": "test-user",
            "priority": "high",
            "due_date": "2024-12-31"
        }
        
        response = client.post("/rftps", json=rftp_data)
        
        assert response.status_code == 201
        data = response.json()
        assert "rftp_id" in data
        assert data["status"] == "submitted"
        assert "created_at" in data

    def test_get_rftp_success(self, client):
        """Test successful RFTP retrieval."""
        # First create an RFTP
        rftp_data = {
            "title": "Test IRP Analysis",
            "description": "Comprehensive IRP analysis for CAISO",
            "task_type": "irp_analysis",
            "jurisdiction": "CA",
            "estimated_hours": 200,
            "budget_ceiling": 50000.0,
            "requested_by": "test-user"
        }
        
        create_response = client.post("/rftps", json=rftp_data)
        rftp_id = create_response.json()["rftp_id"]
        
        # Then retrieve it
        response = client.get(f"/rftps/{rftp_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Test IRP Analysis"
        assert data["task_type"] == "irp_analysis"
        assert data["status"] == "submitted"
        assert "history" in data and len(data["history"]) >= 1
        assert "created_at" in data

    def test_get_rftp_not_found(self, client):
        """Test RFTP retrieval for non-existent ID."""
        response = client.get("/rftps/non-existent-id")
        
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data

    def test_list_rftps(self, client):
        """Test RFTP listing."""
        # Create multiple RFTPs
        rftp_data_1 = {
            "title": "IRP Analysis 1",
            "description": "First IRP analysis",
            "task_type": "irp_analysis",
            "jurisdiction": "CA",
            "estimated_hours": 200,
            "budget_ceiling": 50000.0,
            "requested_by": "test-user-1"
        }
        
        rftp_data_2 = {
            "title": "RPS Compliance Study",
            "description": "RPS compliance analysis",
            "task_type": "rps_compliance",
            "jurisdiction": "CA",
            "estimated_hours": 150,
            "budget_ceiling": 35000.0,
            "requested_by": "test-user-2"
        }
        
        client.post("/rftps", json=rftp_data_1)
        client.post("/rftps", json=rftp_data_2)
        
        # List all RFTPs
        response = client.get("/rftps")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert any(rftp["title"] == "IRP Analysis 1" for rftp in data)
        assert any(rftp["title"] == "RPS Compliance Study" for rftp in data)
        assert all("status" in rftp for rftp in data)

    def test_list_rftps_with_filter(self, client):
        """Test RFTP listing with task type filter."""
        # Create RFTPs with different task types
        rftp_data_1 = {
            "title": "IRP Analysis",
            "description": "IRP analysis",
            "task_type": "irp_analysis",
            "jurisdiction": "CA",
            "estimated_hours": 200,
            "budget_ceiling": 50000.0,
            "requested_by": "test-user"
        }
        
        rftp_data_2 = {
            "title": "RPS Study",
            "description": "RPS study",
            "task_type": "rps_compliance",
            "jurisdiction": "CA",
            "estimated_hours": 150,
            "budget_ceiling": 35000.0,
            "requested_by": "test-user"
        }
        
        client.post("/rftps", json=rftp_data_1)
        client.post("/rftps", json=rftp_data_2)
        
        # Filter by task type
        response = client.get("/rftps?task_type=irp_analysis")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["task_type"] == "irp_analysis"

    def test_create_proposal_success(self, client):
        """Test successful task proposal creation."""
        # First create an RFTP
        rftp_data = {
            "title": "Test IRP Analysis",
            "description": "Comprehensive IRP analysis for CAISO",
            "task_type": "irp_analysis",
            "jurisdiction": "CA",
            "estimated_hours": 200,
            "budget_ceiling": 50000.0,
            "requested_by": "test-user"
        }
        
        rftp_response = client.post("/rftps", json=rftp_data)
        rftp_id = rftp_response.json()["rftp_id"]
        
        # Then create a proposal
        proposal_data = {
            "proposal_id": "proposal-123",
            "rftp_id": rftp_id,
            "rftp_request": rftp_data,
            "proposed_hours": 180,
            "proposed_budget": 45000.0,
            "proposed_deliverables": ["Executive Summary", "Technical Analysis", "Recommendations"],
            "proposed_timeline": {
                "start_date": "2024-02-01",
                "completion_date": "2024-05-31"
            },
            "technical_approach": "Comprehensive IRP analysis using GridPath",
            "assumptions": ["Load growth assumptions", "Technology cost projections"],
            "risks": ["Data availability", "Model complexity"],
            "created_by": "analyst-1",
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        response = client.post("/proposals", json=proposal_data)
        
        assert response.status_code == 201
        data = response.json()
        assert "proposal_id" in data
        assert data["status"] == "created"
        assert "task_id" in data

    def test_approve_task_success(self, client):
        """Test successful task approval."""
        workflow = self._bootstrap_task(client)
        approval_data = {
            "task_id": workflow["task_id"],
            "approved_by": "manager-1",
            "approved_at": datetime.now(timezone.utc).isoformat(),
            "approved_budget": 45000.0,
            "approved_hours": 180,
            "conditions": ["Monthly status reports required"],
            "notes": "Approved with conditions"
        }
        
        response = client.post(f"/tasks/{workflow['task_id']}/approve", json=approval_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "accepted"

    def test_start_task_success(self, client):
        """Test successful task start."""
        workflow = self._bootstrap_task(client)
        approval_data = {
            "task_id": workflow["task_id"],
            "approved_by": "manager-1",
            "approved_at": datetime.now(timezone.utc).isoformat(),
            "approved_budget": 45000.0,
            "approved_hours": 180,
            "conditions": ["Monthly status reports required"],
            "notes": "Approved with conditions"
        }
        
        client.post(f"/tasks/{workflow['task_id']}/approve", json=approval_data)

        start_data = {"assigned_to": "analyst-1"}
        response = client.post(f"/tasks/{workflow['task_id']}/start", json=start_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "in_progress"

    def test_complete_task_success(self, client):
        """Test successful task completion."""
        workflow = self._bootstrap_task(client)
        approval_data = {
            "task_id": workflow["task_id"],
            "approved_by": "manager-1",
            "approved_at": datetime.now(timezone.utc).isoformat(),
            "approved_budget": 45000.0,
            "approved_hours": 180
        }
        client.post(f"/tasks/{workflow['task_id']}/approve", json=approval_data)
        client.post(f"/tasks/{workflow['task_id']}/start", json={"assigned_to": "analyst-1"})

        completion_data = {
            "artifacts": [
                {
                    "artifact_id": "artifact-1",
                    "filename": "irp_report.pdf",
                    "file_size": 1024000,
                    "content_type": "application/pdf",
                    "download_url": "http://minio:9000/reports/irp_report.pdf",
                    "created_at": datetime.now(timezone.utc).isoformat()
                }
            ]
        }
        
        response = client.post(f"/tasks/{workflow['task_id']}/complete", json=completion_data)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"

    def test_update_progress_success(self, client):
        """Test successful progress update."""
        workflow = self._bootstrap_task(client)
        approval_data = {
            "task_id": workflow["task_id"],
            "approved_by": "manager-1",
            "approved_at": datetime.now(timezone.utc).isoformat(),
            "approved_budget": 45000.0,
            "approved_hours": 180
        }
        client.post(f"/tasks/{workflow['task_id']}/approve", json=approval_data)
        client.post(f"/tasks/{workflow['task_id']}/start", json={"assigned_to": "analyst-1"})

        progress_data = {
            "progress_percentage": 50,
            "spent_hours": 90.0,
            "spent_budget": 22500.0
        }
        
        response = client.post(f"/tasks/{workflow['task_id']}/progress", json=progress_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["updates"]["progress_percentage"] == 50

    def test_get_dashboard_data(self, client):
        """Test dashboard telemetry data retrieval."""
        workflow = self._bootstrap_task(client)
        approval_data = {
            "task_id": workflow["task_id"],
            "approved_by": "manager-1",
            "approved_at": datetime.now(timezone.utc).isoformat(),
            "approved_budget": 45000.0,
            "approved_hours": 180
        }
        client.post(f"/tasks/{workflow['task_id']}/approve", json=approval_data)
        client.post(f"/tasks/{workflow['task_id']}/start", json={"assigned_to": "analyst-1"})
        client.post(
            f"/tasks/{workflow['task_id']}/progress",
            json={"progress_percentage": 80, "spent_budget": 40000.0, "spent_hours": 160.0},
        )

        response = client.get("/telemetry/dashboard")
        
        assert response.status_code == 200
        data = response.json()
        assert "summary" in data
        assert "budget_by_type" in data
        assert "status_distribution" in data
        assert "workflow_funnel" in data
        assert "recent_events" in data
        assert "at_risk_tasks" in data
        
        # Check summary structure
        summary = data["summary"]
        assert "total_tasks" in summary
        assert "completed_tasks" in summary
        assert "in_progress_tasks" in summary
        assert "completion_rate" in summary
        assert "total_budget" in summary
        assert "spent_budget" in summary
        assert "budget_utilization" in summary

    def test_health_check(self, client):
        """Test health check endpoint."""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "task-manager"

    def test_rftp_validation(self, client):
        """Test RFTP request validation."""
        # Test missing required fields
        invalid_rftp = {
            "title": "Test",
            # Missing required fields
        }
        
        response = client.post("/rftps", json=invalid_rftp)
        
        assert response.status_code == 422  # Validation error

    def test_task_type_enum_validation(self, client):
        """Test task type enum validation."""
        invalid_rftp = {
            "title": "Test",
            "description": "Test description",
            "task_type": "invalid_type",  # Invalid task type
            "jurisdiction": "CA",
            "estimated_hours": 200,
            "budget_ceiling": 50000.0,
            "requested_by": "test-user"
        }
        
        response = client.post("/rftps", json=invalid_rftp)
        
        assert response.status_code == 422  # Validation error

    def test_budget_ceiling_validation(self, client):
        """Test budget ceiling validation."""
        invalid_rftp = {
            "title": "Test",
            "description": "Test description",
            "task_type": "irp_analysis",
            "jurisdiction": "CA",
            "estimated_hours": 200,
            "budget_ceiling": -1000.0,  # Negative budget
            "requested_by": "test-user"
        }
        
        response = client.post("/rftps", json=invalid_rftp)
        
        assert response.status_code == 422  # Validation error

    def test_estimated_hours_validation(self, client):
        """Test estimated hours validation."""
        invalid_rftp = {
            "title": "Test",
            "description": "Test description",
            "task_type": "irp_analysis",
            "jurisdiction": "CA",
            "estimated_hours": 0,  # Invalid hours
            "budget_ceiling": 50000.0,
            "requested_by": "test-user"
        }
        
        response = client.post("/rftps", json=invalid_rftp)
        
        assert response.status_code == 422  # Validation error


class TestTaskManagerModels:
    """Test cases for Pydantic models."""

    def test_rftp_request_model(self):
        """Test RFTPRequest model validation."""
        valid_data = {
            "title": "Test IRP Analysis",
            "description": "Comprehensive IRP analysis for CAISO",
            "task_type": "irp_analysis",
            "jurisdiction": "CA",
            "estimated_hours": 200,
            "budget_ceiling": 50000.0,
            "requested_by": "test-user"
        }
        
        rftp = RFTPRequest(**valid_data)
        assert rftp.title == "Test IRP Analysis"
        assert rftp.task_type == "irp_analysis"
        assert rftp.estimated_hours == 200

    def test_task_proposal_model(self):
        """Test TaskProposal model validation."""
        rftp_data = {
            "title": "Test IRP Analysis",
            "description": "Comprehensive IRP analysis for CAISO",
            "task_type": "irp_analysis",
            "jurisdiction": "CA",
            "estimated_hours": 200,
            "budget_ceiling": 50000.0,
            "requested_by": "test-user"
        }
        
        valid_data = {
            "proposal_id": "proposal-123",
            "rftp_request": RFTPRequest(**rftp_data),
            "proposed_hours": 180,
            "proposed_budget": 45000.0,
            "proposed_deliverables": ["Executive Summary", "Technical Analysis"],
            "proposed_timeline": {
                "start_date": "2024-02-01",
                "completion_date": "2024-05-31"
            },
            "technical_approach": "Comprehensive IRP analysis using GridPath",
            "created_by": "analyst-1",
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        proposal = TaskProposal(**valid_data)
        assert proposal.proposal_id == "proposal-123"
        assert proposal.proposed_hours == 180
        assert len(proposal.proposed_deliverables) == 2

    def test_task_approval_model(self):
        """Test TaskApproval model validation."""
        valid_data = {
            "task_id": "task-123",
            "approved_by": "manager-1",
            "approved_at": datetime.now(timezone.utc).isoformat(),
            "approved_budget": 45000.0,
            "approved_hours": 180
        }
        
        approval = TaskApproval(**valid_data)
        assert approval.task_id == "task-123"
        assert approval.approved_budget == 45000.0
        assert approval.approved_hours == 180


if __name__ == "__main__":
    pytest.main([__file__])
