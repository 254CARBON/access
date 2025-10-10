"""
Async ClickHouse HTTP client wrapper used by the Access Gateway service.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import httpx

from shared.logging import get_logger


class ClickHouseError(RuntimeError):
    """Raised when the ClickHouse client encounters an error."""


class ClickHouseClient:
    """Lightweight async client for ClickHouse's HTTP interface."""

    def __init__(self, base_url: str, *, timeout: float = 5.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.logger = get_logger("gateway.clickhouse")
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=timeout)

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    async def query(self, sql: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute a SQL query against ClickHouse and return the JSON-decoded response.

        Parameters are bound using ClickHouse HTTP named parameter semantics by
        passing them as `param_<name>` query parameters.
        """
        query_params: Dict[str, Any] = {"query": sql}
        if params:
            for key, value in params.items():
                query_params[f"param_{key}"] = value

        try:
            response = await self._client.get("/query", params=query_params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as exc:  # pragma: no cover - network failures are logged
            self.logger.error("ClickHouse query failed", error=str(exc))
            raise ClickHouseError(str(exc)) from exc

    async def ping(self) -> bool:
        """Return True when ClickHouse responds successfully."""
        try:
            await self.query("SELECT 1 FORMAT JSON")
            return True
        except ClickHouseError:
            return False
