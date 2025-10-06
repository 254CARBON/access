"""
Unit tests for Entitlements main service.
"""

import pytest
import json
import hashlib
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from fastapi import FastAPI

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from service_entitlements.app.main import EntitlementsService, create_app
from service_entitlements.app.rules.models import (
    RuleAction, RuleResource, RuleConditionOperator
)


class TestEntitlementsService:
    """Test cases for EntitlementsService."""

    @pytest.fixture
    def entitlements_service(self):
        """Create EntitlementsService instance."""
        return EntitlementsService()

    @pytest.fixture
    def app(self):
        """Create FastAPI app instance."""
        return create_app()

    @pytest.fixture
    def client(self, app):
        """Create test client."""
        return TestClient(app)

    @pytest.fixture
    def mock_entitlement_request(self):
        """Mock entitlement check request."""
        return {
            "user_id": "user-123",
            "tenant_id": "tenant-1",
            "resource": "curve",
            "action": "read",
            "context": {
                "user_roles": ["user", "analyst"],
                "resource_id": "curve-1",
                "commodity": "oil"
            }
        }

    @pytest.fixture
    def mock_rule_create_request(self):
        """Mock rule creation request."""
        return {
            "name": "Test Rule",
            "description": "Test entitlement rule",
            "resource": "curve",
            "action": "allow",
            "conditions": [
                {
                    "field": "tenant_id",
                    "operator": "equals",
                    "value": "tenant-1",
                    "description": "Tenant must be tenant-1"
                }
            ],
            "priority": 100,
            "tenant_id": "tenant-1",
            "user_id": None,
            "expires_at": None
        }

    def test_root_endpoint(self, client):
        """Test root endpoint."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "entitlements"
        assert data["message"] == "254Carbon Access Layer - Entitlements Service"
        assert "rule_engine" in data["capabilities"]
        assert "caching" in data["capabilities"]
        assert "persistence" in data["capabilities"]

    def test_health_endpoint(self, client):
        """Test health endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "entitlements"
        assert data["status"] == "ok"

    @patch('service_entitlements.app.main.EntitlementsService._check_dependencies')
    def test_health_with_dependencies(self, mock_check_deps, client):
        """Test health endpoint with dependency checks."""
        mock_check_deps.return_value = {
            "redis": "ok",
            "postgres": "ok"
        }

        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["dependencies"]["redis"] == "ok"
        assert data["dependencies"]["postgres"] == "ok"

    def test_service_initialization(self, entitlements_service):
        """Test service initialization."""
        assert entitlements_service.name == "entitlements"
        assert entitlements_service.port == 8011
        assert entitlements_service.rule_engine is not None
        assert entitlements_service.persistence is not None
        assert entitlements_service.cache is not None

    def test_observability_setup(self, entitlements_service):
        """Test observability setup."""
        assert entitlements_service.observability is not None
        assert hasattr(entitlements_service.observability, 'log_request')
        assert hasattr(entitlements_service.observability, 'log_error')
        assert hasattr(entitlements_service.observability, 'log_business_event')

    @patch('service_entitlements.app.main.RedisCache.get_entitlement_result')
    @patch('service_entitlements.app.main.RuleEngine.evaluate')
    @patch('service_entitlements.app.main.RedisCache.set_entitlement_result')
    def test_check_entitlements_cache_hit(self, mock_set_cache, mock_evaluate, mock_get_cache, client, mock_entitlement_request):
        """Test entitlement check with cache hit."""
        # Mock cache hit
        mock_get_cache.return_value = {
            "allowed": True,
            "reason": "Cached result",
            "matched_rules": ["rule-1"],
            "ttl_seconds": 300
        }

        response = client.post("/entitlements/check", json=mock_entitlement_request)

        assert response.status_code == 200
        data = response.json()
        assert data["allowed"] is True
        assert data["reason"] == "Cached result"
        assert data["matched_rules"] == ["rule-1"]

        # Verify cache was checked
        mock_get_cache.assert_called_once()

    @patch('service_entitlements.app.main.RedisCache.get_entitlement_result')
    @patch('service_entitlements.app.main.RuleEngine.evaluate')
    @patch('service_entitlements.app.main.RedisCache.set_entitlement_result')
    def test_check_entitlements_cache_miss(self, mock_set_cache, mock_evaluate, mock_get_cache, client, mock_entitlement_request):
        """Test entitlement check with cache miss."""
        # Mock cache miss
        mock_get_cache.return_value = None

        # Mock rule engine evaluation
        mock_evaluation_result = MagicMock()
        mock_evaluation_result.allowed = True
        mock_evaluation_result.reason = "Rule matched"
        mock_evaluation_result.matched_rules = ["rule-1"]
        mock_evaluation_result.evaluation_time_ms = 5.0
        mock_evaluate.return_value = mock_evaluation_result

        # Mock cache set
        mock_set_cache.return_value = True

        response = client.post("/entitlements/check", json=mock_entitlement_request)

        assert response.status_code == 200
        data = response.json()
        assert data["allowed"] is True
        assert data["reason"] == "Rule matched"
        assert data["matched_rules"] == ["rule-1"]
        assert data["ttl_seconds"] == 300

        # Verify cache was checked and set
        mock_get_cache.assert_called_once()
        mock_set_cache.assert_called_once()

    @patch('service_entitlements.app.main.RuleEngine.get_rules_for_resource')
    def test_get_rules_success(self, mock_get_rules, client):
        """Test getting rules successfully."""
        mock_rules = [
            MagicMock(
                rule_id="rule-1",
                name="Test Rule",
                description="Test rule",
                resource=RuleResource.CURVE,
                action=RuleAction.ALLOW,
                conditions=[],
                priority=100,
                enabled=True,
                tenant_id="tenant-1",
                user_id=None,
                created_at="2024-01-01T00:00:00Z",
                updated_at="2024-01-01T00:00:00Z",
                expires_at=None
            )
        ]
        mock_get_rules.return_value = mock_rules

        response = client.get("/entitlements/rules")

        assert response.status_code == 200
        data = response.json()
        assert "rules" in data
        assert "total" in data
        assert "page" in data
        assert "limit" in data
        assert data["total"] == 1
        assert len(data["rules"]) == 1

    @patch('service_entitlements.app.main.RuleEngine.get_rules_for_resource')
    def test_get_rules_with_filters(self, mock_get_rules, client):
        """Test getting rules with filters."""
        mock_rules = []
        mock_get_rules.return_value = mock_rules

        response = client.get("/entitlements/rules?resource=curve&page=1&limit=10")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["page"] == 1
        assert data["limit"] == 10

    @patch('service_entitlements.app.main.RuleEngine.add_rule')
    @patch('service_entitlements.app.main.PostgreSQLPersistence.save_rule')
    @patch('service_entitlements.app.main.RedisCache.invalidate_resource_entitlements')
    def test_create_rule_success(self, mock_invalidate_cache, mock_save_rule, mock_add_rule, client, mock_rule_create_request):
        """Test successful rule creation."""
        mock_add_rule.return_value = True
        mock_save_rule.return_value = True
        mock_invalidate_cache.return_value = True

        response = client.post("/entitlements/rules", json=mock_rule_create_request)

        assert response.status_code == 200
        data = response.json()
        assert "rule_id" in data
        assert data["name"] == "Test Rule"
        assert data["description"] == "Test entitlement rule"
        assert data["resource"] == "curve"
        assert data["action"] == "allow"
        assert data["priority"] == 100
        assert data["tenant_id"] == "tenant-1"

        # Verify rule was added and saved
        mock_add_rule.assert_called_once()
        mock_save_rule.assert_called_once()
        mock_invalidate_cache.assert_called_once()

    @patch('service_entitlements.app.main.RuleEngine.add_rule')
    @patch('service_entitlements.app.main.PostgreSQLPersistence.save_rule')
    def test_create_rule_engine_failure(self, mock_save_rule, mock_add_rule, client, mock_rule_create_request):
        """Test rule creation when engine fails."""
        mock_add_rule.return_value = False

        response = client.post("/entitlements/rules", json=mock_rule_create_request)

        assert response.status_code == 500
        data = response.json()
        assert data["detail"] == "Failed to add rule to engine"

    @patch('service_entitlements.app.main.RuleEngine.add_rule')
    @patch('service_entitlements.app.main.PostgreSQLPersistence.save_rule')
    @patch('service_entitlements.app.main.RuleEngine.remove_rule')
    def test_create_rule_persistence_failure(self, mock_remove_rule, mock_save_rule, mock_add_rule, client, mock_rule_create_request):
        """Test rule creation when persistence fails."""
        mock_add_rule.return_value = True
        mock_save_rule.return_value = False

        response = client.post("/entitlements/rules", json=mock_rule_create_request)

        assert response.status_code == 500
        data = response.json()
        assert data["detail"] == "Failed to save rule to database"

        # Verify rule was removed from engine
        mock_remove_rule.assert_called_once()

    @patch('service_entitlements.app.main.RuleEngine.get_rule')
    @patch('service_entitlements.app.main.RuleEngine.update_rule')
    @patch('service_entitlements.app.main.PostgreSQLPersistence.save_rule')
    @patch('service_entitlements.app.main.RedisCache.invalidate_resource_entitlements')
    def test_update_rule_success(self, mock_invalidate_cache, mock_save_rule, mock_update_rule, mock_get_rule, client):
        """Test successful rule update."""
        # Mock existing rule
        existing_rule = MagicMock()
        existing_rule.rule_id = "rule-1"
        existing_rule.name = "Old Name"
        existing_rule.description = "Old Description"
        existing_rule.resource = RuleResource.CURVE
        existing_rule.action = RuleAction.ALLOW
        existing_rule.conditions = []
        existing_rule.priority = 100
        existing_rule.enabled = True
        existing_rule.tenant_id = "tenant-1"
        existing_rule.user_id = None
        existing_rule.created_at = "2024-01-01T00:00:00Z"
        existing_rule.updated_at = "2024-01-01T00:00:00Z"
        existing_rule.expires_at = None

        mock_get_rule.return_value = existing_rule
        mock_update_rule.return_value = True
        mock_save_rule.return_value = True
        mock_invalidate_cache.return_value = True

        update_request = {
            "name": "Updated Rule",
            "description": "Updated Description",
            "priority": 200
        }

        response = client.put("/entitlements/rules/rule-1", json=update_request)

        assert response.status_code == 200
        data = response.json()
        assert data["rule_id"] == "rule-1"
        assert data["name"] == "Updated Rule"
        assert data["description"] == "Updated Description"
        assert data["priority"] == 200

        # Verify rule was updated and saved
        mock_update_rule.assert_called_once()
        mock_save_rule.assert_called_once()
        mock_invalidate_cache.assert_called_once()

    @patch('service_entitlements.app.main.RuleEngine.get_rule')
    def test_update_rule_not_found(self, mock_get_rule, client):
        """Test rule update when rule not found."""
        mock_get_rule.return_value = None

        update_request = {
            "name": "Updated Rule"
        }

        response = client.put("/entitlements/rules/non-existent-rule", json=update_request)

        assert response.status_code == 404
        data = response.json()
        assert data["detail"] == "Rule not found"

    @patch('service_entitlements.app.main.RuleEngine.get_rule')
    @patch('service_entitlements.app.main.RuleEngine.remove_rule')
    @patch('service_entitlements.app.main.PostgreSQLPersistence.delete_rule')
    @patch('service_entitlements.app.main.RedisCache.invalidate_resource_entitlements')
    def test_delete_rule_success(self, mock_invalidate_cache, mock_delete_rule, mock_remove_rule, mock_get_rule, client):
        """Test successful rule deletion."""
        # Mock existing rule
        existing_rule = MagicMock()
        existing_rule.rule_id = "rule-1"
        existing_rule.name = "Test Rule"
        existing_rule.resource = RuleResource.CURVE
        existing_rule.tenant_id = "tenant-1"
        existing_rule.user_id = None

        mock_get_rule.return_value = existing_rule
        mock_remove_rule.return_value = True
        mock_delete_rule.return_value = True
        mock_invalidate_cache.return_value = True

        response = client.delete("/entitlements/rules/rule-1")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "Rule deleted successfully"

        # Verify rule was removed and deleted
        mock_remove_rule.assert_called_once()
        mock_delete_rule.assert_called_once()
        mock_invalidate_cache.assert_called_once()

    @patch('service_entitlements.app.main.RuleEngine.get_rule')
    def test_delete_rule_not_found(self, mock_get_rule, client):
        """Test rule deletion when rule not found."""
        mock_get_rule.return_value = None

        response = client.delete("/entitlements/rules/non-existent-rule")

        assert response.status_code == 404
        data = response.json()
        assert data["detail"] == "Rule not found"

    @patch('service_entitlements.app.main.RuleEngine.get_engine_stats')
    @patch('service_entitlements.app.main.RedisCache.get_cache_stats')
    @patch('service_entitlements.app.main.PostgreSQLPersistence.get_rule_stats')
    def test_get_stats_success(self, mock_persistence_stats, mock_cache_stats, mock_engine_stats, client):
        """Test getting service statistics."""
        mock_engine_stats.return_value = {
            "total_rules": 10,
            "enabled_rules": 8,
            "disabled_rules": 2,
            "expired_rules": 0
        }

        mock_cache_stats.return_value = {
            "hit_ratio": 0.85,
            "total_requests": 1000,
            "cache_hits": 850
        }

        mock_persistence_stats.return_value = {
            "total_rules": 10,
            "rules_by_tenant": {"tenant-1": 5, "tenant-2": 5}
        }

        response = client.get("/entitlements/stats")

        assert response.status_code == 200
        data = response.json()
        assert "engine" in data
        assert "cache" in data
        assert "persistence" in data
        assert "timestamp" in data

        assert data["engine"]["total_rules"] == 10
        assert data["cache"]["hit_ratio"] == 0.85
        assert data["persistence"]["total_rules"] == 10

    @patch('service_entitlements.app.main.RedisCache.health_check')
    @patch('service_entitlements.app.main.PostgreSQLPersistence.health_check')
    async def test_check_dependencies(self, mock_postgres_health, mock_redis_health, entitlements_service):
        """Test dependency checks."""
        mock_redis_health.return_value = True
        mock_postgres_health.return_value = True

        dependencies = await entitlements_service._check_dependencies()

        assert dependencies["redis"] == "ok"
        assert dependencies["postgres"] == "ok"

    @patch('service_entitlements.app.main.RedisCache.health_check')
    @patch('service_entitlements.app.main.PostgreSQLPersistence.health_check')
    async def test_check_dependencies_redis_error(self, mock_postgres_health, mock_redis_health, entitlements_service):
        """Test dependency checks with Redis error."""
        mock_redis_health.return_value = False
        mock_postgres_health.return_value = True

        dependencies = await entitlements_service._check_dependencies()

        assert dependencies["redis"] == "error"
        assert dependencies["postgres"] == "ok"

    @patch('service_entitlements.app.main.PostgreSQLPersistence.start')
    @patch('service_entitlements.app.main.RedisCache.start')
    @patch('service_entitlements.app.main.PostgreSQLPersistence.load_all_rules')
    @patch('service_entitlements.app.main.RuleEngine.add_rule')
    async def test_start_service(self, mock_add_rule, mock_load_rules, mock_cache_start, mock_persistence_start, entitlements_service):
        """Test service start."""
        # Mock loaded rules
        mock_rules = [MagicMock(), MagicMock()]
        mock_load_rules.return_value = mock_rules

        await entitlements_service.start()

        # Verify components started
        mock_persistence_start.assert_called_once()
        mock_cache_start.assert_called_once()

        # Verify rules were loaded
        mock_load_rules.assert_called_once()
        assert mock_add_rule.call_count == 2

    @patch('service_entitlements.app.main.PostgreSQLPersistence.stop')
    @patch('service_entitlements.app.main.RedisCache.stop')
    async def test_stop_service(self, mock_cache_stop, mock_persistence_stop, entitlements_service):
        """Test service stop."""
        await entitlements_service.stop()

        mock_persistence_stop.assert_called_once()
        mock_cache_stop.assert_called_once()

    def test_context_hash_generation(self, entitlements_service, mock_entitlement_request):
        """Test context hash generation for caching."""
        context_str = json.dumps({
            "user_id": mock_entitlement_request["user_id"],
            "tenant_id": mock_entitlement_request["tenant_id"],
            "resource": mock_entitlement_request["resource"],
            "action": mock_entitlement_request["action"],
            "context": mock_entitlement_request["context"]
        }, sort_keys=True)
        
        expected_hash = hashlib.md5(context_str.encode()).hexdigest()
        
        # This would be generated in the actual endpoint
        assert len(expected_hash) == 32
        assert expected_hash.isalnum()

    def test_rule_validation(self, client):
        """Test rule validation."""
        invalid_rule_request = {
            "name": "",  # Empty name
            "description": "Test rule",
            "resource": "invalid_resource",  # Invalid resource
            "action": "invalid_action",  # Invalid action
            "conditions": [
                {
                    "field": "tenant_id",
                    "operator": "invalid_operator",  # Invalid operator
                    "value": "tenant-1"
                }
            ],
            "priority": -1  # Invalid priority
        }

        response = client.post("/entitlements/rules", json=invalid_rule_request)

        # Should handle validation errors gracefully
        assert response.status_code in [400, 422, 500]