from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import aiohttp
from fastapi import HTTPException

from shared.logging import get_logger


class ReportGenerationService:
    """Coordinates report generation workflows."""

    def __init__(
        self,
        *,
        template_store,
        figure_factory,
        irp_client,
        artifact_bucket: str,
        storage_region: str,
        minio_endpoint: str,
        metrics,
    ) -> None:
        self.template_store = template_store
        self.figure_factory = figure_factory
        self.irp_client = irp_client
        self.artifact_bucket = artifact_bucket
        self.storage_region = storage_region
        self.minio_endpoint = minio_endpoint
        self.metrics = metrics
        self.logger = get_logger("gateway.reporting")
        self._reports: Dict[str, Dict[str, Any]] = {}
        self._worker_task: Optional[asyncio.Task] = None
        self._running = False

    async def start_workers(self) -> None:
        """Start background report generation workers."""
        if self._running:
            return
        self._running = True
        self._worker_task = asyncio.create_task(self._report_worker())

    async def stop_workers(self) -> None:
        """Stop background report generation workers."""
        if not self._running:
            return
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass

    async def _report_worker(self) -> None:
        """Background worker to process queued reports."""
        while self._running:
            try:
                # Find queued reports
                queued_reports = [
                    report_id for report_id, report in self._reports.items()
                    if report.get("status") == "queued"
                ]

                if not queued_reports:
                    await asyncio.sleep(1)
                    continue

                # Process first queued report
                report_id = queued_reports[0]
                await self._process_report(report_id)

            except Exception as e:
                self.logger.error("Error in report worker", error=str(e))
                await asyncio.sleep(5)

    async def _process_report(self, report_id: str) -> None:
        """Process a single report generation."""
        report = self._require_report(report_id)
        report["status"] = "generating"
        report["started_at"] = datetime.now(timezone.utc).isoformat()

        try:
            # Get template and parameters
            template_id = report["payload"]["template_id"]
            parameters = report["payload"]["parameters"]

            template = await self.template_store.get_template(template_id)
            if not template:
                raise HTTPException(status_code=404, detail="Template not found")

            # Generate report content
            report_content = await self._generate_report_content(template, parameters)

            # Upload to MinIO
            artifact_url = await self._upload_artifact(report_id, report_content)

            # Update report status
            await self.mark_report_completed(
                report_id,
                download_url=artifact_url,
                file_size=len(report_content)
            )

            self.logger.info("Report generated successfully", report_id=report_id)

        except Exception as e:
            self.logger.error("Report generation failed", report_id=report_id, error=str(e))
            await self.mark_report_failed(report_id, reason=str(e))

    async def _generate_report_content(self, template: Dict[str, Any], parameters: Dict[str, Any]) -> bytes:
        """Generate the actual report content."""
        # This would integrate with a report generation library like python-docx or reportlab
        # For now, return a placeholder
        content = {
            "template_id": template["template_id"],
            "template_name": template["template_name"],
            "parameters": parameters,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "sections": template.get("sections", [])
        }
        return json.dumps(content, indent=2).encode('utf-8')

    async def _upload_artifact(self, report_id: str, content: bytes) -> str:
        """Upload report artifact to MinIO and return presigned URL."""
        # This would integrate with MinIO SDK
        # For now, return a placeholder URL
        return f"{self.minio_endpoint}/{self.artifact_bucket}/{report_id}.json"

    async def list_templates(self, *, report_type: Optional[str], jurisdiction: Optional[str]) -> List[Dict[str, Any]]:
        return await self.template_store.list_templates(report_type=report_type, jurisdiction=jurisdiction)

    async def enqueue_report(self, payload: Dict[str, Any], requested_by: str) -> str:
        self._validate_request(payload)
        report_id = str(uuid.uuid4())
        record = {
            "report_id": report_id,
            "payload": payload,
            "status": "queued",
            "requested_by": requested_by,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "download_url": None,
            "file_size_bytes": None,
            "details": {},
        }
        self._reports[report_id] = record
        self.metrics.record_business_event("report_enqueue", service="gateway")
        return report_id

    async def get_report_status(self, report_id: str) -> Optional[Dict[str, Any]]:
        return self._reports.get(report_id)

    async def get_download_url(self, report_id: str) -> Optional[Dict[str, Any]]:
        record = self._reports.get(report_id)
        if not record or record.get("download_url") is None:
            return None
        return {
            "report_id": report_id,
            "download_url": record["download_url"],
            "expires_at": record.get("expires_at"),
        }

    async def mark_report_completed(self, report_id: str, *, download_url: str, file_size: int) -> None:
        record = self._require_report(record_id=report_id)
        record.update(
            {
                "status": "completed",
                "download_url": download_url,
                "file_size_bytes": file_size,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        )

    async def mark_report_failed(self, report_id: str, *, reason: str) -> None:
        record = self._require_report(record_id=report_id)
        record.update(
            {
                "status": "failed",
                "error": reason,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        )

    def _require_report(self, record_id: str) -> Dict[str, Any]:
        record = self._reports.get(record_id)
        if not record:
            raise HTTPException(status_code=404, detail={"error": "Report not found"})
        return record

    def _validate_request(self, payload: Dict[str, Any]) -> None:
        required_fields = ["report_type", "jurisdiction", "reporting_period"]
        missing = [field for field in required_fields if field not in payload]
        if missing:
            raise HTTPException(status_code=400, detail={"error": f"Missing fields: {', '.join(missing)}"})
