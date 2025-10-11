from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from .clickhouse_client import ClickHouseClient


class ReportTemplateStore:
    """Queries ClickHouse Gold tables for report templates and sections."""

    def __init__(self, clickhouse: ClickHouseClient) -> None:
        self._clickhouse = clickhouse
        self._logger = logging.getLogger(__name__)

    async def list_templates(
        self,
        *,
        report_type: Optional[str] = None,
        jurisdiction: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        filters: List[str] = []
        params: Dict[str, Any] = {}

        if report_type:
            filters.append("report_type = {report_type:String}")
            params["report_type"] = report_type

        if jurisdiction:
            filters.append("hasAny(jurisdictions, [{jurisdiction:String}])")
            params["jurisdiction"] = jurisdiction

        where_clause = " AND ".join(filters)
        if where_clause:
            where_clause = f"WHERE {where_clause}"

        sql = f"""
            SELECT
                template_id,
                template_name,
                report_type,
                jurisdictions,
                document_format,
                template_engine,
                sections,
                styles,
                version,
                author,
                created_at,
                updated_at
            FROM gold.reporting.templates
            {where_clause}
            ORDER BY report_type, template_name
        """

        result = await self._clickhouse.query(sql, params)
        rows = result.get("data", [])
        return [self._normalize_template_row(row) for row in rows]

    async def get_template(self, template_id: str) -> Optional[Dict[str, Any]]:
        sql = """
            SELECT *
            FROM gold.reporting.templates
            WHERE template_id = {template_id:String}
            LIMIT 1
        """
        result = await self._clickhouse.query(sql, {"template_id": template_id})
        rows = result.get("data", [])
        if not rows:
            return None
        return self._normalize_template_row(rows[0])

    def _normalize_template_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Convert JSON string columns into structured objects."""
        normalized = dict(row)
        normalized["sections"] = self._decode_json(normalized.get("sections"), default=[])
        normalized["styles"] = self._decode_json(normalized.get("styles"), default={})

        sections = normalized.get("sections", [])
        if isinstance(sections, list):
            normalized["sections"] = sorted(
                [self._normalize_section(section) for section in sections if isinstance(section, dict)],
                key=lambda section: section.get("section_order", 0),
            )
        else:
            normalized["sections"] = []
        return normalized

    def _normalize_section(self, section: Dict[str, Any]) -> Dict[str, Any]:
        normalized = dict(section)
        normalized["data_sources"] = self._ensure_list(normalized.get("data_sources"))
        figures = self._ensure_list(normalized.get("figures"))
        normalized["figures"] = [self._decode_json_figure(fig) for fig in figures]
        normalized["text_templates"] = self._ensure_list(normalized.get("text_templates"))
        return normalized

    def _decode_json_figure(self, figure: Any) -> Dict[str, Any]:
        if isinstance(figure, dict):
            return figure
        decoded = self._decode_json(figure, default={})
        if isinstance(decoded, dict):
            return decoded
        return {}

    def _decode_json(self, value: Any, *, default: Any) -> Any:
        if value is None:
            return default
        if isinstance(value, (dict, list)):
            return value
        if isinstance(value, str):
            candidate = value.strip()
            if not candidate:
                return default
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                self._logger.warning("Failed to decode JSON field from ClickHouse row", value=value)
                return default
        return default

    def _ensure_list(self, value: Any) -> List[Any]:
        if value is None:
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            decoded = self._decode_json(value, default=[])
            if isinstance(decoded, list):
                return decoded
        return []
