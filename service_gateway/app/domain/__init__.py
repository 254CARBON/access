"""
Domain utilities for the Gateway Service.

Includes cross-cutting middleware and request processing helpers that do
not belong to adapters or transport-specific layers.
"""

from .reporting import ReportGenerationService

__all__ = [
    "AuthMiddleware",
    "ReportGenerationService",
]
