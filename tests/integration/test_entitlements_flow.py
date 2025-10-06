"""
Integration tests for Entitlements service flow.
"""

import pytest
import httpx
import json
from unittest.mock import patch, AsyncMock

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from shared.test_helpers import create_mock_jwt_token, create_mock_user


class TestEntitlementsFlow:
    """Integration tests for Entitlements service flow."""
    
    @pytest.fixture
    def entitlements_url(self):
        """Entitlements service URL."""
        return "http://localhost:8002"
    
    @pytest.fixture
    def mock_user(self):
        """Create mock user."""
        return create_mock_user(
            user_id="test-user-1",
            tenant_id="tenant-1",
            roles=["user", "analyst"]
        )
    
    @pytest.fixture
    def mock_jwt_token(self, mock_user):
        """Create mock JWT token."""
        return create_mock_jwt_token(
            user_id=mock_user["user_id"],
            tenant_id=mock_user["tenant_id"],
            roles=mock_user["roles"],
            expires_in=3600
        )
    
    @pytest.fixture
    def mock_rule(self):
        """Create mock entitlement rule."""
        return {
            "rule_id": "rule-1",
            "name": "Test Rule",
            "description": "Test entitlement rule",
            "resource": "instrument",
            "action": "allow",
            "conditions": [
                {
                    "field": "user_roles",
                    "operator": "contains",
                    "value": "user"
                }
            ],
            "priority": 100,
            "enabled": True,
            "tenant_id": "tenant-1"
        }
    
    @pytest.mark.asyncio
    async def test_entitlements_check_flow(self, entitlements_url, mock_jwt_token, mock_rule):
        """Test entitlements check flow."""
        async with httpx.AsyncClient() as client:
            headers = {"Authorization": f"Bearer {mock_jwt_token}"}
            
            # First, create a rule
            create_response = await client.post(
                f"{entitlements_url}/entitlements/rules",
                headers=headers,
                json=mock_rule
            )
            assert create_response.status_code == 201
            rule_data = create_response.json()
            assert rule_data["rule_id"] == mock_rule["rule_id"]
            
            # Check entitlements
            check_data = {
                "user_id": "test-user-1",
                "tenant_id": "tenant-1",
                "resource": "instrument",
                "action": "read",
                "context": {
                    "user_roles": ["user", "analyst"],
                    "resource_id": "INST001"
                }
            }
            
            check_response = await client.post(
                f"{entitlements_url}/entitlements/check",
                headers=headers,
                json=check_data
            )
            assert check_response.status_code == 200
            result = check_response.json()
            assert "allowed" in result
            assert "reason" in result
            assert "matched_rules" in result
    
    @pytest.mark.asyncio
    async def test_entitlements_rule_crud_flow(self, entitlements_url, mock_jwt_token, mock_rule):
        """Test entitlements rule CRUD flow."""
        async with httpx.AsyncClient() as client:
            headers = {"Authorization": f"Bearer {mock_jwt_token}"}
            
            # Create rule
            create_response = await client.post(
                f"{entitlements_url}/entitlements/rules",
                headers=headers,
                json=mock_rule
            )
            assert create_response.status_code == 201
            rule_data = create_response.json()
            rule_id = rule_data["rule_id"]
            
            # Get rule
            get_response = await client.get(
                f"{entitlements_url}/entitlements/rules/{rule_id}",
                headers=headers
            )
            assert get_response.status_code == 200
            retrieved_rule = get_response.json()
            assert retrieved_rule["rule_id"] == rule_id
            assert retrieved_rule["name"] == mock_rule["name"]
            
            # Update rule
            updated_rule = mock_rule.copy()
            updated_rule["name"] = "Updated Test Rule"
            updated_rule["description"] = "Updated description"
            
            update_response = await client.put(
                f"{entitlements_url}/entitlements/rules/{rule_id}",
                headers=headers,
                json=updated_rule
            )
            assert update_response.status_code == 200
            updated_data = update_response.json()
            assert updated_data["name"] == "Updated Test Rule"
            
            # List rules
            list_response = await client.get(
                f"{entitlements_url}/entitlements/rules",
                headers=headers
            )
            assert list_response.status_code == 200
            rules_list = list_response.json()
            assert "rules" in rules_list
            assert len(rules_list["rules"]) > 0
            
            # Delete rule
            delete_response = await client.delete(
                f"{entitlements_url}/entitlements/rules/{rule_id}",
                headers=headers
            )
            assert delete_response.status_code == 200
            delete_data = delete_response.json()
            assert delete_data["deleted"] is True
    
    @pytest.mark.asyncio
    async def test_entitlements_rule_evaluation(self, entitlements_url, mock_jwt_token):
        """Test entitlements rule evaluation."""
        async with httpx.AsyncClient() as client:
            headers = {"Authorization": f"Bearer {mock_jwt_token}"}
            
            # Create multiple rules with different priorities
            rules = [
                {
                    "rule_id": "rule-1",
                    "name": "Allow Users",
                    "resource": "instrument",
                    "action": "allow",
                    "conditions": [{"field": "user_roles", "operator": "contains", "value": "user"}],
                    "priority": 100,
                    "enabled": True,
                    "tenant_id": "tenant-1"
                },
                {
                    "rule_id": "rule-2",
                    "name": "Deny Specific Instrument",
                    "resource": "instrument",
                    "action": "deny",
                    "conditions": [{"field": "resource_id", "operator": "equals", "value": "RESTRICTED"}],
                    "priority": 200,
                    "enabled": True,
                    "tenant_id": "tenant-1"
                }
            ]
            
            # Create rules
            for rule in rules:
                create_response = await client.post(
                    f"{entitlements_url}/entitlements/rules",
                    headers=headers,
                    json=rule
                )
                assert create_response.status_code == 201
            
            # Test evaluation with allowed access
            check_data = {
                "user_id": "test-user-1",
                "tenant_id": "tenant-1",
                "resource": "instrument",
                "action": "read",
                "context": {
                    "user_roles": ["user"],
                    "resource_id": "INST001"
                }
            }
            
            check_response = await client.post(
                f"{entitlements_url}/entitlements/check",
                headers=headers,
                json=check_data
            )
            assert check_response.status_code == 200
            result = check_response.json()
            assert result["allowed"] is True
            assert "rule-1" in result["matched_rules"]
            
            # Test evaluation with denied access
            check_data["context"]["resource_id"] = "RESTRICTED"
            check_response = await client.post(
                f"{entitlements_url}/entitlements/check",
                headers=headers,
                json=check_data
            )
            assert check_response.status_code == 200
            result = check_response.json()
            assert result["allowed"] is False
            assert "rule-2" in result["matched_rules"]
    
    @pytest.mark.asyncio
    async def test_entitlements_tenant_isolation(self, entitlements_url, mock_jwt_token):
        """Test entitlements tenant isolation."""
        async with httpx.AsyncClient() as client:
            headers = {"Authorization": f"Bearer {mock_jwt_token}"}
            
            # Create rule for tenant-1
            rule_tenant1 = {
                "rule_id": "rule-tenant1",
                "name": "Tenant 1 Rule",
                "resource": "instrument",
                "action": "allow",
                "conditions": [{"field": "user_roles", "operator": "contains", "value": "user"}],
                "priority": 100,
                "enabled": True,
                "tenant_id": "tenant-1"
            }
            
            create_response = await client.post(
                f"{entitlements_url}/entitlements/rules",
                headers=headers,
                json=rule_tenant1
            )
            assert create_response.status_code == 201
            
            # Check entitlements for tenant-1 (should be allowed)
            check_data = {
                "user_id": "test-user-1",
                "tenant_id": "tenant-1",
                "resource": "instrument",
                "action": "read",
                "context": {"user_roles": ["user"]}
            }
            
            check_response = await client.post(
                f"{entitlements_url}/entitlements/check",
                headers=headers,
                json=check_data
            )
            assert check_response.status_code == 200
            result = check_response.json()
            assert result["allowed"] is True
            
            # Check entitlements for tenant-2 (should be denied - no rules)
            check_data["tenant_id"] = "tenant-2"
            check_response = await client.post(
                f"{entitlements_url}/entitlements/check",
                headers=headers,
                json=check_data
            )
            assert check_response.status_code == 200
            result = check_response.json()
            assert result["allowed"] is False
    
    @pytest.mark.asyncio
    async def test_entitlements_caching(self, entitlements_url, mock_jwt_token, mock_rule):
        """Test entitlements caching."""
        async with httpx.AsyncClient() as client:
            headers = {"Authorization": f"Bearer {mock_jwt_token}"}
            
            # Create rule
            create_response = await client.post(
                f"{entitlements_url}/entitlements/rules",
                headers=headers,
                json=mock_rule
            )
            assert create_response.status_code == 201
            
            # First check - should evaluate rules
            check_data = {
                "user_id": "test-user-1",
                "tenant_id": "tenant-1",
                "resource": "instrument",
                "action": "read",
                "context": {"user_roles": ["user"]}
            }
            
            check_response1 = await client.post(
                f"{entitlements_url}/entitlements/check",
                headers=headers,
                json=check_data
            )
            assert check_response1.status_code == 200
            result1 = check_response1.json()
            
            # Second check - should use cache
            check_response2 = await client.post(
                f"{entitlements_url}/entitlements/check",
                headers=headers,
                json=check_data
            )
            assert check_response2.status_code == 200
            result2 = check_response2.json()
            
            # Results should be the same
            assert result1["allowed"] == result2["allowed"]
            assert result1["matched_rules"] == result2["matched_rules"]
    
    @pytest.mark.asyncio
    async def test_entitlements_error_handling(self, entitlements_url, mock_jwt_token):
        """Test entitlements error handling."""
        async with httpx.AsyncClient() as client:
            headers = {"Authorization": f"Bearer {mock_jwt_token}"}
            
            # Test invalid rule creation
            invalid_rule = {
                "rule_id": "invalid-rule",
                "name": "Invalid Rule",
                "resource": "invalid_resource",
                "action": "invalid_action",
                "conditions": []
            }
            
            create_response = await client.post(
                f"{entitlements_url}/entitlements/rules",
                headers=headers,
                json=invalid_rule
            )
            assert create_response.status_code == 400
            
            # Test invalid entitlement check
            invalid_check = {
                "user_id": "test-user-1",
                "tenant_id": "tenant-1",
                "resource": "instrument",
                "action": "read"
                # Missing context
            }
            
            check_response = await client.post(
                f"{entitlements_url}/entitlements/check",
                headers=headers,
                json=invalid_check
            )
            assert check_response.status_code == 400
            
            # Test non-existent rule
            get_response = await client.get(
                f"{entitlements_url}/entitlements/rules/non-existent",
                headers=headers
            )
            assert get_response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_entitlements_statistics(self, entitlements_url, mock_jwt_token, mock_rule):
        """Test entitlements statistics."""
        async with httpx.AsyncClient() as client:
            headers = {"Authorization": f"Bearer {mock_jwt_token}"}
            
            # Create rule
            create_response = await client.post(
                f"{entitlements_url}/entitlements/rules",
                headers=headers,
                json=mock_rule
            )
            assert create_response.status_code == 201
            
            # Get statistics
            stats_response = await client.get(
                f"{entitlements_url}/entitlements/stats",
                headers=headers
            )
            assert stats_response.status_code == 200
            stats = stats_response.json()
            assert "total_rules" in stats
            assert "enabled_rules" in stats
            assert "cached_results" in stats
            assert stats["total_rules"] > 0
    
    @pytest.mark.asyncio
    async def test_entitlements_rule_priority(self, entitlements_url, mock_jwt_token):
        """Test entitlements rule priority handling."""
        async with httpx.AsyncClient() as client:
            headers = {"Authorization": f"Bearer {mock_jwt_token}"}
            
            # Create rules with different priorities
            rules = [
                {
                    "rule_id": "rule-low-priority",
                    "name": "Low Priority Rule",
                    "resource": "instrument",
                    "action": "allow",
                    "conditions": [{"field": "user_roles", "operator": "contains", "value": "user"}],
                    "priority": 10,
                    "enabled": True,
                    "tenant_id": "tenant-1"
                },
                {
                    "rule_id": "rule-high-priority",
                    "name": "High Priority Rule",
                    "resource": "instrument",
                    "action": "deny",
                    "conditions": [{"field": "user_roles", "operator": "contains", "value": "user"}],
                    "priority": 100,
                    "enabled": True,
                    "tenant_id": "tenant-1"
                }
            ]
            
            # Create rules
            for rule in rules:
                create_response = await client.post(
                    f"{entitlements_url}/entitlements/rules",
                    headers=headers,
                    json=rule
                )
                assert create_response.status_code == 201
            
            # Test evaluation - high priority rule should win
            check_data = {
                "user_id": "test-user-1",
                "tenant_id": "tenant-1",
                "resource": "instrument",
                "action": "read",
                "context": {"user_roles": ["user"]}
            }
            
            check_response = await client.post(
                f"{entitlements_url}/entitlements/check",
                headers=headers,
                json=check_data
            )
            assert check_response.status_code == 200
            result = check_response.json()
            assert result["allowed"] is False  # High priority deny rule should win
            assert "rule-high-priority" in result["matched_rules"]
    
    @pytest.mark.asyncio
    async def test_entitlements_rule_expiration(self, entitlements_url, mock_jwt_token):
        """Test entitlements rule expiration."""
        async with httpx.AsyncClient() as client:
            headers = {"Authorization": f"Bearer {mock_jwt_token}"}
            
            # Create rule with expiration
            expired_rule = {
                "rule_id": "expired-rule",
                "name": "Expired Rule",
                "resource": "instrument",
                "action": "allow",
                "conditions": [{"field": "user_roles", "operator": "contains", "value": "user"}],
                "priority": 100,
                "enabled": True,
                "tenant_id": "tenant-1",
                "expires_at": "2020-01-01T00:00:00Z"  # Expired
            }
            
            create_response = await client.post(
                f"{entitlements_url}/entitlements/rules",
                headers=headers,
                json=expired_rule
            )
            assert create_response.status_code == 201
            
            # Test evaluation - expired rule should not apply
            check_data = {
                "user_id": "test-user-1",
                "tenant_id": "tenant-1",
                "resource": "instrument",
                "action": "read",
                "context": {"user_roles": ["user"]}
            }
            
            check_response = await client.post(
                f"{entitlements_url}/entitlements/check",
                headers=headers,
                json=check_data
            )
            assert check_response.status_code == 200
            result = check_response.json()
            assert result["allowed"] is False  # No applicable rules
    
    @pytest.mark.asyncio
    async def test_entitlements_concurrent_requests(self, entitlements_url, mock_jwt_token, mock_rule):
        """Test entitlements with concurrent requests."""
        async with httpx.AsyncClient() as client:
            headers = {"Authorization": f"Bearer {mock_jwt_token}"}
            
            # Create rule
            create_response = await client.post(
                f"{entitlements_url}/entitlements/rules",
                headers=headers,
                json=mock_rule
            )
            assert create_response.status_code == 201
            
            # Make concurrent entitlement checks
            async def check_entitlements():
                check_data = {
                    "user_id": "test-user-1",
                    "tenant_id": "tenant-1",
                    "resource": "instrument",
                    "action": "read",
                    "context": {"user_roles": ["user"]}
                }
                response = await client.post(
                    f"{entitlements_url}/entitlements/check",
                    headers=headers,
                    json=check_data
                )
                return response.status_code == 200
            
            # Make 20 concurrent requests
            tasks = [check_entitlements() for _ in range(20)]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # All should succeed
            success_count = sum(1 for r in results if r is True)
            assert success_count > 0