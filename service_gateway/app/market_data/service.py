"""
Market data service responsible for retrieving tick information.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import redis.asyncio as redis

from shared.logging import get_logger

from service_gateway.app.adapters.clickhouse_client import ClickHouseClient, ClickHouseError


_SYMBOL_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,64}$")
_MARKET_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,64}$")


@dataclass(frozen=True)
class TickRecord:
    """Structured representation of a market tick."""

    tenant_id: str
    symbol: str
    tick_timestamp: str
    price: float
    market: Optional[str] = None
    instrument_id: Optional[str] = None
    volume: Optional[float] = None
    quality_flags: Optional[List[str]] = None
    source_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    updated_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the tick to a JSON-friendly dictionary."""
        payload: Dict[str, Any] = {
            "tenant_id": self.tenant_id,
            "symbol": self.symbol,
            "tick_timestamp": self.tick_timestamp,
            "price": self.price,
        }

        if self.market is not None:
            payload["market"] = self.market
        if self.instrument_id is not None:
            payload["instrument_id"] = self.instrument_id
        if self.volume is not None:
            payload["volume"] = self.volume
        if self.quality_flags is not None:
            payload["quality_flags"] = list(self.quality_flags)
        if self.source_id is not None:
            payload["source_id"] = self.source_id
        if self.metadata is not None:
            payload["metadata"] = self.metadata
        if self.updated_at is not None:
            payload["updated_at"] = self.updated_at
        return payload

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "TickRecord":
        """Rehydrate a tick record from cached JSON state."""
        return cls(
            tenant_id=payload["tenant_id"],
            symbol=payload["symbol"],
            tick_timestamp=payload["tick_timestamp"],
            price=float(payload["price"]),
            market=payload.get("market"),
            instrument_id=payload.get("instrument_id"),
            volume=cls._optional_float(payload.get("volume")),
            quality_flags=list(payload.get("quality_flags", [])) or None,
            source_id=payload.get("source_id"),
            metadata=payload.get("metadata"),
            updated_at=payload.get("updated_at"),
        )

    @staticmethod
    def _optional_float(value: Any) -> Optional[float]:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None


class MarketDataService:
    """Coordinates Redis cache reads and ClickHouse lookups for tick data."""

    def __init__(
        self,
        redis_url: str,
        clickhouse_client: ClickHouseClient,
        *,
        cache_ttl_seconds: int = 5,
    ) -> None:
        self.redis_url = redis_url
        self.cache_ttl_seconds = cache_ttl_seconds
        self.clickhouse = clickhouse_client
        self.logger = get_logger("gateway.market_data")
        self._redis = redis.from_url(
            redis_url,
            encoding="utf-8",
            decode_responses=True,
        )

    async def close(self) -> None:
        """Close Redis connections."""
        try:
            await self._redis.close()
        except Exception:  # pragma: no cover - close is best effort
            pass

    async def get_latest_tick(
        self,
        tenant_id: str,
        symbol: str,
        *,
        market: Optional[str] = None,
    ) -> Tuple[Optional[TickRecord], str]:
        """
        Retrieve the most recent tick for the requested symbol.

        Returns a tuple containing the tick (or None) and the data source that
        satisfied the request: "redis", "clickhouse", or "miss".
        """
        self._validate_symbol(symbol)
        if market:
            self._validate_market(market)

        cache_key = self._cache_key("latest", tenant_id, symbol, market)
        cached = await self._read_cache(cache_key)
        if cached:
            return TickRecord.from_dict(cached), "redis"

        tick = await self._fetch_latest_from_clickhouse(tenant_id, symbol, market=market)
        if tick:
            await self._write_cache(cache_key, tick)
            return tick, "clickhouse"
        return None, "miss"

    async def get_tick_window(
        self,
        tenant_id: str,
        symbol: str,
        start: datetime,
        end: datetime,
        *,
        market: Optional[str] = None,
    ) -> List[TickRecord]:
        """Retrieve all ticks within the requested time window."""
        self._validate_symbol(symbol)
        if market:
            self._validate_market(market)
        if start >= end:
            raise ValueError("start must be earlier than end")

        query = """
SELECT tenant_id,
       market,
       symbol,
       instrument_id,
       tick_timestamp,
       price,
       volume,
       quality_flags,
       source_id,
       metadata,
       updated_at
FROM served_market_ticks
WHERE tenant_id = {tenant_id:String}
  AND symbol = {symbol:String}
  AND tick_timestamp >= parseDateTime64BestEffort({start:String})
  AND tick_timestamp < parseDateTime64BestEffort({end:String})
{market_clause}
ORDER BY tick_timestamp ASC
FORMAT JSON
""".strip()

        market_clause = ""
        params: Dict[str, Any] = {
            "tenant_id": tenant_id,
            "symbol": symbol,
            "start": self._format_iso(start),
            "end": self._format_iso(end),
        }

        if market:
            market_clause = "  AND market = {market:String}"
            params["market"] = market

        sql = query.replace("{market_clause}", market_clause)

        try:
            response = await self.clickhouse.query(sql, params=params)
        except ClickHouseError as exc:
            raise RuntimeError(f"ClickHouse query failed: {exc}") from exc

        rows = response.get("data", [])
        ticks: List[TickRecord] = []
        for row in rows:
            record = self._tick_from_row(row, fallback_symbol=symbol)
            if record:
                ticks.append(record)
        return ticks

    async def check_redis(self) -> bool:
        """Return True when Redis responds to a ping."""
        try:
            return bool(await self._redis.ping())
        except Exception as exc:
            self.logger.error("Redis health check failed", error=str(exc))
            return False

    async def check_clickhouse(self) -> bool:
        """Return True when ClickHouse responds to a ping."""
        return await self.clickhouse.ping()

    async def _fetch_latest_from_clickhouse(
        self,
        tenant_id: str,
        symbol: str,
        *,
        market: Optional[str],
    ) -> Optional[TickRecord]:
        """Query ClickHouse for the most recent tick."""
        query = """
SELECT tenant_id,
       market,
       symbol,
       instrument_id,
       tick_timestamp,
       price,
       volume,
       quality_flags,
       source_id,
       metadata,
       updated_at
FROM served_market_ticks_latest
WHERE tenant_id = {tenant_id:String}
  AND symbol = {symbol:String}
{market_clause}
ORDER BY tick_timestamp DESC
LIMIT 1
FORMAT JSON
""".strip()

        params: Dict[str, Any] = {"tenant_id": tenant_id, "symbol": symbol}
        market_clause = ""
        if market:
            market_clause = "  AND market = {market:String}"
            params["market"] = market

        sql = query.replace("{market_clause}", market_clause)

        try:
            response = await self.clickhouse.query(sql, params=params)
        except ClickHouseError as exc:
            self.logger.error("Latest tick query failed", error=str(exc))
            return None

        rows = response.get("data", [])
        if not rows:
            return None

        return self._tick_from_row(rows[0], fallback_symbol=symbol)

    async def _read_cache(self, key: str) -> Optional[Dict[str, Any]]:
        """Read a cached tick entry from Redis."""
        try:
            value = await self._redis.get(key)
        except Exception as exc:
            self.logger.error("Redis read failed", key=key, error=str(exc))
            return None

        if not value:
            return None

        try:
            return json.loads(value)
        except json.JSONDecodeError:
            self.logger.warning("Discarding malformed cache payload", key=key)
            return None

    async def _write_cache(self, key: str, tick: TickRecord) -> None:
        """Persist a tick to Redis."""
        try:
            await self._redis.set(key, json.dumps(tick.to_dict()), ex=self.cache_ttl_seconds)
        except Exception as exc:
            self.logger.error("Redis write failed", key=key, error=str(exc))

    def _tick_from_row(self, row: Dict[str, Any], *, fallback_symbol: str) -> Optional[TickRecord]:
        """Convert a ClickHouse row into a TickRecord."""
        try:
            price_value = float(row["price"])
        except (KeyError, TypeError, ValueError):
            return None

        symbol = row.get("symbol") or fallback_symbol
        tenant_id = row.get("tenant_id") or "default"
        tick_timestamp = self._normalize_timestamp(row.get("tick_timestamp"))
        updated_at = self._normalize_timestamp(row.get("updated_at"))

        quality_flags = row.get("quality_flags")
        flags: Optional[List[str]] = None
        if isinstance(quality_flags, list):
            flags = [str(flag) for flag in quality_flags]
        elif isinstance(quality_flags, str):
            parts = [part.strip() for part in quality_flags.split(",") if part.strip()]
            flags = parts or None

        metadata = row.get("metadata")
        if not isinstance(metadata, dict):
            metadata = None

        volume = TickRecord._optional_float(row.get("volume"))

        return TickRecord(
            tenant_id=tenant_id,
            symbol=str(symbol),
            tick_timestamp=tick_timestamp,
            price=price_value,
            market=row.get("market"),
            instrument_id=row.get("instrument_id"),
            volume=volume,
            quality_flags=flags,
            source_id=row.get("source_id"),
            metadata=metadata,
            updated_at=updated_at,
        )

    def _cache_key(self, namespace: str, tenant_id: str, symbol: str, market: Optional[str]) -> str:
        """Generate a Redis cache key."""
        parts: List[str] = ["gateway", "ticks", namespace, tenant_id.lower(), symbol.lower()]
        if market:
            parts.append(market.lower())
        return ":".join(parts)

    def _validate_symbol(self, symbol: str) -> None:
        if not _SYMBOL_PATTERN.match(symbol):
            raise ValueError("symbol must match pattern [A-Za-z0-9._:-]{1,64}")

    def _validate_market(self, market: str) -> None:
        if not _MARKET_PATTERN.match(market):
            raise ValueError("market must match pattern [A-Za-z0-9._:-]{1,64}")

    def _normalize_timestamp(self, value: Any) -> str:
        """Best-effort conversion of ClickHouse timestamp values to ISO-8601."""
        if value is None:
            return self._format_iso(datetime.now(timezone.utc))

        if isinstance(value, (int, float)):
            dt = datetime.fromtimestamp(float(value), tz=timezone.utc)
            return self._format_iso(dt)

        if isinstance(value, str):
            text = value.strip()
            if not text:
                return self._format_iso(datetime.now(timezone.utc))

            text = text.replace(" ", "T")
            if text.endswith("Z"):
                candidate = text
            elif "+" in text:
                candidate = text
            else:
                candidate = f"{text}Z"

            try:
                dt = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                else:
                    dt = dt.astimezone(timezone.utc)
                return self._format_iso(dt)
            except ValueError:
                pass

        # Fallback to best effort string representation
        return str(value)

    def _format_iso(self, dt: datetime) -> str:
        """Format datetime as ISO-8601 with millisecond precision."""
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return dt.isoformat(timespec="milliseconds").replace("+00:00", "Z")
