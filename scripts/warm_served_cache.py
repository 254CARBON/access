#!/usr/bin/env python3
"""
Warm Redis caches for the most frequently requested served projections.

This helper mirrors the Gateway cache warm endpoint but can be executed manually
from a developer workstation or CI job. It loads the curated hot query list and
invokes the projection service to pre-populate Redis keys.
"""

import argparse
import asyncio
import json
from pathlib import Path
from typing import Optional
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from service_gateway.app.adapters.served_data_client import ServedDataClient  # noqa: E402
from service_gateway.app.caching.cache_manager import CacheManager  # noqa: E402


class _NoOpMetrics:
    """Fallback metrics collector used when running outside the service."""

    def increment_counter(self, *args, **kwargs):
        return None

    def observe_histogram(self, *args, **kwargs):
        return None


async def warm(
    *,
    redis_url: str,
    projection_url: str,
    tenant_id: str,
    user_id: str,
    hot_queries_path: Optional[Path],
    concurrency: int,
    dry_run: bool,
) -> dict:
    """Execute cache warming and return the summary."""
    served_client = ServedDataClient(projection_url)
    metrics = _NoOpMetrics()
    manager = CacheManager(
        redis_url,
        served_client,
        metrics=metrics,
        hot_queries_path=hot_queries_path,
        warm_concurrency=concurrency,
    )

    if dry_run:
        manager.set_served_latest_price = _noop_async  # type: ignore[assignment]
        manager.set_served_curve_snapshot = _noop_async  # type: ignore[assignment]
        manager.set_served_custom = _noop_async  # type: ignore[assignment]

    summary = await manager.warm_cache(user_id, tenant_id)
    return summary


async def _noop_async(*args, **kwargs):  # type: ignore[no-untyped-def]
    return True


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Warm Redis caches for hot served queries.")
    parser.add_argument("--redis-url", default=os.getenv("ACCESS_REDIS_URL", "redis://localhost:6379/0"), help="Redis connection URL")
    parser.add_argument("--projection-url", default=os.getenv("ACCESS_PROJECTION_SERVICE_URL", "http://localhost:8085"), help="Projection service URL")
    parser.add_argument("--tenant", required=True, help="Tenant identifier to warm")
    parser.add_argument("--user", default="cache-warmer", help="User identifier (for observability)")
    parser.add_argument("--hot-queries-file", type=Path, default=None, help="Path to hot served queries JSON override")
    parser.add_argument("--concurrency", type=int, default=int(os.getenv("ACCESS_CACHE_WARM_CONCURRENCY", 5)), help="Concurrent warm operations")
    parser.add_argument("--dry-run", action="store_true", help="Do not write to Redis; print planned warm actions")
    parser.add_argument("--output", type=Path, default=None, help="Optional path to write JSON summary")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        summary = asyncio.run(
            warm(
                redis_url=args.redis_url,
                projection_url=args.projection_url,
                tenant_id=args.tenant,
                user_id=args.user,
                hot_queries_path=args.hot_queries_file,
                concurrency=args.concurrency,
                dry_run=args.dry_run,
            )
        )
    except KeyboardInterrupt:
        return 130
    except Exception as exc:  # pragma: no cover - CLI surface
        print(f"[cache-warm] failed: {exc}", file=sys.stderr)
        return 1

    if args.dry_run:
        print("[cache-warm] DRY RUN - no Redis writes executed")

    print(json.dumps(summary, indent=2))

    if args.output:
        args.output.write_text(json.dumps(summary, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
