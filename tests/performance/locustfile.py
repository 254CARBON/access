"""
Load testing for 254Carbon Access Layer using Locust.

This file contains load tests for:
- Gateway Service REST endpoints
- Streaming Service WebSocket connections
- Authentication flows
- Entitlement checks
- Metrics collection
"""

import json
import random
import time
from typing import Dict, Any, List
import asyncio
import websockets
from locust import HttpUser, TaskSet, task, between, events
from locust.exception import StopUser


SERVED_LATEST_INSTRUMENTS = [
    "NG_HH_BALMO",
    "ERCOT_HOUSTON_15MIN",
    "NBP_GAS_DA",
    "EU_POWER_PHELIX",
    "WTI_CRUDE_FRONT",
]

SERVED_CURVE_TARGETS = [
    ("NG_HH_BALMO", "1m"),
    ("ERCOT_HOUSTON_15MIN", "da"),
    ("NBP_GAS_DA", "2w"),
    ("EU_POWER_PHELIX", "1q"),
    ("WTI_CRUDE_FRONT", "3m"),
]


class GatewayRESTTasks(TaskSet):
    """Load tests for Gateway Service REST endpoints."""
    
    def on_start(self):
        """Setup for each user."""
        self.token = self.get_auth_token()
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
    
    def get_auth_token(self) -> str:
        """Get authentication token."""
        # Mock JWT token for testing
        return "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c2VyLTEyMyIsInRlbmFudF9pZCI6InRlbmFudC0xIiwicm9sZXMiOlsidXNlciIsImFuYWx5c3QiXSwiZXhwIjoxNzA1MzE1ODAwfQ.test"
    
    @task(3)
    def get_instruments(self):
        """Test instruments endpoint."""
        with self.client.get("/api/v1/instruments", headers=self.headers, catch_response=True) as response:
            if response.status_code == 200:
                data = response.json()
                if "instruments" in data:
                    response.success()
                else:
                    response.failure("Missing instruments in response")
            elif response.status_code == 429:
                response.failure("Rate limited")
            else:
                response.failure(f"Unexpected status code: {response.status_code}")
    
    @task(3)
    def get_curves(self):
        """Test curves endpoint."""
        with self.client.get("/api/v1/curves", headers=self.headers, catch_response=True) as response:
            if response.status_code == 200:
                data = response.json()
                if "curves" in data:
                    response.success()
                else:
                    response.failure("Missing curves in response")
            elif response.status_code == 429:
                response.failure("Rate limited")
            else:
                response.failure(f"Unexpected status code: {response.status_code}")
    
    @task(2)
    def get_products(self):
        """Test products endpoint."""
        with self.client.get("/api/v1/products", headers=self.headers, catch_response=True) as response:
            if response.status_code == 200:
                data = response.json()
                if "products" in data:
                    response.success()
                else:
                    response.failure("Missing products in response")
            elif response.status_code == 429:
                response.failure("Rate limited")
            else:
                response.failure(f"Unexpected status code: {response.status_code}")
    
    @task(2)
    def get_pricing(self):
        """Test pricing endpoint."""
        with self.client.get("/api/v1/pricing", headers=self.headers, catch_response=True) as response:
            if response.status_code == 200:
                data = response.json()
                if "pricing" in data:
                    response.success()
                else:
                    response.failure("Missing pricing in response")
            elif response.status_code == 429:
                response.failure("Rate limited")
            else:
                response.failure(f"Unexpected status code: {response.status_code}")
    
    @task(1)
    def get_historical(self):
        """Test historical data endpoint."""
        with self.client.get("/api/v1/historical", headers=self.headers, catch_response=True) as response:
            if response.status_code == 200:
                data = response.json()
                if "historical" in data:
                    response.success()
                else:
                    response.failure("Missing historical data in response")
            elif response.status_code == 429:
                response.failure("Rate limited")
            else:
                response.failure(f"Unexpected status code: {response.status_code}")
    
    @task(1)
    def get_cache_stats(self):
        """Test cache statistics endpoint."""
        with self.client.get("/api/v1/cache/stats", catch_response=True) as response:
            if response.status_code == 200:
                data = response.json()
                if "hit_ratio" in data:
                    response.success()
                else:
                    response.failure("Missing hit_ratio in response")
            else:
                response.failure(f"Unexpected status code: {response.status_code}")
    
    @task(1)
    def get_rate_limits(self):
        """Test rate limits endpoint."""
        with self.client.get("/api/v1/rate-limits", catch_response=True) as response:
            if response.status_code == 200:
                data = response.json()
                if "rate_limits" in data:
                    response.success()
                else:
                    response.failure("Missing rate_limits in response")
            else:
                response.failure(f"Unexpected status code: {response.status_code}")
    
    @task(1)
    def get_circuit_breakers(self):
        """Test circuit breakers endpoint."""
        with self.client.get("/api/v1/circuit-breakers", catch_response=True) as response:
            if response.status_code == 200:
                data = response.json()
                if "circuit_breakers" in data:
                    response.success()
                else:
                    response.failure("Missing circuit_breakers in response")
            else:
                response.failure(f"Unexpected status code: {response.status_code}")
    
    @task(1)
    def warm_cache(self):
        """Test cache warming endpoint."""
        with self.client.post("/api/v1/cache/warm", headers=self.headers, catch_response=True) as response:
            if response.status_code == 200:
                data = response.json()
                if "message" in data:
                    response.success()
                else:
                    response.failure("Missing message in response")
            elif response.status_code == 429:
                response.failure("Rate limited")
            else:
                response.failure(f"Unexpected status code: {response.status_code}")

    @task(2)
    def get_served_latest_price(self):
        """Exercise served latest price endpoint."""
        instrument = random.choice(SERVED_LATEST_INSTRUMENTS)
        with self.client.get(
            f"/api/v1/served/latest-price/{instrument}",
            headers=self.headers,
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                payload = response.json()
                if "projection" in payload:
                    response.success()
                else:
                    response.failure("Missing projection in latest price response")
            elif response.status_code == 404:
                response.failure("Served latest price not found")
            else:
                response.failure(f"Unexpected status code: {response.status_code}")

    @task(2)
    def get_served_curve_snapshot(self):
        """Exercise served curve snapshot endpoint."""
        instrument_id, horizon = random.choice(SERVED_CURVE_TARGETS)
        with self.client.get(
            f"/api/v1/served/curve-snapshots/{instrument_id}",
            headers=self.headers,
            params={"horizon": horizon},
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                payload = response.json()
                if "projection" in payload:
                    response.success()
                else:
                    response.failure("Missing projection in curve snapshot response")
            elif response.status_code == 404:
                response.failure("Served curve snapshot not found")
            else:
                response.failure(f"Unexpected status code: {response.status_code}")


class StreamingWebSocketTasks(TaskSet):
    """Load tests for Streaming Service WebSocket connections."""
    
    def on_start(self):
        """Setup for each user."""
        self.token = self.get_auth_token()
        self.websocket = None
        self.connection_id = None
        self.subscribed_topics = []
    
    def get_auth_token(self) -> str:
        """Get authentication token."""
        return "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c2VyLTEyMyIsInRlbmFudF9pZCI6InRlbmFudC0xIiwicm9sZXMiOlsidXNlciIsImFuYWx5c3QiXSwiZXhwIjoxNzA1MzE1ODAwfQ.test"
    
    @task(1)
    def connect_websocket(self):
        """Test WebSocket connection."""
        try:
            # Note: This is a simplified test - real WebSocket testing would require async setup
            # For now, we'll test the connection endpoint
            with self.client.get(f"/ws/stream?token={self.token}", catch_response=True) as response:
                if response.status_code in [101, 426]:  # WebSocket upgrade or upgrade required
                    response.success()
                else:
                    response.failure(f"WebSocket connection failed: {response.status_code}")
        except Exception as e:
            self.client.events.request_failure.fire(
                request_type="WebSocket",
                name="connect",
                response_time=0,
                response_length=0,
                exception=e
            )
    
    @task(2)
    def test_sse_stream(self):
        """Test SSE stream endpoint."""
        try:
            with self.client.get(f"/sse/stream?token={self.token}", 
                               catch_response=True, 
                               stream=True) as response:
                if response.status_code == 200:
                    # Read a few lines to verify SSE is working
                    lines_read = 0
                    for line in response.iter_lines():
                        if line:
                            lines_read += 1
                            if lines_read >= 3:  # Read first few lines
                                break
                    response.success()
                else:
                    response.failure(f"SSE stream failed: {response.status_code}")
        except Exception as e:
            self.client.events.request_failure.fire(
                request_type="SSE",
                name="stream",
                response_time=0,
                response_length=0,
                exception=e
            )
    
    @task(1)
    def test_sse_subscribe(self):
        """Test SSE subscription endpoint."""
        connection_id = f"conn-{random.randint(1000, 9999)}"
        topics = ["pricing.updates", "curve.changes"]
        topic = random.choice(topics)
        
        filters = json.dumps({"commodity": "oil"})
        
        with self.client.post("/sse/subscribe", 
                            params={
                                "connection_id": connection_id,
                                "topic": topic,
                                "filters": filters
                            },
                            catch_response=True) as response:
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    response.success()
                else:
                    response.failure("Subscription failed")
            else:
                response.failure(f"Subscription request failed: {response.status_code}")


class AuthServiceTasks(TaskSet):
    """Load tests for Auth Service."""
    
    def on_start(self):
        """Setup for each user."""
        self.token = self.get_auth_token()
    
    def get_auth_token(self) -> str:
        """Get authentication token."""
        return "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c2VyLTEyMyIsInRlbmFudF9pZCI6InRlbmFudC0xIiwicm9sZXMiOlsidXNlciIsImFuYWx5c3QiXSwiZXhwIjoxNzA1MzE1ODAwfQ.test"
    
    @task(3)
    def verify_token(self):
        """Test token verification."""
        with self.client.post("/auth/verify", 
                            json={"token": self.token},
                            catch_response=True) as response:
            if response.status_code == 200:
                data = response.json()
                if data.get("valid"):
                    response.success()
                else:
                    response.failure("Token validation failed")
            else:
                response.failure(f"Token verification failed: {response.status_code}")
    
    @task(2)
    def verify_websocket_token(self):
        """Test WebSocket token verification."""
        with self.client.post("/auth/verify-ws", 
                            json={"token": self.token},
                            catch_response=True) as response:
            if response.status_code == 200:
                data = response.json()
                if data.get("valid"):
                    response.success()
                else:
                    response.failure("WebSocket token validation failed")
            else:
                response.failure(f"WebSocket token verification failed: {response.status_code}")
    
    @task(1)
    def get_user_info(self):
        """Test user info retrieval."""
        user_id = f"user-{random.randint(100, 999)}"
        with self.client.get(f"/auth/users/{user_id}", catch_response=True) as response:
            if response.status_code in [200, 404]:  # 404 is expected for non-existent users
                response.success()
            else:
                response.failure(f"User info retrieval failed: {response.status_code}")


class EntitlementsServiceTasks(TaskSet):
    """Load tests for Entitlements Service."""
    
    def on_start(self):
        """Setup for each user."""
        self.user_id = f"user-{random.randint(100, 999)}"
        self.tenant_id = f"tenant-{random.randint(1, 5)}"
    
    @task(5)
    def check_entitlements(self):
        """Test entitlement checks."""
        resources = ["curve", "instrument", "product", "pricing"]
        actions = ["read", "write", "delete"]
        
        resource = random.choice(resources)
        action = random.choice(actions)
        
        payload = {
            "user_id": self.user_id,
            "tenant_id": self.tenant_id,
            "resource": resource,
            "action": action,
            "context": {
                "user_roles": ["user", "analyst"],
                "resource_id": f"{resource}-{random.randint(1, 100)}",
                "commodity": "oil"
            }
        }
        
        with self.client.post("/entitlements/check", 
                            json=payload,
                            catch_response=True) as response:
            if response.status_code == 200:
                data = response.json()
                if "allowed" in data:
                    response.success()
                else:
                    response.failure("Missing allowed field in response")
            else:
                response.failure(f"Entitlement check failed: {response.status_code}")
    
    @task(1)
    def get_rules(self):
        """Test rules retrieval."""
        with self.client.get("/entitlements/rules", catch_response=True) as response:
            if response.status_code == 200:
                data = response.json()
                if "rules" in data:
                    response.success()
                else:
                    response.failure("Missing rules in response")
            else:
                response.failure(f"Rules retrieval failed: {response.status_code}")
    
    @task(1)
    def get_stats(self):
        """Test statistics endpoint."""
        with self.client.get("/entitlements/stats", catch_response=True) as response:
            if response.status_code == 200:
                data = response.json()
                if "engine" in data:
                    response.success()
                else:
                    response.failure("Missing engine stats in response")
            else:
                response.failure(f"Stats retrieval failed: {response.status_code}")


class MetricsServiceTasks(TaskSet):
    """Load tests for Metrics Service."""
    
    def on_start(self):
        """Setup for each user."""
        self.service_name = f"test-service-{random.randint(1, 10)}"
        self.tenant_id = f"tenant-{random.randint(1, 5)}"
    
    @task(3)
    def track_metric(self):
        """Test single metric tracking."""
        metric_types = ["counter", "gauge", "histogram"]
        metric_type = random.choice(metric_types)
        
        payload = {
            "name": f"test_metric_{random.randint(1, 100)}",
            "value": random.uniform(1, 100),
            "type": metric_type,
            "labels": {
                "service": self.service_name,
                "endpoint": f"/api/v1/test{random.randint(1, 10)}",
                "method": random.choice(["GET", "POST", "PUT", "DELETE"]),
                "status_code": str(random.choice([200, 201, 400, 404, 500]))
            },
            "service": self.service_name,
            "tenant_id": self.tenant_id
        }
        
        with self.client.post("/metrics/track", 
                            json=payload,
                            catch_response=True) as response:
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    response.success()
                else:
                    response.failure("Metric tracking failed")
            else:
                response.failure(f"Metric tracking failed: {response.status_code}")
    
    @task(2)
    def track_batch_metrics(self):
        """Test batch metric tracking."""
        metrics = []
        for i in range(random.randint(1, 5)):
            metrics.append({
                "name": f"batch_metric_{i}",
                "value": random.uniform(1, 100),
                "type": "gauge",
                "labels": {
                    "service": self.service_name,
                    "batch_id": f"batch-{random.randint(1, 100)}"
                },
                "service": self.service_name,
                "tenant_id": self.tenant_id
            })
        
        with self.client.post("/metrics/track/batch", 
                            json=metrics,
                            catch_response=True) as response:
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    response.success()
                else:
                    response.failure("Batch metric tracking failed")
            else:
                response.failure(f"Batch metric tracking failed: {response.status_code}")
    
    @task(1)
    def export_metrics(self):
        """Test metrics export."""
        with self.client.get("/metrics?format=prometheus", catch_response=True) as response:
            if response.status_code == 200:
                data = response.json()
                if "data" in data:
                    response.success()
                else:
                    response.failure("Missing data in export response")
            else:
                response.failure(f"Metrics export failed: {response.status_code}")
    
    @task(1)
    def get_series(self):
        """Test metric series retrieval."""
        with self.client.get("/metrics/series", catch_response=True) as response:
            if response.status_code == 200:
                data = response.json()
                if "series" in data:
                    response.success()
                else:
                    response.failure("Missing series in response")
            else:
                response.failure(f"Series retrieval failed: {response.status_code}")
    
    @task(1)
    def get_stats(self):
        """Test statistics endpoint."""
        with self.client.get("/metrics/stats", catch_response=True) as response:
            if response.status_code == 200:
                data = response.json()
                if "collector" in data:
                    response.success()
                else:
                    response.failure("Missing collector stats in response")
            else:
                response.failure(f"Stats retrieval failed: {response.status_code}")


class GatewayRESTUser(HttpUser):
    """Gateway Service REST API load test user."""
    tasks = [GatewayRESTTasks]
    wait_time = between(1, 3)
    host = "http://localhost:8000"


class StreamingUser(HttpUser):
    """Streaming Service load test user."""
    tasks = [StreamingWebSocketTasks]
    wait_time = between(2, 5)
    host = "http://localhost:8001"


class AuthServiceUser(HttpUser):
    """Auth Service load test user."""
    tasks = [AuthServiceTasks]
    wait_time = between(1, 2)
    host = "http://localhost:8010"


class EntitlementsServiceUser(HttpUser):
    """Entitlements Service load test user."""
    tasks = [EntitlementsServiceTasks]
    wait_time = between(1, 3)
    host = "http://localhost:8011"


class MetricsServiceUser(HttpUser):
    """Metrics Service load test user."""
    tasks = [MetricsServiceTasks]
    wait_time = between(1, 2)
    host = "http://localhost:8012"


# Custom event handlers for additional metrics
@events.request.add_listener
def on_request(request_type, name, response_time, response_length, exception, context, **kwargs):
    """Custom request event handler."""
    if exception:
        print(f"Request failed: {request_type} {name} - {exception}")
    elif response_time > 5000:  # Log slow requests
        print(f"Slow request: {request_type} {name} - {response_time}ms")


@events.user_error.add_listener
def on_user_error(user_instance, exception, tb, **kwargs):
    """Custom user error event handler."""
    print(f"User error: {exception}")


# Performance thresholds
class PerformanceThresholds:
    """Performance thresholds for load testing."""
    
    # Response time thresholds (milliseconds)
    RESPONSE_TIME_THRESHOLDS = {
        "gateway": {
            "instruments": 100,
            "curves": 100,
            "products": 150,
            "pricing": 200,
            "historical": 500
        },
        "auth": {
            "verify_token": 50,
            "verify_websocket_token": 50,
            "get_user_info": 100
        },
        "entitlements": {
            "check_entitlements": 100,
            "get_rules": 200,
            "get_stats": 100
        },
        "metrics": {
            "track_metric": 50,
            "track_batch_metrics": 100,
            "export_metrics": 500,
            "get_series": 200,
            "get_stats": 100
        },
        "streaming": {
            "websocket_connect": 1000,
            "sse_stream": 200,
            "sse_subscribe": 100
        }
    }
    
    # Error rate thresholds (percentage)
    ERROR_RATE_THRESHOLDS = {
        "gateway": 1.0,
        "auth": 0.5,
        "entitlements": 1.0,
        "metrics": 0.5,
        "streaming": 2.0
    }
    
    # Throughput thresholds (requests per second)
    THROUGHPUT_THRESHOLDS = {
        "gateway": 100,
        "auth": 200,
        "entitlements": 150,
        "metrics": 300,
        "streaming": 50
    }


# Load test scenarios
class LoadTestScenarios:
    """Predefined load test scenarios."""
    
    @staticmethod
    def light_load():
        """Light load scenario."""
        return {
            "gateway_users": 10,
            "auth_users": 5,
            "entitlements_users": 5,
            "metrics_users": 10,
            "streaming_users": 5,
            "duration": "5m"
        }
    
    @staticmethod
    def medium_load():
        """Medium load scenario."""
        return {
            "gateway_users": 50,
            "auth_users": 25,
            "entitlements_users": 25,
            "metrics_users": 50,
            "streaming_users": 25,
            "duration": "10m"
        }
    
    @staticmethod
    def heavy_load():
        """Heavy load scenario."""
        return {
            "gateway_users": 100,
            "auth_users": 50,
            "entitlements_users": 50,
            "metrics_users": 100,
            "streaming_users": 50,
            "duration": "15m"
        }
    
    @staticmethod
    def stress_test():
        """Stress test scenario."""
        return {
            "gateway_users": 200,
            "auth_users": 100,
            "entitlements_users": 100,
            "metrics_users": 200,
            "streaming_users": 100,
            "duration": "20m"
        }


# Example usage commands:
"""
# Light load test
locust -f tests/performance/locustfile.py \
  --host=http://localhost:8000 \
  --users=10 \
  --spawn-rate=2 \
  --run-time=5m

# Medium load test
locust -f tests/performance/locustfile.py \
  --host=http://localhost:8000 \
  --users=50 \
  --spawn-rate=5 \
  --run-time=10m

# Heavy load test
locust -f tests/performance/locustfile.py \
  --host=http://localhost:8000 \
  --users=100 \
  --spawn-rate=10 \
  --run-time=15m

# Stress test
locust -f tests/performance/locustfile.py \
  --host=http://localhost:8000 \
  --users=200 \
  --spawn-rate=20 \
  --run-time=20m

# Test specific service
locust -f tests/performance/locustfile.py \
  GatewayRESTUser \
  --host=http://localhost:8000 \
  --users=50 \
  --spawn-rate=5 \
  --run-time=10m
"""
