"""
Test helper functions and factory methods for 254Carbon Access Layer.
"""

import json
import time
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from dataclasses import dataclass
import jwt


@dataclass
class TestUser:
    """Test user data."""
    user_id: str
    username: str
    email: str
    tenant_id: str
    roles: List[str]
    password: str = "password123"


@dataclass
class TestToken:
    """Test token data."""
    access_token: str
    refresh_token: str
    expires_in: int
    token_type: str = "Bearer"


class TestDataFactory:
    """Factory for creating test data."""
    
    @staticmethod
    def create_test_users() -> List[TestUser]:
        """Create test users."""
        return [
            TestUser(
                user_id="user1",
                username="john.doe",
                email="john.doe@254carbon.com",
                tenant_id="tenant-1",
                roles=["user", "analyst"]
            ),
            TestUser(
                user_id="user2",
                username="jane.smith", 
                email="jane.smith@254carbon.com",
                tenant_id="tenant-2",
                roles=["user", "admin"]
            ),
            TestUser(
                user_id="admin",
                username="admin",
                email="admin@254carbon.com",
                tenant_id="tenant-1",
                roles=["admin", "superuser"]
            )
        ]
    
    @staticmethod
    def create_test_instruments() -> List[Dict[str, Any]]:
        """Create test instruments."""
        return [
            {
                "id": "INST001",
                "symbol": "BRN",
                "name": "Brent Crude Oil",
                "type": "commodity",
                "commodity": "oil",
                "exchange": "ICE",
                "currency": "USD",
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z"
            },
            {
                "id": "INST002",
                "symbol": "WTI", 
                "name": "West Texas Intermediate",
                "type": "commodity",
                "commodity": "oil",
                "exchange": "NYMEX",
                "currency": "USD",
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z"
            },
            {
                "id": "INST003",
                "symbol": "NG",
                "name": "Natural Gas",
                "type": "commodity",
                "commodity": "gas", 
                "exchange": "NYMEX",
                "currency": "USD",
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z"
            }
        ]
    
    @staticmethod
    def create_test_curves() -> List[Dict[str, Any]]:
        """Create test curves."""
        return [
            {
                "id": "CURVE_OIL_1M",
                "name": "Oil 1M Curve",
                "commodity": "oil",
                "tenor": "1M",
                "price": 52.0,
                "timestamp": datetime.now().isoformat(),
                "tenant_id": "tenant-1"
            },
            {
                "id": "CURVE_OIL_3M",
                "name": "Oil 3M Curve", 
                "commodity": "oil",
                "tenor": "3M",
                "price": 54.0,
                "timestamp": datetime.now().isoformat(),
                "tenant_id": "tenant-1"
            },
            {
                "id": "CURVE_GAS_1M",
                "name": "Gas 1M Curve",
                "commodity": "gas",
                "tenor": "1M", 
                "price": 3.2,
                "timestamp": datetime.now().isoformat(),
                "tenant_id": "tenant-1"
            }
        ]
    
    @staticmethod
    def create_test_pricing_data() -> List[Dict[str, Any]]:
        """Create test pricing data."""
        pricing_data = []
        base_time = datetime.now() - timedelta(hours=1)
        
        for i in range(10):
            timestamp = base_time + timedelta(minutes=i * 5)
            for instrument_id in ["INST001", "INST002", "INST003"]:
                base_price = 50.0 if instrument_id == "INST001" else 45.0 if instrument_id == "INST002" else 3.0
                price = base_price + (i * 0.1)
                
                pricing_data.append({
                    "instrument_id": instrument_id,
                    "timestamp": timestamp.isoformat(),
                    "price": round(price, 2),
                    "volume": round(1000 + i * 100, 2),
                    "bid": round(price - 0.01, 2),
                    "ask": round(price + 0.01, 2),
                    "tenant_id": "tenant-1"
                })
        
        return pricing_data
    
    @staticmethod
    def create_test_entitlement_rules() -> List[Dict[str, Any]]:
        """Create test entitlement rules."""
        return [
            {
                "rule_id": "rule1",
                "name": "Admin Access",
                "description": "Full access for admin users",
                "conditions": [
                    {
                        "field": "user_roles",
                        "operator": "contains",
                        "value": "admin"
                    }
                ],
                "action": "allow",
                "priority": 100,
                "resource": "*",
                "tenant_id": "*"
            },
            {
                "rule_id": "rule2",
                "name": "Tenant Isolation",
                "description": "Users can only access their tenant data",
                "conditions": [
                    {
                        "field": "tenant_id",
                        "operator": "equals",
                        "value": "{{user_tenant_id}}"
                    }
                ],
                "action": "allow",
                "priority": 50,
                "resource": "*",
                "tenant_id": "*"
            },
            {
                "rule_id": "rule3",
                "name": "Read Only Access",
                "description": "Read-only access for regular users",
                "conditions": [
                    {
                        "field": "action",
                        "operator": "equals",
                        "value": "read"
                    },
                    {
                        "field": "user_roles",
                        "operator": "contains",
                        "value": "user"
                    }
                ],
                "action": "allow",
                "priority": 10,
                "resource": "*",
                "tenant_id": "*"
            }
        ]
    
    @staticmethod
    def create_test_metrics() -> List[Dict[str, Any]]:
        """Create test metrics."""
        return [
            {
                "name": "http_requests_total",
                "type": "counter",
                "value": 1000,
                "labels": {
                    "method": "GET",
                    "endpoint": "/api/v1/instruments",
                    "status": "200"
                },
                "timestamp": datetime.now().isoformat(),
                "service": "gateway"
            },
            {
                "name": "http_request_duration_seconds",
                "type": "histogram",
                "value": 0.05,
                "labels": {
                    "method": "GET",
                    "endpoint": "/api/v1/curves"
                },
                "timestamp": datetime.now().isoformat(),
                "service": "gateway"
            },
            {
                "name": "websocket_connections_active",
                "type": "gauge",
                "value": 25,
                "labels": {
                    "tenant_id": "tenant-1"
                },
                "timestamp": datetime.now().isoformat(),
                "service": "streaming"
            }
        ]


class MockTokenGenerator:
    """Generate mock JWT tokens for testing."""
    
    def __init__(self, issuer: str = "http://localhost:8080/realms/254carbon", secret: str = "mock-secret"):
        self.issuer = issuer
        self.secret = secret
    
    def generate_access_token(self, user: TestUser, expires_in: int = 3600) -> str:
        """Generate access token for user."""
        now = datetime.utcnow()
        payload = {
            "iss": self.issuer,
            "sub": user.user_id,
            "aud": "access-layer",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(seconds=expires_in)).timestamp()),
            "azp": "access-layer",
            "scope": "openid profile email",
            "preferred_username": user.username,
            "email": user.email,
            "tenant_id": user.tenant_id,
            "realm_access": {
                "roles": user.roles
            },
            "resource_access": {
                "access-layer": {
                    "roles": user.roles
                }
            }
        }
        
        return jwt.encode(payload, self.secret, algorithm="HS256")
    
    def generate_refresh_token(self, user: TestUser, expires_in: int = 2592000) -> str:
        """Generate refresh token for user."""
        now = datetime.utcnow()
        payload = {
            "iss": self.issuer,
            "sub": user.user_id,
            "aud": "access-layer",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(seconds=expires_in)).timestamp()),
            "azp": "access-layer",
            "typ": "Refresh"
        }
        
        return jwt.encode(payload, self.secret, algorithm="HS256")
    
    def generate_token_pair(self, user: TestUser) -> TestToken:
        """Generate access and refresh token pair."""
        access_token = self.generate_access_token(user)
        refresh_token = self.generate_refresh_token(user)
        
        return TestToken(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=3600
        )


class TestEnvironment:
    """Test environment configuration."""
    
    @staticmethod
    def get_mock_config() -> Dict[str, Any]:
        """Get mock environment configuration."""
        return {
            "ACCESS_ENV": "test",
            "ACCESS_LOG_LEVEL": "debug",
            "ACCESS_JWKS_URL": "http://localhost:8080/realms/254carbon/protocol/openid-connect/certs",
            "ACCESS_REDIS_URL": "redis://localhost:6379/0",
            "ACCESS_CLICKHOUSE_URL": "http://localhost:8123",
            "ACCESS_POSTGRES_DSN": "postgresql://test:test@localhost:5432/test",
            "ACCESS_KAFKA_BOOTSTRAP": "localhost:9092",
            "ACCESS_METRICS_ENDPOINT": "http://localhost:8012",
            "ACCESS_ENABLE_TRACING": "false",
            "ACCESS_OTEL_EXPORTER": "http://localhost:4318",
            "ACCESS_TLS_ENABLED": "false"
        }
    
    @staticmethod
    def get_service_urls() -> Dict[str, str]:
        """Get service URLs for testing."""
        return {
            "gateway": "http://localhost:8000",
            "streaming": "http://localhost:8001",
            "auth": "http://localhost:8010",
            "entitlements": "http://localhost:8011",
            "metrics": "http://localhost:8012",
            "keycloak": "http://localhost:8080",
            "kafka": "http://localhost:9092",
            "clickhouse": "http://localhost:8123",
            "redis": "redis://localhost:6379",
            "postgres": "postgresql://test:test@localhost:5432/test"
        }


# Global instances for easy access
test_data_factory = TestDataFactory()
mock_token_generator = MockTokenGenerator()
test_environment = TestEnvironment()
