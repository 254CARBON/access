"""
Base service class for 254Carbon Access Layer services.
"""

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional
import time
import sys
import os

# Add shared directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from shared.config import get_config
from shared.logging import configure_logging, get_logger
from shared.metrics import get_metrics_collector
from shared.errors import AccessLayerException


class BaseService:
    """Base service class with common functionality."""
    
    def __init__(self, service_name: str, port: int):
        self.service_name = service_name
        self.port = port
        self.config = get_config(service_name, port)
        self.logger = get_logger(service_name)
        self.metrics = get_metrics_collector(service_name)
        
        # Configure logging
        configure_logging(service_name, self.config.log_level)
        
        # Configure tracing if enabled
        if self.config.enable_tracing:
            try:
                from shared.tracing import configure_tracing
                configure_tracing(service_name, self.config.otel_exporter)
            except ImportError:
                self.logger.warning("Tracing not available, skipping configuration")
        
        # Create FastAPI app
        self.app = self._create_app()
        
        # Set up middleware
        self._setup_middleware()
        
        # Set up routes
        self._setup_routes()
    
    def _create_app(self) -> FastAPI:
        """Create FastAPI application."""
        return FastAPI(
            title=f"{self.service_name.title()} Service",
            description=f"254Carbon Access Layer - {self.service_name.title()} Service",
            version="1.0.0",
            docs_url="/docs" if self.config.env == "local" else None,
            redoc_url="/redoc" if self.config.env == "local" else None,
        )
    
    def _setup_middleware(self):
        """Set up middleware."""
        
        # CORS middleware
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"] if self.config.env == "local" else [],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Request timing middleware
        @self.app.middleware("http")
        async def add_request_timing(request: Request, call_next):
            start_time = time.time()
            
            # Process request
            response = await call_next(request)
            
            # Calculate duration
            duration = time.time() - start_time
            
            # Record metrics
            self.metrics.record_http_request(
                method=request.method,
                endpoint=request.url.path,
                status_code=response.status_code,
                duration=duration
            )
            
            # Log request
            self.logger.info(
                "HTTP request",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=round(duration * 1000, 2)
            )
            
            return response
    
    def _setup_routes(self):
        """Set up common routes."""
        
        @self.app.get("/health")
        async def health_check():
            """Health check endpoint."""
            try:
                # Check dependencies
                dependencies = await self._check_dependencies()
                
                # Record health check
                self.metrics.record_health_check("ok")
                
                return {
                    "service": self.service_name,
                    "status": "ok",
                    "uptime_seconds": self._get_uptime(),
                    "dependencies": dependencies,
                    "version": "1.0.0",
                    "commit": os.getenv("GIT_COMMIT", "unknown")
                }
            except Exception as e:
                self.logger.error("Health check failed", error=str(e))
                self.metrics.record_health_check("error")
                return JSONResponse(
                    status_code=503,
                    content={
                        "service": self.service_name,
                        "status": "error",
                        "error": str(e)
                    }
                )
        
        @self.app.get("/metrics")
        async def metrics_endpoint():
            """Prometheus metrics endpoint."""
            from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
            return Response(
                content=generate_latest(),
                media_type=CONTENT_TYPE_LATEST
            )
        
        # Error handlers
        @self.app.exception_handler(AccessLayerException)
        async def access_layer_exception_handler(request: Request, exc: AccessLayerException):
            """Handle AccessLayerException."""
            self.logger.error(
                "Access layer error",
                code=exc.code,
                message=exc.message,
                details=exc.details
            )
            return JSONResponse(
                status_code=400,
                content=exc.to_response().dict()
            )
        
        @self.app.exception_handler(Exception)
        async def general_exception_handler(request: Request, exc: Exception):
            """Handle general exceptions."""
            self.logger.error("Unhandled exception", error=str(exc), exc_info=True)
            return JSONResponse(
                status_code=500,
                content={
                    "code": "INTERNAL_ERROR",
                    "message": "Internal server error",
                    "details": {}
                }
            )
    
    async def _check_dependencies(self) -> Dict[str, str]:
        """Check service dependencies. Override in subclasses."""
        return {}
    
    def _get_uptime(self) -> float:
        """Get service uptime in seconds."""
        if not hasattr(self, '_start_time'):
            self._start_time = time.time()
        return time.time() - self._start_time
    
    def run(self):
        """Run the service."""
        import uvicorn
        uvicorn.run(
            self.app,
            host=self.config.host,
            port=self.config.port,
            log_level=self.config.log_level.lower()
        )
