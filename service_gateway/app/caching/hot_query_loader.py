"""
Utility helpers for loading pre-ranked served query definitions used for cache warming.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Union
import json
import threading


DEFAULT_DATA_FILE = Path(__file__).resolve().parent / "data" / "hot_served_queries.json"


@dataclass(frozen=True)
class HotQueryEntry:
    """Simple view of a hot query entry."""

    tenant_id: str
    instrument_id: str
    projection_type: str
    horizon: Optional[str] = None
    weight: float = 0.0
    ttl_seconds: Optional[int] = None
    raw: Dict[str, Any] = None  # type: ignore[assignment]


class HotServedQueryLoader:
    """
    Loads and filters the curated set of "hot" served queries for cache warming.

    The data is expected to live alongside the service in JSON form. The loader
    handles missing files gracefully by returning empty result sets.
    """

    def __init__(self, config_path: Optional[Union[str, Path]] = None):
        self._path = Path(config_path) if config_path else DEFAULT_DATA_FILE
        self._lock = threading.Lock()
        self._data = self._load()

    @property
    def path(self) -> Path:
        """Return the resolved path to the data file."""
        return self._path

    def refresh(self) -> None:
        """Reload the hot query data from disk."""
        with self._lock:
            self._data = self._load()

    def get_entries(
        self,
        category: str,
        tenant_id: str,
        *,
        limit: Optional[int] = None,
    ) -> List[HotQueryEntry]:
        """
        Return hot query entries for a category filtered by tenant.

        Rows tagged with tenant '*' or 'global' apply to all tenants.
        """
        payload = self._data.get(category, {})
        entries: Iterable[Dict[str, Any]] = payload.get("entries", [])
        max_entries = payload.get("max_entries")
        resolved_limit = limit or max_entries

        filtered: List[HotQueryEntry] = []
        for entry in entries:
            entry_tenant = entry.get("tenant_id", "*")
            if entry_tenant not in (tenant_id, "*", "global"):
                continue

            projection_type = self._resolve_projection_type(category, entry)
            filtered.append(
                HotQueryEntry(
                    tenant_id=tenant_id if entry_tenant != "*" else tenant_id,
                    instrument_id=entry.get("instrument_id", ""),
                    projection_type=projection_type,
                    horizon=entry.get("horizon"),
                    weight=float(entry.get("weight", 0.0)),
                    ttl_seconds=entry.get("ttl_seconds"),
                    raw=entry,
                )
            )

        filtered.sort(key=lambda item: item.weight, reverse=True)
        if resolved_limit:
            filtered = filtered[: resolved_limit]
        return filtered

    def default_ttl(self, category: str, fallback: int) -> int:
        """Return the default TTL for a category, falling back when unset."""
        payload = self._data.get(category, {})
        return int(payload.get("ttl_seconds") or fallback)

    def categories(self) -> List[str]:
        """Return the configured categories in the data file."""
        return [key for key in self._data.keys() if key not in ("metadata",)]

    def _load(self) -> Dict[str, Any]:
        """Read JSON payload from disk. Returns empty configuration on failure."""
        if not self._path.exists():
            return {
                "metadata": {
                    "generated_at": None,
                    "source": [],
                    "description": "No hot query dataset found; cache warming will no-op.",
                },
                "latest_price": {"entries": []},
                "curve_snapshot": {"entries": []},
                "custom": {"entries": []},
            }

        try:
            with self._path.open("r", encoding="utf-8") as handle:
                return json.load(handle)
        except (ValueError, OSError):
            # On malformed payload fall back to empty configuration rather than crashing,
            # so that cache warming degrades gracefully.
            return {
                "metadata": {
                    "generated_at": None,
                    "source": [],
                    "description": f"Failed to parse hot query file at {self._path}",
                },
                "latest_price": {"entries": []},
                "curve_snapshot": {"entries": []},
                "custom": {"entries": []},
            }

    @staticmethod
    def _resolve_projection_type(category: str, entry: Dict[str, Any]) -> str:
        if category == "latest_price":
            return "latest_price"
        if category == "curve_snapshot":
            return "curve_snapshot"
        # Custom projections specify their type explicitly; fall back to provided field.
        return entry.get("projection_type", category)
