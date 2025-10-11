"""
Task Manager service for 254Carbon Access Layer.
Manages RFTP intake, task proposals, approvals, and billing workflows.
"""

import sys
import os
import uuid
from collections import deque
from datetime import datetime, timezone, timedelta
from enum import Enum
from time import perf_counter
from typing import Any, Deque, Dict, List, Optional, Sequence

# Add shared directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(os.path.join(os.path.dirname(__file__), '.'))

from fastapi import Body, Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import structlog

from shared.config import BaseConfig
from shared.logging import get_logger
from shared.metrics import MetricsCollector
from shared.observability import get_observability_manager
from shared.tracing import get_w3c_trace_context

try:  # pragma: no cover - allow running tests without auth dependency
    from shared.auth import JWKSAuthenticator
except ModuleNotFoundError:  # pragma: no cover
    class JWKSAuthenticator:  # type: ignore[override]
        """Lightweight fallback authenticator used for local tests."""

        def __init__(self, jwks_url: str):
            self.jwks_url = jwks_url

        async def authenticate(self, *args, **kwargs):
            return {"user_id": "test-user", "roles": ["user"]}



class RFTPStatus(str, Enum):
    """Workflow states for RFTP intake."""

    DRAFT = "draft"
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    REJECTED = "rejected"


class TaskStatus(str, Enum):
    """Task status enumeration aligned with public contract."""

    DRAFT = "draft"
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    TERMINATED = "terminated"
    REJECTED = "rejected"




class TaskType(str, Enum):
    """Task type enumeration."""
    IRP_ANALYSIS = "irp_analysis"
    RPS_COMPLIANCE = "rps_compliance"
    GHG_ASSESSMENT = "ghg_assessment"
    RELIABILITY_STUDY = "reliability_study"
    DER_PROGRAM = "der_program"
    TRANSMISSION_PLANNING = "transmission_planning"


class RFTPRequest(BaseModel):
    """Request for Task Proposal (RFTP) model."""
    title: str = Field(..., description="Task title")
    description: str = Field(..., description="Detailed task description")
    task_type: TaskType = Field(..., description="Type of task")
    jurisdiction: str = Field(..., description="Regulatory jurisdiction")
    estimated_hours: int = Field(..., ge=1, le=1000, description="Estimated hours")
    budget_ceiling: float = Field(..., ge=0, description="Budget ceiling in USD")
    requested_by: str = Field(..., description="Requesting user ID")
    priority: str = Field(default="medium", description="Priority level")
    due_date: Optional[str] = Field(None, description="Requested due date")
    attachments: List[Dict[str, Any]] = Field(default_factory=list, description="Attachments")


class TaskProposal(BaseModel):
    """Task proposal model."""
    proposal_id: str = Field(..., description="Unique proposal ID")
    rftp_id: Optional[str] = Field(
        None,
        description="Associated RFTP identifier; required for workflow transition",
    )
    rftp_request: RFTPRequest = Field(..., description="Original RFTP request")
    proposed_hours: int = Field(..., ge=1, description="Proposed hours")
    proposed_budget: float = Field(..., ge=0, description="Proposed budget")
    proposed_deliverables: List[str] = Field(..., description="Proposed deliverables")
    proposed_timeline: Dict[str, str] = Field(..., description="Proposed timeline")
    technical_approach: str = Field(..., description="Technical approach")
    assumptions: List[str] = Field(default_factory=list, description="Assumptions")
    risks: List[str] = Field(default_factory=list, description="Identified risks")
    created_by: str = Field(..., description="Proposal creator")
    created_at: str = Field(..., description="Creation timestamp")


class TaskApproval(BaseModel):
    """Task approval model."""
    task_id: str = Field(..., description="Task ID")
    approved_by: str = Field(..., description="Approver user ID")
    approved_at: str = Field(..., description="Approval timestamp")
    approved_budget: float = Field(..., ge=0, description="Approved budget")
    approved_hours: int = Field(..., ge=1, description="Approved hours")
    conditions: List[str] = Field(default=[], description="Approval conditions")
    notes: Optional[str] = Field(None, description="Approval notes")


class Task(BaseModel):
    """Task model."""
    task_id: str = Field(..., description="Unique task ID")
    proposal_id: str = Field(..., description="Associated proposal ID")
    rftp_id: Optional[str] = Field(None, description="Associated RFTP ID")
    title: str = Field(..., description="Task title")
    description: str = Field(..., description="Task description")
    task_type: TaskType = Field(..., description="Task type")
    jurisdiction: str = Field(..., description="Jurisdiction")
    status: TaskStatus = Field(..., description="Current status")
    assigned_to: Optional[str] = Field(None, description="Assigned user ID")
    budget: float = Field(..., ge=0, description="Approved budget")
    hours: int = Field(..., ge=1, description="Approved hours")
    deliverables: List[str] = Field(..., description="Deliverables")
    timeline: Dict[str, str] = Field(..., description="Timeline")
    created_by: str = Field(..., description="Task creator")
    created_at: str = Field(..., description="Creation timestamp")
    approved_at: Optional[str] = Field(None, description="Approval timestamp")
    started_at: Optional[str] = Field(None, description="Start timestamp")
    completed_at: Optional[str] = Field(None, description="Completion timestamp")
    progress_percentage: int = Field(default=0, ge=0, le=100, description="Progress percentage")
    spent_hours: float = Field(default=0, ge=0, description="Hours spent")
    spent_budget: float = Field(default=0, ge=0, description="Budget spent")
    due_date: Optional[str] = Field(None, description="Target completion date")
    artifacts: List[Dict[str, Any]] = Field(default_factory=list, description="Generated artifacts")
    monthly_reports: List[Dict[str, Any]] = Field(default_factory=list, description="Monthly status reports")
    workflow_history: List[Dict[str, Any]] = Field(default_factory=list, description="Workflow event history")
    last_event_at: Optional[str] = Field(None, description="Timestamp of the last workflow event")


class TaskManagerService:
    """Task Manager service implementation."""

    def __init__(self):
        self.config = BaseConfig()
        self.logger = get_logger("task-manager")
        self.metrics = MetricsCollector("task-manager")
        
        # Initialize observability
        self.observability = get_observability_manager(
            "task-manager",
            log_level=self.config.log_level,
            otel_exporter=self.config.otel_exporter if self.config.enable_tracing else None,
            enable_console=self.config.enable_console_tracing if self.config.enable_tracing else False
        )
        
        # Initialize authentication
        self.jwks_authenticator = JWKSAuthenticator(self.config.jwks_url)
        
        # In-memory storage for demo (would be replaced with database)
        self._rftp_requests: Dict[str, Dict[str, Any]] = {}
        self._task_proposals: Dict[str, Dict[str, Any]] = {}
        self._tasks: Dict[str, Task] = {}
        self._approvals: Dict[str, TaskApproval] = {}
        self._workflow_events: Deque[Dict[str, Any]] = deque(maxlen=200)
        
        # Create FastAPI app
        self.app = FastAPI(
            title="Task Manager API",
            description="Task authorization workflow and telemetry for 254Carbon",
            version="1.0.0",
            docs_url="/docs",
            redoc_url="/redoc"
        )
        
        self._setup_routes()
        self._setup_middleware()

    @staticmethod
    def _now() -> str:
        """Return an ISO8601 timestamp in UTC."""
        return datetime.now(timezone.utc).isoformat()

    def _emit_event(
        self,
        entity_type: str,
        entity_id: str,
        action: str,
        *,
        metadata: Optional[Dict[str, Any]] = None,
        timestamp: Optional[str] = None,
    ) -> None:
        """Record a workflow event and push it to the rolling buffer."""
        event_ts = timestamp or self._now()
        payload = {
            "timestamp": event_ts,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "action": action,
            "metadata": metadata or {},
        }
        self._workflow_events.append(payload)
        self.metrics.record_business_event(action, service="task-manager")
        try:
            self.logger.info(
                "Workflow event",
                entity_type=entity_type,
                entity_id=entity_id,
                action=action,
                metadata=metadata or {},
            )
        except Exception:
            # Logging should never break control flow.
            pass

    def _append_task_history(
        self,
        task_id: str,
        action: str,
        *,
        metadata: Optional[Dict[str, Any]] = None,
        timestamp: Optional[str] = None,
    ) -> None:
        """Update a task's workflow history in-place and emit an event."""
        if task_id not in self._tasks:
            return
        task = self._tasks[task_id]
        event_ts = timestamp or self._now()
        entry = {
            "event": action,
            "timestamp": event_ts,
            "metadata": metadata or {},
        }
        task.workflow_history.append(entry)
        task.last_event_at = event_ts
        self._tasks[task_id] = task
        self._emit_event("task", task_id, action, metadata=metadata, timestamp=event_ts)

    def _update_rftp_status(
        self,
        rftp_id: str,
        status: RFTPStatus,
        *,
        metadata: Optional[Dict[str, Any]] = None,
        timestamp: Optional[str] = None,
    ) -> None:
        """Update stored RFTP metadata and record the change."""
        if rftp_id not in self._rftp_requests:
            raise HTTPException(status_code=404, detail="RFTP not found")
        event_ts = timestamp or self._now()
        record = self._rftp_requests[rftp_id]
        record["status"] = status
        record["updated_at"] = event_ts
        history_entry = {
            "event": status.value,
            "timestamp": event_ts,
            "metadata": metadata or {},
        }
        record["history"].append(history_entry)
        self._emit_event("rftp", rftp_id, f"rftp_{status.value}", metadata=metadata, timestamp=event_ts)

    def _set_task_status(
        self,
        task_id: str,
        status: TaskStatus,
        *,
        metadata: Optional[Dict[str, Any]] = None,
        timestamp: Optional[str] = None,
    ) -> None:
        """Update task status and append workflow history."""
        if task_id not in self._tasks:
            raise HTTPException(status_code=404, detail="Task not found")
        task = self._tasks[task_id]
        task.status = status
        self._tasks[task_id] = task
        self._append_task_history(
            task_id,
            f"task_status_{status.value}",
            metadata=metadata,
            timestamp=timestamp,
        )

    def _store_proposal(
        self,
        proposal: TaskProposal,
        *,
        task_id: str,
        timestamp: str,
    ) -> None:
        """Persist proposal metadata and emit workflow event."""
        self._task_proposals[proposal.proposal_id] = {
            "proposal": proposal,
            "task_id": task_id,
            "created_at": timestamp,
            "status": "submitted",
        }
        self._emit_event(
            "proposal",
            proposal.proposal_id,
            "proposal_submitted",
            metadata={"task_id": task_id, "rftp_id": proposal.rftp_id},
            timestamp=timestamp,
        )
    def _setup_routes(self):
        """Set up API routes."""

        @self.app.post("/rftps", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
        async def create_rftp(
            request: RFTPRequest,
            auth_context: Dict[str, Any] = Depends(self._authenticate),
        ):
            """Create a new Request for Task Proposal."""
            rftp_id = str(uuid.uuid4())
            now = self._now()
            self._rftp_requests[rftp_id] = {
                "request": request,
                "status": RFTPStatus.DRAFT,
                "created_at": now,
                "updated_at": now,
                "history": [],
            }
            self._update_rftp_status(
                rftp_id,
                RFTPStatus.SUBMITTED,
                metadata={
                    "requested_by": request.requested_by,
                    "task_type": request.task_type.value,
                },
                timestamp=now,
            )

            self.logger.info("RFTP created", rftp_id=rftp_id, task_type=request.task_type)

            return {
                "rftp_id": rftp_id,
                "status": self._rftp_requests[rftp_id]["status"].value,
                "created_at": now,
            }

        @self.app.get("/rftps/{rftp_id}", response_model=Dict[str, Any])
        async def get_rftp(
            rftp_id: str,
            auth_context: Dict[str, Any] = Depends(self._authenticate),
        ):
            """Get RFTP by ID."""
            record = self._rftp_requests.get(rftp_id)
            if not record:
                raise HTTPException(status_code=404, detail="RFTP not found")
            request_model = record["request"]
            if hasattr(request_model, "model_dump"):
                payload = request_model.model_dump()  # type: ignore[call-arg]
            else:  # pragma: no cover - pydantic v1 fallback
                payload = request_model.dict()
            payload.update(
                {
                    "rftp_id": rftp_id,
                    "status": record["status"].value,
                    "created_at": record["created_at"],
                    "updated_at": record["updated_at"],
                    "history": record["history"],
                }
            )
            return payload

        @self.app.get("/rftps", response_model=List[Dict[str, Any]])
        async def list_rftps(
            status: Optional[str] = Query(None, description="Filter by status"),
            task_type: Optional[str] = Query(None, description="Filter by task type"),
            auth_context: Dict[str, Any] = Depends(self._authenticate),
        ):
            """List RFTPs with optional filters."""
            items: List[Dict[str, Any]] = []
            for rftp_id, record in self._rftp_requests.items():
                req: RFTPRequest = record["request"]
                status_value = record["status"].value
                if status and status_value != status:
                    continue
                if task_type and req.task_type.value != task_type:
                    continue
                items.append(
                    {
                        "rftp_id": rftp_id,
                        "title": req.title,
                        "task_type": req.task_type.value,
                        "jurisdiction": req.jurisdiction,
                        "estimated_hours": req.estimated_hours,
                        "budget_ceiling": req.budget_ceiling,
                        "requested_by": req.requested_by,
                        "priority": req.priority,
                        "due_date": req.due_date,
                        "status": status_value,
                        "created_at": record["created_at"],
                        "updated_at": record["updated_at"],
                    }
                )
            return items

        @self.app.post("/proposals", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
        async def create_proposal(
            proposal: TaskProposal,
            auth_context: Dict[str, Any] = Depends(self._authenticate),
        ):
            """Create a task proposal and instantiate a task record."""
            if not proposal.rftp_id:
                raise HTTPException(status_code=400, detail="Proposal must include rftp_id")
            if proposal.proposal_id in self._task_proposals:
                raise HTTPException(status_code=409, detail="Proposal already exists")
            rftp_record = self._rftp_requests.get(proposal.rftp_id)
            if not rftp_record:
                raise HTTPException(status_code=404, detail="RFTP not found")

            timestamp = self._now()
            rftp_request: RFTPRequest = rftp_record["request"]
            task_id = str(uuid.uuid4())

            task = Task(
                task_id=task_id,
                proposal_id=proposal.proposal_id,
                rftp_id=proposal.rftp_id,
                title=rftp_request.title,
                description=rftp_request.description,
                task_type=rftp_request.task_type,
                jurisdiction=rftp_request.jurisdiction,
                status=TaskStatus.PROPOSED,
                assigned_to=None,
                budget=proposal.proposed_budget,
                hours=proposal.proposed_hours,
                deliverables=proposal.proposed_deliverables,
                timeline=proposal.proposed_timeline,
                created_by=proposal.created_by,
                created_at=proposal.created_at or timestamp,
                due_date=rftp_request.due_date,
            )
            self._tasks[task_id] = task

            self._append_task_history(
                task_id,
                "task_created",
                metadata={"proposal_id": proposal.proposal_id, "task_type": task.task_type.value},
                timestamp=timestamp,
            )
            self._set_task_status(
                task_id,
                TaskStatus.PROPOSED,
                metadata={"proposal_id": proposal.proposal_id},
                timestamp=timestamp,
            )

            self._store_proposal(proposal, task_id=task_id, timestamp=timestamp)
            self._update_rftp_status(
                proposal.rftp_id,
                RFTPStatus.UNDER_REVIEW,
                metadata={"proposal_id": proposal.proposal_id},
                timestamp=timestamp,
            )

            self.logger.info("Task proposal created", proposal_id=proposal.proposal_id, task_id=task_id)

            return {"proposal_id": proposal.proposal_id, "task_id": task_id, "status": "created"}

        @self.app.get("/proposals/{proposal_id}", response_model=TaskProposal)
        async def get_proposal(
            proposal_id: str,
            auth_context: Dict[str, Any] = Depends(self._authenticate),
        ):
            """Get task proposal by ID."""
            record = self._task_proposals.get(proposal_id)
            if not record:
                raise HTTPException(status_code=404, detail="Proposal not found")
            return record["proposal"]

        @self.app.get("/tasks", response_model=List[Task])
        async def list_tasks(
            status: Optional[str] = Query(None, description="Filter by status"),
            task_type: Optional[str] = Query(None, description="Filter by task type"),
            assigned_to: Optional[str] = Query(None, description="Filter by assigned user"),
            auth_context: Dict[str, Any] = Depends(self._authenticate),
        ):
            """List tasks with optional filters."""
            tasks = list(self._tasks.values())
            if status:
                tasks = [t for t in tasks if t.status.value == status]
            if task_type:
                tasks = [t for t in tasks if t.task_type.value == task_type]
            if assigned_to:
                tasks = [t for t in tasks if t.assigned_to == assigned_to]
            return tasks

        @self.app.get("/tasks/{task_id}", response_model=Task)
        async def get_task(
            task_id: str,
            auth_context: Dict[str, Any] = Depends(self._authenticate),
        ):
            """Get task by ID."""
            task = self._tasks.get(task_id)
            if not task:
                raise HTTPException(status_code=404, detail="Task not found")
            return task

        @self.app.post("/tasks/{task_id}/approve", response_model=Dict[str, Any])
        async def approve_task(
            task_id: str,
            approval: TaskApproval,
            auth_context: Dict[str, Any] = Depends(self._authenticate),
        ):
            """Approve a task."""
            if task_id not in self._tasks:
                raise HTTPException(status_code=404, detail="Task not found")

            task = self._tasks[task_id]
            if task.status not in {TaskStatus.PROPOSED, TaskStatus.DRAFT}:
                raise HTTPException(status_code=400, detail="Task cannot be approved from current status")

            task.budget = approval.approved_budget
            task.hours = approval.approved_hours
            task.approved_at = approval.approved_at or self._now()
            self._tasks[task_id] = task
            self._approvals[task_id] = approval

            if task.proposal_id in self._task_proposals:
                self._task_proposals[task.proposal_id]["status"] = "approved"

            if task.rftp_id:
                self._update_rftp_status(
                    task.rftp_id,
                    RFTPStatus.APPROVED,
                    metadata={"task_id": task_id},
                )

            self._set_task_status(
                task_id,
                TaskStatus.ACCEPTED,
                metadata={"approved_by": approval.approved_by},
                timestamp=approval.approved_at,
            )

            self.logger.info("Task approved", task_id=task_id, approved_by=approval.approved_by)

            return {"task_id": task_id, "status": TaskStatus.ACCEPTED.value}

        @self.app.post("/tasks/{task_id}/start", response_model=Dict[str, Any])
        async def start_task(
            task_id: str,
            body: Dict[str, Any] = Body(...),
            auth_context: Dict[str, Any] = Depends(self._authenticate),
        ):
            """Start a task."""
            task = self._tasks.get(task_id)
            if not task:
                raise HTTPException(status_code=404, detail="Task not found")
            if task.status != TaskStatus.ACCEPTED:
                raise HTTPException(status_code=400, detail="Task must be accepted before starting")

            assigned_to = body.get("assigned_to")
            if not assigned_to:
                raise HTTPException(status_code=400, detail="assigned_to is required")

            now = self._now()
            task.assigned_to = assigned_to
            task.started_at = now
            self._tasks[task_id] = task

            self._set_task_status(
                task_id,
                TaskStatus.IN_PROGRESS,
                metadata={"assigned_to": assigned_to},
                timestamp=now,
            )

            self.logger.info("Task started", task_id=task_id, assigned_to=assigned_to)

            return {"task_id": task_id, "status": TaskStatus.IN_PROGRESS.value}

        @self.app.post("/tasks/{task_id}/complete", response_model=Dict[str, Any])
        async def complete_task(
            task_id: str,
            payload: Dict[str, Any] = Body(default_factory=dict),
            auth_context: Dict[str, Any] = Depends(self._authenticate),
        ):
            """Complete a task."""
            task = self._tasks.get(task_id)
            if not task:
                raise HTTPException(status_code=404, detail="Task not found")
            if task.status != TaskStatus.IN_PROGRESS:
                raise HTTPException(status_code=400, detail="Task must be in progress to complete")

            artifacts = payload.get("artifacts", [])
            now = self._now()
            task.status = TaskStatus.COMPLETED
            task.completed_at = now
            task.progress_percentage = 100
            task.artifacts = artifacts
            self._tasks[task_id] = task

            self._append_task_history(
                task_id,
                "task_completed",
                metadata={"artifact_count": len(artifacts)},
                timestamp=now,
            )
            self._set_task_status(
                task_id,
                TaskStatus.COMPLETED,
                metadata={"complete": True},
                timestamp=now,
            )

            self.logger.info("Task completed", task_id=task_id, artifacts=len(artifacts))

            return {"task_id": task_id, "status": TaskStatus.COMPLETED.value}

        @self.app.post("/tasks/{task_id}/progress", response_model=Dict[str, Any])
        async def update_progress(
            task_id: str,
            progress_data: Dict[str, Any] = Body(...),
            auth_context: Dict[str, Any] = Depends(self._authenticate),
        ):
            """Update task progress."""
            task = self._tasks.get(task_id)
            if not task:
                raise HTTPException(status_code=404, detail="Task not found")

            updated_fields: Dict[str, Any] = {}
            if "progress_percentage" in progress_data:
                task.progress_percentage = max(0, min(100, progress_data["progress_percentage"]))
                updated_fields["progress_percentage"] = task.progress_percentage
            if "spent_hours" in progress_data:
                task.spent_hours = max(0.0, float(progress_data["spent_hours"]))
                updated_fields["spent_hours"] = task.spent_hours
            if "spent_budget" in progress_data:
                task.spent_budget = max(0.0, float(progress_data["spent_budget"]))
                updated_fields["spent_budget"] = task.spent_budget

            self._tasks[task_id] = task

            if task.budget > 0 and task.spent_budget >= task.budget * 0.8:
                self.logger.warning(
                    "Budget utilization alert",
                    task_id=task_id,
                    spent=task.spent_budget,
                    budget=task.budget,
                )
                self._emit_event(
                    "task",
                    task_id,
                    "task_budget_alert",
                    metadata={"spent_budget": task.spent_budget, "budget": task.budget},
                )

            self._append_task_history(
                task_id,
                "task_progress_updated",
                metadata=updated_fields,
            )

            self.logger.info("Task progress updated", task_id=task_id, updates=updated_fields)

            return {"task_id": task_id, "status": task.status.value, "updates": updated_fields}

        @self.app.get("/telemetry/dashboard", response_model=Dict[str, Any])
        async def get_dashboard_data(
            auth_context: Dict[str, Any] = Depends(self._authenticate),
        ):
            """Get dashboard telemetry data."""
            total_tasks = len(self._tasks)
            completed_tasks = len([t for t in self._tasks.values() if t.status == TaskStatus.COMPLETED])
            in_progress_tasks = len([t for t in self._tasks.values() if t.status == TaskStatus.IN_PROGRESS])
            accepted_tasks = len([t for t in self._tasks.values() if t.status == TaskStatus.ACCEPTED])
            total_budget = sum(t.budget for t in self._tasks.values())
            spent_budget = sum(t.spent_budget for t in self._tasks.values())

            budget_by_type: Dict[str, Dict[str, float]] = {}
            for task in self._tasks.values():
                key = task.task_type.value
                bucket = budget_by_type.setdefault(key, {"budget": 0.0, "spent": 0.0})
                bucket["budget"] += task.budget
                bucket["spent"] += task.spent_budget

            status_distribution = {
                status.value: len([t for t in self._tasks.values() if t.status == status])
                for status in TaskStatus
            }

            workflow_funnel = {
                "rftps_submitted": len(self._rftp_requests),
                "proposals_active": len(self._task_proposals),
                "tasks_accepted": accepted_tasks,
                "tasks_in_progress": in_progress_tasks,
                "tasks_completed": completed_tasks,
            }

            recent_events = list(self._workflow_events)[-10:]
            at_risk_tasks = [
                {
                    "task_id": task.task_id,
                    "status": task.status.value,
                    "progress_percentage": task.progress_percentage,
                    "spent_budget": task.spent_budget,
                    "budget": task.budget,
                }
                for task in self._tasks.values()
                if task.status in {TaskStatus.ACCEPTED, TaskStatus.IN_PROGRESS}
                and task.budget > 0
                and task.spent_budget > task.budget * 0.9
            ]

            return {
                "summary": {
                    "total_tasks": total_tasks,
                    "completed_tasks": completed_tasks,
                    "in_progress_tasks": in_progress_tasks,
                    "completion_rate": completed_tasks / total_tasks if total_tasks else 0,
                    "total_budget": total_budget,
                    "spent_budget": spent_budget,
                    "budget_utilization": (spent_budget / total_budget) if total_budget else 0,
                },
                "budget_by_type": budget_by_type,
                "status_distribution": status_distribution,
                "workflow_funnel": workflow_funnel,
                "recent_events": recent_events,
                "at_risk_tasks": at_risk_tasks,
            }

        @self.app.get("/health")
        async def health_check():
            """Health check endpoint."""
            return {"status": "healthy", "service": "task-manager"}

    def _setup_middleware(self):
        """Set up middleware."""
        @self.app.middleware("http")
        async def observability_middleware(request: Request, call_next):
            start_time = perf_counter()

            inbound_request_id = (
                request.headers.get("x-request-id")
                or request.headers.get("x-correlation-id")
            )
            user_id = request.headers.get("x-user-id")
            tenant_id = request.headers.get("x-tenant-id")

            request_id = self.observability.set_request_id(inbound_request_id)
            self.observability.trace_request(
                request_id=request_id,
                user_id=user_id,
                tenant_id=tenant_id,
            )

            try:
                response = await call_next(request)
            except Exception as exc:
                duration = perf_counter() - start_time
                self.observability.log_error(
                    "unhandled_exception",
                    str(exc),
                    method=request.method,
                    endpoint=request.url.path,
                    duration=duration,
                    tenant_id=tenant_id,
                )
                raise
            else:
                duration = perf_counter() - start_time
                self.observability.log_request(
                    request.method,
                    request.url.path,
                    response.status_code,
                    duration,
                    tenant_id=tenant_id,
                )

                response.headers["X-Process-Time"] = f"{duration:.6f}"
                response.headers["X-Request-Id"] = request_id

                trace_context = get_w3c_trace_context()
                if trace_context:
                    traceparent = trace_context.get("traceparent")
                    if traceparent:
                        response.headers["traceparent"] = traceparent
                    tracestate = trace_context.get("tracestate")
                    if tracestate:
                        response.headers["tracestate"] = tracestate

                return response
            finally:
                self.observability.clear_request_context()

    async def _authenticate(self) -> Dict[str, Any]:
        """Authentication dependency."""
        # Simplified authentication for demo
        return {"user_id": "demo-user", "roles": ["user"]}

    def run(self):
        """Run the service."""
        import uvicorn
        uvicorn.run(
            self.app,
            host="0.0.0.0",
            port=8000,
            log_level=self.config.log_level.lower()
        )


def create_app():
    """Create FastAPI application."""
    service = TaskManagerService()
    return service.app


if __name__ == "__main__":
    service = TaskManagerService()
    service.run()
