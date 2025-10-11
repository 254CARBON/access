from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from .clickhouse_client import ClickHouseClient


class FigureFactory:
    """Materializes figures defined in report templates."""

    _PARAM_PATTERN = re.compile(r"\{(?P<name>[a-zA-Z_][a-zA-Z0-9_]*):(?P<type>[A-Za-z0-9]+)\}")
    _TYPE_CASTERS: Dict[str, Callable[[Any], Any]] = {
        "String": lambda value: None if value is None else str(value),
        "Int32": lambda value: None if value is None else int(value),
        "Int64": lambda value: None if value is None else int(value),
        "UInt32": lambda value: None if value is None else int(value),
        "UInt64": lambda value: None if value is None else int(value),
        "Float32": lambda value: None if value is None else float(value),
        "Float64": lambda value: None if value is None else float(value),
        "Bool": lambda value: None if value is None else bool(value),
        "Date": lambda value: FigureFactory._coerce_date(value),
        "DateTime": lambda value: FigureFactory._coerce_datetime(value),
    }

    def __init__(self, clickhouse: ClickHouseClient) -> None:
        self._clickhouse = clickhouse
        self._logger = logging.getLogger(__name__)

    async def get_figure_spec(self, figure_id: str) -> Optional[Dict[str, Any]]:
        sql = """
            SELECT *
            FROM gold.reporting.figure_specs
            WHERE figure_id = {figure_id:String}
            LIMIT 1
        """
        result = await self._clickhouse.query(sql, {"figure_id": figure_id})
        rows = result.get("data", [])
        if not rows:
            return None
        return self._normalize_figure_spec(rows[0])

    async def render_figure(self, figure_spec: Dict[str, Any], parameters: Dict[str, Any]) -> Dict[str, Any]:
        normalized_spec = self._normalize_figure_spec(figure_spec)
        data_sql: str = normalized_spec.get("query_template", "") or ""
        if not data_sql:
            return {"figure": normalized_spec, "data": [], "parameters": {}, "row_count": 0}

        sql, params = self._bind_parameters(data_sql, parameters)
        result = await self._clickhouse.query(sql, params)
        records = result.get("data", [])
        return {
            "figure": normalized_spec,
            "data": records,
            "parameters": params,
            "row_count": len(records),
        }

    def _bind_parameters(self, query_template: str, parameters: Dict[str, Any]) -> (str, Dict[str, Any]):
        params: Dict[str, Any] = {}
        if not parameters:
            return query_template, params

        for match in self._PARAM_PATTERN.finditer(query_template):
            name = match.group("name")
            type_name = match.group("type")
            if name not in parameters:
                continue

            raw_value = parameters[name]
            caster = self._TYPE_CASTERS.get(type_name, lambda value: value)
            try:
                params[name] = caster(raw_value)
            except (TypeError, ValueError) as exc:
                self._logger.warning("Failed to cast figure parameter", parameter=name, type=type_name, error=str(exc))
                params[name] = raw_value
        return query_template, params

    def _normalize_figure_spec(self, figure_spec: Dict[str, Any]) -> Dict[str, Any]:
        """Decode JSON fields stored as strings in ClickHouse."""
        normalized = dict(figure_spec)
        normalized["filters"] = self._decode_json(normalized.get("filters"), default={})
        normalized["columns"] = self._decode_json(normalized.get("columns"), default=[])
        normalized["conditional_formats"] = self._decode_json(normalized.get("conditional_formats"), default=[])
        normalized["color_palette"] = self._ensure_list(normalized.get("color_palette"))

        for key in ("show_legend", "show_grid"):
            if key in normalized and isinstance(normalized[key], str):
                normalized[key] = normalized[key].lower() == "true"
        return normalized

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
                self._logger.warning("Unable to decode JSON field in figure spec", value=value)
                return default
        return default

    def _ensure_list(self, value: Any) -> List[Any]:
        if value is None:
            return []
        if isinstance(value, list):
            return value
        decoded = self._decode_json(value, default=[])
        return decoded if isinstance(decoded, list) else []

    @staticmethod
    def _coerce_date(value: Any) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, date) and not isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, datetime):
            return value.date().isoformat()
        return str(value)

    @staticmethod
    def _coerce_datetime(value: Any) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc).isoformat()
            return value.astimezone(timezone.utc).isoformat()
        if isinstance(value, date):
            return datetime.combine(value, datetime.min.time(), tzinfo=timezone.utc).isoformat()
        return str(value)
