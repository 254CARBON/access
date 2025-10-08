"""
Served data client for Gateway.
"""

from typing import Any, Dict, Optional
import httpx
import sys
import os

# Add shared directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from shared.logging import get_logger
from shared.errors import ExternalServiceError
from shared.circuit_breaker import get_circuit_breaker
from shared.retry import retry_on_exception, RetryConfig


class ServedDataClient:
    """Client for retrieving served projections from data-processing."""

    def __init__(self, projection_service_url: str):
        self.base_url = projection_service_url.rstrip('/')
        self.logger = get_logger("gateway.served_client")

        self.circuit_breaker = get_circuit_breaker(
            "projection_service",
            failure_threshold=3,
            recovery_timeout=30.0
        )

        self.retry_config = RetryConfig(
            max_attempts=3,
            base_delay=0.5,
            max_delay=5.0,
            exponential_base=2.0,
            jitter=True
        )

    @retry_on_exception((httpx.HTTPError, httpx.ConnectError), config=RetryConfig(max_attempts=3, base_delay=0.5))
    async def get_latest_price(self, tenant_id: str, instrument_id: str) -> Optional[Dict[str, Any]]:
        """Fetch the latest price projection."""
        params = {"tenant_id": tenant_id, "instrument_id": instrument_id}
        return await self._fetch_projection("/projections/latest_price", params)

    @retry_on_exception((httpx.HTTPError, httpx.ConnectError), config=RetryConfig(max_attempts=3, base_delay=0.5))
    async def get_curve_snapshot(self, tenant_id: str, instrument_id: str, horizon: str) -> Optional[Dict[str, Any]]:
        """Fetch a curve snapshot projection."""
        params = {"tenant_id": tenant_id, "instrument_id": instrument_id, "horizon": horizon}
        return await self._fetch_projection("/projections/curve_snapshot", params)

    @retry_on_exception((httpx.HTTPError, httpx.ConnectError), config=RetryConfig(max_attempts=3, base_delay=0.5))
    async def get_custom_projection(
        self,
        tenant_id: str,
        instrument_id: str,
        projection_type: str
    ) -> Optional[Dict[str, Any]]:
        """Fetch a custom projection."""
        params = {
            "tenant_id": tenant_id,
            "instrument_id": instrument_id,
            "projection_type": projection_type
        }
        return await self._fetch_projection("/projections/custom", params)

    async def _fetch_projection(self, path: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Execute projection fetch with circuit breaker + error handling."""

        async def _request():
            url = f"{self.base_url}{path}"
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, params=params)

            if response.status_code == 200:
                data = response.json()
                self.logger.debug("Served projection retrieved", url=url, params=params)
                return data

            if response.status_code == 404:
                self.logger.info("Served projection not found", url=url, params=params)
                return None

            self.logger.error(
                "Served projection request failed",
                url=url,
                params=params,
                status_code=response.status_code,
                response=response.text
            )
            raise ExternalServiceError(
                service="projection_service",
                message=f"Unexpected status {response.status_code}",
                details={"status_code": response.status_code, "body": response.text}
            )

        try:
            return await self.circuit_breaker.call(_request)
        except ExternalServiceError:
            raise
        except Exception as exc:
            self.logger.error("Projection service error", error=str(exc), params=params)
            raise ExternalServiceError(
                service="projection_service",
                message=str(exc),
                details={"params": params}
            )
