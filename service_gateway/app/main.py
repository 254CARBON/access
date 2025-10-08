"""
API Gateway service for 254Carbon Access Layer.
"""

import sys
import os
import time
import asyncio

# Add shared directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(os.path.join(os.path.dirname(__file__), '.'))

from shared.base_service import BaseService
from shared.config import get_config
from shared.observability import get_observability_manager, observe_function, observe_operation
from shared.errors import ExternalServiceError
from adapters.auth_client import AuthClient
from adapters.entitlements_client import EntitlementsClient
from adapters.served_data_client import ServedDataClient
from domain.auth_middleware import AuthMiddleware
from caching.cache_manager import CacheManager
from ratelimit.token_bucket import TokenBucketRateLimiter, RateLimitMiddleware
from shared.circuit_breaker import circuit_breaker_manager
from fastapi import Depends, HTTPException, Request, Header, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials


class GatewayService(BaseService):
    """API Gateway service implementation."""
    
    def __init__(self):
        super().__init__("gateway", 8000)
        self.auth_client = AuthClient(self.config.auth_service_url)
        self.entitlements_client = EntitlementsClient(self.config.entitlements_service_url)
        self.served_client = ServedDataClient(self.config.projection_service_url)
        self.auth_middleware = AuthMiddleware(self.auth_client, self.entitlements_client)
        self.cache_manager = CacheManager(self.config.redis_url)
        self.rate_limiter = TokenBucketRateLimiter(self.config.redis_url)
        self.rate_limit_middleware = RateLimitMiddleware(self.rate_limiter)
        
        # Initialize observability
        self.observability = get_observability_manager(
            "gateway",
            log_level=self.config.log_level,
            otel_exporter=self.config.otel_exporter,
            enable_console=self.config.enable_console_tracing
        )
        
        # API key authentication fallback
        self.api_keys = {
            "dev-key-123": {"tenant_id": "tenant-1", "roles": ["user"]},
            "admin-key-456": {"tenant_id": "tenant-1", "roles": ["admin"]},
            "service-key-789": {"tenant_id": "*", "roles": ["service"]}
        }
        
        self._setup_gateway_routes()
        self._setup_observability_middleware()

        # Expose service instance via app state for introspection/testing
        self.app.state.gateway_service = self
    
    def _setup_observability_middleware(self):
        """Set up observability middleware."""
        from fastapi import Request, Response
        from starlette.middleware.base import BaseHTTPMiddleware
        
        class ObservabilityMiddleware(BaseHTTPMiddleware):
            def __init__(self, app, observability_manager):
                super().__init__(app)
                self.observability = observability_manager
            
            async def dispatch(self, request: Request, call_next):
                # Generate request ID
                request_id = self.observability.set_request_id()
                
                # Set request context
                self.observability.trace_request(request_id=request_id)
                
                # Start timing
                start_time = time.time()
                
                try:
                    # Process request
                    response = await call_next(request)
                    
                    # Calculate duration
                    duration = time.time() - start_time
                    
                    # Log request
                    self.observability.log_request(
                        method=request.method,
                        endpoint=str(request.url.path),
                        status_code=response.status_code,
                        duration=duration,
                        request_id=request_id
                    )
                    
                    # Add request ID to response headers
                    response.headers["X-Request-ID"] = request_id
                    
                    return response
                    
                except Exception as e:
                    # Calculate duration
                    duration = time.time() - start_time
                    
                    # Log error
                    self.observability.log_error(
                        "request_error",
                        str(e),
                        method=request.method,
                        endpoint=str(request.url.path),
                        duration=duration,
                        request_id=request_id
                    )
                    
                    raise
                finally:
                    # Clear request context
                    self.observability.clear_request_context()
        
        # Add middleware
        self.app.add_middleware(ObservabilityMiddleware, observability_manager=self.observability)
    
    def _setup_gateway_routes(self):
        """Set up gateway-specific routes."""
        
        @self.app.get("/")
        async def root():
            """Root endpoint."""
            return {
                "service": "gateway",
                "message": "254Carbon Access Layer - API Gateway",
                "version": "1.0.0"
            }
        
        @self.app.get("/api/v1/status")
        async def api_status():
            """API status endpoint."""
            return {
                "status": "operational",
                "version": "1.0.0",
                "services": {
                    "gateway": "ok",
                    "auth": "ok",
                    "entitlements": "ok",
                    "streaming": "ok",
                    "metrics": "ok"
                }
            }
        
        @self.app.get("/api/v1/instruments")
        @observe_function("gateway_get_instruments")
        async def get_instruments(request: Request):
            """Get instruments endpoint with authentication, rate limiting, and caching."""
            # Check rate limit first
            rate_limit_result = await self.rate_limit_middleware.check_request(request, "authenticated")
            if not rate_limit_result["allowed"]:
                raise HTTPException(
                    status_code=429,
                    detail={
                        "error": "Rate limit exceeded",
                        "current_count": rate_limit_result["current_count"],
                        "limit": rate_limit_result["limit"],
                        "reset_in_seconds": rate_limit_result["reset_in_seconds"]
                    }
                )

            try:
                user_info = await self.auth_middleware.process_request(
                    request, "read", "instrument"
                )
            except Exception as e:
                self.logger.error("Auth middleware error", error=str(e))
                raise

            # Check cache first
            cached_instruments = await self.cache_manager.get_instruments(
                user_info["user_id"], user_info["tenant_id"]
            )

            if cached_instruments:
                # Log cache hit
                self.observability.log_business_event(
                    "cache_hit",
                    cache_type="instruments",
                    user_id=user_info["user_id"],
                    tenant_id=user_info["tenant_id"]
                )
                
                return {
                    "instruments": cached_instruments,
                    "cached": True,
                    "user": user_info["user_id"],
                    "tenant": user_info["tenant_id"]
                }

            # Simulate fetching from downstream service
            instruments = [
                {"id": "EURUSD", "name": "Euro/US Dollar", "type": "forex"},
                {"id": "GBPUSD", "name": "British Pound/US Dollar", "type": "forex"},
                {"id": "USDJPY", "name": "US Dollar/Japanese Yen", "type": "forex"}
            ]

            # Cache the result
            await self.cache_manager.set_instruments(
                user_info["user_id"], user_info["tenant_id"], instruments
            )
            
            # Log cache miss
            self.observability.log_business_event(
                "cache_miss",
                cache_type="instruments",
                user_id=user_info["user_id"],
                tenant_id=user_info["tenant_id"]
            )

            return {
                "instruments": instruments,
                "cached": False,
                "user": user_info["user_id"],
                "tenant": user_info["tenant_id"]
            }
        
        @self.app.get("/api/v1/curves")
        async def get_curves(request: Request):
            """Get curves endpoint with authentication, rate limiting, and caching."""
            # Check rate limit first
            rate_limit_result = await self.rate_limit_middleware.check_request(request, "authenticated")
            if not rate_limit_result["allowed"]:
                raise HTTPException(
                    status_code=429,
                    detail={
                        "error": "Rate limit exceeded",
                        "current_count": rate_limit_result["current_count"],
                        "limit": rate_limit_result["limit"],
                        "reset_in_seconds": rate_limit_result["reset_in_seconds"]
                    }
                )

            try:
                user_info = await self.auth_middleware.process_request(
                    request, "read", "curve"
                )
            except Exception as e:
                self.logger.error("Auth middleware error", error=str(e))
                raise

            # Check cache first
            cached_curves = await self.cache_manager.get_curves(
                user_info["user_id"], user_info["tenant_id"]
            )

            if cached_curves:
                self.logger.info("Serving curves from cache", user_id=user_info["user_id"])
                return {
                    "curves": cached_curves,
                    "cached": True,
                    "user": user_info["user_id"],
                    "tenant": user_info["tenant_id"]
                }

            # Simulate fetching from downstream service
            curves = [
                {"id": "USD_CURVE", "name": "USD Yield Curve", "currency": "USD"},
                {"id": "EUR_CURVE", "name": "EUR Yield Curve", "currency": "EUR"},
                {"id": "GBP_CURVE", "name": "GBP Yield Curve", "currency": "GBP"}
            ]

            # Cache the result
            await self.cache_manager.set_curves(
                user_info["user_id"], user_info["tenant_id"], curves
            )

            return {
                "curves": curves,
                "cached": False,
                "user": user_info["user_id"],
                "tenant": user_info["tenant_id"]
            }

        @self.app.post("/api/v1/cache/warm")
        async def warm_cache(request: Request):
            """Warm cache for user (admin endpoint)."""
            try:
                user_info = await self.auth_middleware.process_request(
                    request, "admin", "cache"
                )

                # Warm cache for the user
                await self.cache_manager.warm_cache(
                    user_info["user_id"], user_info["tenant_id"]
                )

                return {
                    "message": "Cache warmed successfully",
                    "user": user_info["user_id"],
                    "tenant": user_info["tenant_id"]
                }
            except Exception as e:
                self.logger.error("Cache warming error", error=str(e))
                raise

        @self.app.get("/api/v1/circuit-breakers")
        async def get_circuit_breakers():
            """Get circuit breaker status."""
            try:
                circuit_breaker_states = circuit_breaker_manager.get_all_states()
                return {
                    "circuit_breakers": circuit_breaker_states,
                    "count": len(circuit_breaker_states)
                }
            except Exception as e:
                self.logger.error("Circuit breaker status error", error=str(e))
                return {"error": str(e)}

        @self.app.get("/api/v1/rate-limits")
        async def get_rate_limits():
            """Get rate limiting status."""
            try:
                global_stats = await self.rate_limiter.get_global_stats()
                return {
                    "rate_limits": global_stats,
                    "configured_limits": self.rate_limiter.default_limits
                }
            except Exception as e:
                self.logger.error("Rate limit status error", error=str(e))
                return {"error": str(e)}

        @self.app.get("/api/v1/cache/stats")
        async def get_cache_stats():
            """Get cache statistics."""
            try:
                cache_stats = await self.cache_manager.get_cache_stats()
                return cache_stats
            except Exception as e:
                self.logger.error("Cache stats error", error=str(e))
                return {"error": str(e)}

        @self.app.get("/api/v1/instruments/fallback")
        async def get_instruments_fallback():
            """Fallback instruments endpoint when services are unavailable."""
            return {
                "instruments": [
                    {"id": "EURUSD", "name": "Euro/US Dollar (Cached)", "type": "forex"},
                    {"id": "GBPUSD", "name": "British Pound/US Dollar (Cached)", "type": "forex"},
                    {"id": "USDJPY", "name": "US Dollar/Japanese Yen (Cached)", "type": "forex"}
                ],
                "fallback": True,
                "message": "Service temporarily unavailable, showing cached data",
                "timestamp": time.time()
            }

        @self.app.get("/api/v1/curves/fallback")
        async def get_curves_fallback():
            """Fallback curves endpoint when services are unavailable."""
            return {
                "curves": [
                    {"id": "USD_CURVE", "name": "USD Yield Curve (Cached)", "currency": "USD"},
                    {"id": "EUR_CURVE", "name": "EUR Yield Curve (Cached)", "currency": "EUR"},
                    {"id": "GBP_CURVE", "name": "GBP Yield Curve (Cached)", "currency": "GBP"}
                ],
                "fallback": True,
                "message": "Service temporarily unavailable, showing cached data",
                "timestamp": time.time()
            }
        
        @self.app.get("/api/v1/products")
        async def get_products(request: Request):
            """Get products endpoint with authentication, rate limiting, and caching."""
            # Check rate limit first
            rate_limit_result = await self.rate_limit_middleware.check_request(request, "authenticated")
            if not rate_limit_result["allowed"]:
                raise HTTPException(
                    status_code=429,
                    detail={
                        "error": "Rate limit exceeded",
                        "current_count": rate_limit_result["current_count"],
                        "limit": rate_limit_result["limit"],
                        "reset_in_seconds": rate_limit_result["reset_in_seconds"]
                    }
                )

            try:
                user_info = await self.auth_middleware.process_request(
                    request, "read", "product"
                )
            except Exception as e:
                self.logger.error("Auth middleware error", error=str(e))
                raise

            # Check cache first
            cached_products = await self.cache_manager.get_products(
                user_info["user_id"], user_info["tenant_id"]
            )

            if cached_products:
                self.logger.info("Serving products from cache", user_id=user_info["user_id"])
                return {
                    "products": cached_products,
                    "cached": True,
                    "user": user_info["user_id"],
                    "tenant": user_info["tenant_id"]
                }

            # Fetch from ClickHouse
            try:
                import httpx
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"{self.config.clickhouse_url}/query",
                        params={
                            "query": "SELECT * FROM instruments WHERE tenant_id = %(tenant_id)s",
                            "tenant_id": user_info["tenant_id"]
                        },
                        timeout=10.0
                    )
                    response.raise_for_status()
                    clickhouse_data = response.json()
                    
                    products = clickhouse_data.get("data", [])
            except Exception as e:
                self.logger.warning("ClickHouse query failed, using fallback", error=str(e))
                # Fallback to mock data
                products = [
                    {"id": "PROD001", "name": "Oil Futures", "type": "commodity", "commodity": "oil"},
                    {"id": "PROD002", "name": "Gas Futures", "type": "commodity", "commodity": "gas"},
                    {"id": "PROD003", "name": "Power Futures", "type": "commodity", "commodity": "power"}
                ]

            # Cache the result
            await self.cache_manager.set_products(
                user_info["user_id"], user_info["tenant_id"], products
            )

            return {
                "products": products,
                "cached": False,
                "user": user_info["user_id"],
                "tenant": user_info["tenant_id"]
            }
        
        @self.app.get("/api/v1/pricing")
        async def get_pricing(request: Request):
            """Get pricing data endpoint with authentication, rate limiting, and caching."""
            # Check rate limit first
            rate_limit_result = await self.rate_limit_middleware.check_request(request, "authenticated")
            if not rate_limit_result["allowed"]:
                raise HTTPException(
                    status_code=429,
                    detail={
                        "error": "Rate limit exceeded",
                        "current_count": rate_limit_result["current_count"],
                        "limit": rate_limit_result["limit"],
                        "reset_in_seconds": rate_limit_result["reset_in_seconds"]
                    }
                )

            try:
                user_info = await self.auth_middleware.process_request(
                    request, "read", "pricing"
                )
            except Exception as e:
                self.logger.error("Auth middleware error", error=str(e))
                raise

            # Check cache first
            cached_pricing = await self.cache_manager.get_pricing(
                user_info["user_id"], user_info["tenant_id"]
            )

            if cached_pricing:
                self.logger.info("Serving pricing from cache", user_id=user_info["user_id"])
                return {
                    "pricing": cached_pricing,
                    "cached": True,
                    "user": user_info["user_id"],
                    "tenant": user_info["tenant_id"]
                }

            # Fetch from ClickHouse
            try:
                import httpx
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"{self.config.clickhouse_url}/query",
                        params={
                            "query": "SELECT * FROM pricing_data WHERE tenant_id = %(tenant_id)s ORDER BY timestamp DESC LIMIT 100",
                            "tenant_id": user_info["tenant_id"]
                        },
                        timeout=10.0
                    )
                    response.raise_for_status()
                    clickhouse_data = response.json()
                    
                    pricing = clickhouse_data.get("data", [])
            except Exception as e:
                self.logger.warning("ClickHouse query failed, using fallback", error=str(e))
                # Fallback to mock data
                pricing = [
                    {"instrument_id": "INST001", "price": 52.50, "volume": 1000, "timestamp": "2024-01-01T12:00:00Z"},
                    {"instrument_id": "INST002", "price": 45.20, "volume": 1500, "timestamp": "2024-01-01T12:00:00Z"},
                    {"instrument_id": "INST003", "price": 3.15, "volume": 2000, "timestamp": "2024-01-01T12:00:00Z"}
                ]

            # Cache the result
            await self.cache_manager.set_pricing(
                user_info["user_id"], user_info["tenant_id"], pricing
            )

            return {
                "pricing": pricing,
                "cached": False,
                "user": user_info["user_id"],
                "tenant": user_info["tenant_id"]
            }
        
        @self.app.get("/api/v1/historical")
        async def get_historical(request: Request):
            """Get historical data endpoint with authentication, rate limiting, and caching."""
            # Check rate limit first
            rate_limit_result = await self.rate_limit_middleware.check_request(request, "authenticated")
            if not rate_limit_result["allowed"]:
                raise HTTPException(
                    status_code=429,
                    detail={
                        "error": "Rate limit exceeded",
                        "current_count": rate_limit_result["current_count"],
                        "limit": rate_limit_result["limit"],
                        "reset_in_seconds": rate_limit_result["reset_in_seconds"]
                    }
                )

            try:
                user_info = await self.auth_middleware.process_request(
                    request, "read", "historical"
                )
            except Exception as e:
                self.logger.error("Auth middleware error", error=str(e))
                raise

            # Check cache first
            cached_historical = await self.cache_manager.get_historical(
                user_info["user_id"], user_info["tenant_id"]
            )

            if cached_historical:
                self.logger.info("Serving historical data from cache", user_id=user_info["user_id"])
                return {
                    "historical": cached_historical,
                    "cached": True,
                    "user": user_info["user_id"],
                    "tenant": user_info["tenant_id"]
                }

            # Fetch from ClickHouse
            try:
                import httpx
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"{self.config.clickhouse_url}/query",
                        params={
                            "query": "SELECT * FROM pricing_data WHERE tenant_id = %(tenant_id)s AND timestamp >= now() - INTERVAL 30 DAY ORDER BY timestamp DESC",
                            "tenant_id": user_info["tenant_id"]
                        },
                        timeout=10.0
                    )
                    response.raise_for_status()
                    clickhouse_data = response.json()
                    
                    historical = clickhouse_data.get("data", [])
            except Exception as e:
                self.logger.warning("ClickHouse query failed, using fallback", error=str(e))
                # Fallback to mock data
                historical = [
                    {"instrument_id": "INST001", "price": 52.50, "volume": 1000, "timestamp": "2024-01-01T12:00:00Z"},
                    {"instrument_id": "INST001", "price": 52.45, "volume": 1200, "timestamp": "2024-01-01T11:00:00Z"},
                    {"instrument_id": "INST001", "price": 52.60, "volume": 800, "timestamp": "2024-01-01T10:00:00Z"}
                ]

            # Cache the result
            await self.cache_manager.set_historical(
                user_info["user_id"], user_info["tenant_id"], historical
            )

            return {
                "historical": historical,
                "cached": False,
                "user": user_info["user_id"],
                "tenant": user_info["tenant_id"]
            }

        @self.app.get("/api/v1/served/latest-price/{instrument_id}")
        @observe_function("gateway_get_served_latest_price")
        async def get_served_latest_price(instrument_id: str, request: Request):
            """Get served latest price projection."""
            rate_limit_result = await self.rate_limit_middleware.check_request(request, "authenticated")
            if not rate_limit_result["allowed"]:
                raise HTTPException(
                    status_code=429,
                    detail={
                        "error": "Rate limit exceeded",
                        "current_count": rate_limit_result["current_count"],
                        "limit": rate_limit_result["limit"],
                        "reset_in_seconds": rate_limit_result["reset_in_seconds"]
                    }
                )

            normalized_instrument = instrument_id.upper()

            try:
                user_info = await self.auth_middleware.process_request(
                    request, "read", "market_data"
                )
            except Exception as e:
                self.logger.error("Auth middleware error", error=str(e))
                raise

            tenant_id = user_info["tenant_id"]

            # Attempt cache read
            cached_projection = await self.cache_manager.get_served_latest_price(
                tenant_id, normalized_instrument
            )
            if cached_projection:
                self.observability.log_business_event(
                    "served_latest_price_cache_hit",
                    instrument_id=normalized_instrument,
                    tenant_id=tenant_id,
                    user_id=user_info["user_id"]
                )
                return {
                    "projection": cached_projection,
                    "cached": True,
                    "instrument_id": normalized_instrument,
                    "tenant": tenant_id
                }

            # Fetch from served data service
            try:
                projection = await self.served_client.get_latest_price(
                    tenant_id, normalized_instrument
                )
            except ExternalServiceError as exc:
                self.logger.error(
                    "Served latest price fetch error",
                    instrument_id=normalized_instrument,
                    tenant_id=tenant_id,
                    error=str(exc)
                )
                raise HTTPException(status_code=502, detail="Served data unavailable") from None

            if projection is None:
                raise HTTPException(status_code=404, detail="Served latest price not found")

            await self.cache_manager.set_served_latest_price(
                tenant_id, normalized_instrument, projection
            )

            self.observability.log_business_event(
                "served_latest_price_fetched",
                instrument_id=normalized_instrument,
                tenant_id=tenant_id,
                user_id=user_info["user_id"]
            )

            return {
                "projection": projection,
                "cached": False,
                "instrument_id": normalized_instrument,
                "tenant": tenant_id
            }

        @self.app.get("/api/v1/served/curve-snapshots/{instrument_id}")
        @observe_function("gateway_get_served_curve_snapshot")
        async def get_served_curve_snapshot(
            instrument_id: str,
            request: Request,
            horizon: str = Query(..., description="Projection horizon identifier")
        ):
            """Get served curve snapshot projection."""
            rate_limit_result = await self.rate_limit_middleware.check_request(request, "authenticated")
            if not rate_limit_result["allowed"]:
                raise HTTPException(
                    status_code=429,
                    detail={
                        "error": "Rate limit exceeded",
                        "current_count": rate_limit_result["current_count"],
                        "limit": rate_limit_result["limit"],
                        "reset_in_seconds": rate_limit_result["reset_in_seconds"]
                    }
                )

            normalized_instrument = instrument_id.upper()
            normalized_horizon = horizon.lower()

            try:
                user_info = await self.auth_middleware.process_request(
                    request, "read", "market_data"
                )
            except Exception as e:
                self.logger.error("Auth middleware error", error=str(e))
                raise

            tenant_id = user_info["tenant_id"]

            cached_projection = await self.cache_manager.get_served_curve_snapshot(
                tenant_id, normalized_instrument, normalized_horizon
            )
            if cached_projection:
                self.observability.log_business_event(
                    "served_curve_snapshot_cache_hit",
                    instrument_id=normalized_instrument,
                    tenant_id=tenant_id,
                    user_id=user_info["user_id"],
                    horizon=normalized_horizon
                )
                return {
                    "projection": cached_projection,
                    "cached": True,
                    "instrument_id": normalized_instrument,
                    "tenant": tenant_id,
                    "horizon": normalized_horizon
                }

            try:
                projection = await self.served_client.get_curve_snapshot(
                    tenant_id, normalized_instrument, normalized_horizon
                )
            except ExternalServiceError as exc:
                self.logger.error(
                    "Served curve snapshot fetch error",
                    instrument_id=normalized_instrument,
                    tenant_id=tenant_id,
                    horizon=normalized_horizon,
                    error=str(exc)
                )
                raise HTTPException(status_code=502, detail="Served data unavailable") from None

            if projection is None:
                raise HTTPException(status_code=404, detail="Served curve snapshot not found")

            await self.cache_manager.set_served_curve_snapshot(
                tenant_id, normalized_instrument, normalized_horizon, projection
            )

            self.observability.log_business_event(
                "served_curve_snapshot_fetched",
                instrument_id=normalized_instrument,
                tenant_id=tenant_id,
                user_id=user_info["user_id"],
                horizon=normalized_horizon
            )

            return {
                "projection": projection,
                "cached": False,
                "instrument_id": normalized_instrument,
                "tenant": tenant_id,
                "horizon": normalized_horizon
            }

        @self.app.get("/api/v1/served/custom/{projection_type}/{instrument_id}")
        @observe_function("gateway_get_served_custom_projection")
        async def get_served_custom_projection(
            projection_type: str,
            instrument_id: str,
            request: Request
        ):
            """Get served custom projection."""
            rate_limit_result = await self.rate_limit_middleware.check_request(request, "authenticated")
            if not rate_limit_result["allowed"]:
                raise HTTPException(
                    status_code=429,
                    detail={
                        "error": "Rate limit exceeded",
                        "current_count": rate_limit_result["current_count"],
                        "limit": rate_limit_result["limit"],
                        "reset_in_seconds": rate_limit_result["reset_in_seconds"]
                    }
                )

            normalized_instrument = instrument_id.upper()
            normalized_type = projection_type.lower()

            try:
                user_info = await self.auth_middleware.process_request(
                    request, "read", "market_data"
                )
            except Exception as e:
                self.logger.error("Auth middleware error", error=str(e))
                raise

            tenant_id = user_info["tenant_id"]

            cached_projection = await self.cache_manager.get_served_custom(
                tenant_id, normalized_type, normalized_instrument
            )
            if cached_projection:
                self.observability.log_business_event(
                    "served_custom_projection_cache_hit",
                    instrument_id=normalized_instrument,
                    tenant_id=tenant_id,
                    user_id=user_info["user_id"],
                    projection_type=normalized_type
                )
                return {
                    "projection": cached_projection,
                    "cached": True,
                    "instrument_id": normalized_instrument,
                    "tenant": tenant_id,
                    "projection_type": normalized_type
                }

            try:
                projection = await self.served_client.get_custom_projection(
                    tenant_id, normalized_instrument, normalized_type
                )
            except ExternalServiceError as exc:
                self.logger.error(
                    "Served custom projection fetch error",
                    instrument_id=normalized_instrument,
                    tenant_id=tenant_id,
                    projection_type=normalized_type,
                    error=str(exc)
                )
                raise HTTPException(status_code=502, detail="Served data unavailable") from None

            if projection is None:
                raise HTTPException(status_code=404, detail="Served custom projection not found")

            await self.cache_manager.set_served_custom(
                tenant_id, normalized_type, normalized_instrument, projection
            )

            self.observability.log_business_event(
                "served_custom_projection_fetched",
                instrument_id=normalized_instrument,
                tenant_id=tenant_id,
                user_id=user_info["user_id"],
                projection_type=normalized_type
            )

            return {
                "projection": projection,
                "cached": False,
                "instrument_id": normalized_instrument,
                "tenant": tenant_id,
                "projection_type": normalized_type
            }
        
        @self.app.get("/api/v1/auth/api-key")
        async def authenticate_with_api_key(
            x_api_key: str = Header(..., alias="X-API-Key")
        ):
            """API key authentication endpoint."""
            try:
                if x_api_key not in self.api_keys:
                    raise HTTPException(status_code=401, detail="Invalid API key")
                
                api_key_info = self.api_keys[x_api_key]
                
                # Create mock user info for API key
                user_info = {
                    "user_id": f"api-key-{x_api_key}",
                    "tenant_id": api_key_info["tenant_id"],
                    "roles": api_key_info["roles"],
                    "auth_method": "api_key"
                }
                
                self.logger.info(
                    "API key authentication successful",
                    api_key=x_api_key[:8] + "...",
                    tenant_id=api_key_info["tenant_id"]
                )
                
                return {
                    "authenticated": True,
                    "user_info": user_info,
                    "expires_in": 3600  # 1 hour
                }
                
            except HTTPException:
                raise
            except Exception as e:
                self.logger.error("API key authentication error", error=str(e))
                raise HTTPException(status_code=500, detail="Authentication error")
    
    def _check_dependencies(self):
        """Check gateway dependencies."""
        dependencies = {}
        
        # Check Redis
        try:
            import redis
            r = redis.Redis.from_url(self.config.redis_url)
            r.ping()
            dependencies["redis"] = "ok"
        except Exception:
            dependencies["redis"] = "error"
        
        # Check auth service
        try:
            import httpx
            with httpx.Client(timeout=5.0) as client:
                response = client.get(f"{self.config.auth_service_url}/health")
            dependencies["auth"] = "ok" if response.status_code == 200 else "error"
        except Exception:
            dependencies["auth"] = "error"
        
        # Check entitlements service
        try:
            import httpx
            with httpx.Client(timeout=5.0) as client:
                response = client.get(f"{self.config.entitlements_service_url}/health")
            dependencies["entitlements"] = "ok" if response.status_code == 200 else "error"
        except Exception:
            dependencies["entitlements"] = "error"
        
        return dependencies


def create_app():
    """Create FastAPI application."""
    service = GatewayService()
    return service.app


if __name__ == "__main__":
    service = GatewayService()
    service.run()
