"""
Adapters package for the Gateway Service.

Contains HTTP client wrappers for internal dependencies (Auth,
Entitlements, Metrics). These adapters encapsulate:

- Base URLs and request shapes
- Retry policies and circuit breakers
- Error handling that maps to shared errors

Keep adapters thin and side-effect free outside of explicit calls.
"""

from .auth_client import AuthClient
from .entitlements_client import EntitlementsClient
from .served_data_client import ServedDataClient
from .clickhouse_client import ClickHouseClient
from .report_template_store import ReportTemplateStore
from .figure_factory import FigureFactory

__all__ = [
    "AuthClient",
    "EntitlementsClient",
    "ServedDataClient",
    "ClickHouseClient",
    "ReportTemplateStore",
    "FigureFactory",
]
