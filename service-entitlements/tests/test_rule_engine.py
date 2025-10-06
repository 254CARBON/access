"""
Unit tests for RuleEngine.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timedelta

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from service_entitlements.app.rules.engine import RuleEngine
from service_entitlements.app.rules.models import (
    Rule, RuleCondition, RuleConditionOperator, RuleAction, RuleResource,
    EvaluationContext, EvaluationResult
)


class TestRuleEngine:
    """Test cases for RuleEngine."""
    
    @pytest.fixture
    def rule_engine(self):
        """Create RuleEngine instance."""
        return RuleEngine()
    
    @pytest.fixture
    def mock_rule(self):
        """Create mock rule."""
        return Rule(
            rule_id="rule1",
            name="Test Rule",
            description="Test rule for unit testing",
            resource=RuleResource.INSTRUMENT,
            action=RuleAction.ALLOW,
            conditions=[
                RuleCondition(
                    field="user_roles",
                    operator=RuleConditionOperator.CONTAINS,
                    value="admin",
                    description="User must have admin role"
                )
            ],
            priority=100,
            enabled=True,
            tenant_id="tenant-1",
            user_id=None,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            expires_at=None
        )
    
    @pytest.fixture
    def mock_evaluation_context(self):
        """Create mock evaluation context."""
        return EvaluationContext(
            user_id="user1",
            tenant_id="tenant-1",
            resource="instrument",
            action="read",
            context={
                "user_roles": ["admin", "user"],
                "resource_id": "INST001",
                "instrument_type": "commodity"
            },
            timestamp=datetime.now()
        )
    
    def test_add_rule_success(self, rule_engine, mock_rule):
        """Test successful rule addition."""
        # Test
        result = rule_engine.add_rule(mock_rule)
        
        # Assertions
        assert result is True
        assert mock_rule.rule_id in rule_engine.rules
        assert rule_engine.rules[mock_rule.rule_id] == mock_rule
    
    def test_add_rule_error(self, rule_engine, mock_rule):
        """Test rule addition with error."""
        # Mock rule to raise exception
        with patch.object(rule_engine, '_invalidate_cache', side_effect=Exception("Cache error")):
            # Test
            result = rule_engine.add_rule(mock_rule)
            
            # Assertions
            assert result is False
    
    def test_remove_rule_success(self, rule_engine, mock_rule):
        """Test successful rule removal."""
        # Add rule first
        rule_engine.add_rule(mock_rule)
        
        # Test
        result = rule_engine.remove_rule(mock_rule.rule_id)
        
        # Assertions
        assert result is True
        assert mock_rule.rule_id not in rule_engine.rules
    
    def test_remove_rule_not_found(self, rule_engine):
        """Test rule removal for non-existent rule."""
        # Test
        result = rule_engine.remove_rule("nonexistent-rule")
        
        # Assertions
        assert result is False
    
    def test_update_rule_success(self, rule_engine, mock_rule):
        """Test successful rule update."""
        # Add rule first
        rule_engine.add_rule(mock_rule)
        
        # Modify rule
        mock_rule.name = "Updated Test Rule"
        mock_rule.description = "Updated description"
        
        # Test
        result = rule_engine.update_rule(mock_rule)
        
        # Assertions
        assert result is True
        assert rule_engine.rules[mock_rule.rule_id].name == "Updated Test Rule"
    
    def test_update_rule_not_found(self, rule_engine, mock_rule):
        """Test rule update for non-existent rule."""
        # Test
        result = rule_engine.update_rule(mock_rule)
        
        # Assertions
        assert result is False
    
    def test_get_rule_success(self, rule_engine, mock_rule):
        """Test successful rule retrieval."""
        # Add rule first
        rule_engine.add_rule(mock_rule)
        
        # Test
        result = rule_engine.get_rule(mock_rule.rule_id)
        
        # Assertions
        assert result == mock_rule
    
    def test_get_rule_not_found(self, rule_engine):
        """Test rule retrieval for non-existent rule."""
        # Test
        result = rule_engine.get_rule("nonexistent-rule")
        
        # Assertions
        assert result is None
    
    def test_get_rules_for_resource(self, rule_engine, mock_rule):
        """Test rules retrieval for resource."""
        # Add rule
        rule_engine.add_rule(mock_rule)
        
        # Test
        rules = rule_engine.get_rules_for_resource("instrument")
        
        # Assertions
        assert len(rules) == 1
        assert rules[0] == mock_rule
    
    def test_get_rules_for_resource_cached(self, rule_engine, mock_rule):
        """Test rules retrieval for resource with caching."""
        # Add rule
        rule_engine.add_rule(mock_rule)
        
        # First call
        rules1 = rule_engine.get_rules_for_resource("instrument")
        
        # Second call (should use cache)
        rules2 = rule_engine.get_rules_for_resource("instrument")
        
        # Assertions
        assert rules1 == rules2
        assert "instrument" in rule_engine.rule_cache
    
    def test_evaluate_rule_success(self, rule_engine, mock_rule, mock_evaluation_context):
        """Test successful rule evaluation."""
        # Add rule
        rule_engine.add_rule(mock_rule)
        
        # Test
        result = rule_engine.evaluate(mock_evaluation_context)
        
        # Assertions
        assert result.allowed is True
        assert result.reason == "Rule 'Test Rule' matched"
        assert result.matched_rules == ["rule1"]
        assert result.evaluation_time_ms > 0
    
    def test_evaluate_rule_no_rules(self, rule_engine, mock_evaluation_context):
        """Test rule evaluation with no rules."""
        # Test
        result = rule_engine.evaluate(mock_evaluation_context)
        
        # Assertions
        assert result.allowed is False
        assert result.reason == "No rules found for resource"
        assert result.matched_rules == []
    
    def test_evaluate_rule_no_match(self, rule_engine, mock_rule, mock_evaluation_context):
        """Test rule evaluation with no matching rules."""
        # Modify rule to not match
        mock_rule.conditions[0].value = "superuser"  # Change from "admin" to "superuser"
        rule_engine.add_rule(mock_rule)
        
        # Test
        result = rule_engine.evaluate(mock_evaluation_context)
        
        # Assertions
        assert result.allowed is False
        assert result.reason == "No applicable rules matched"
        assert result.matched_rules == []
    
    def test_evaluate_rule_deny_action(self, rule_engine, mock_rule, mock_evaluation_context):
        """Test rule evaluation with deny action."""
        # Modify rule to deny
        mock_rule.action = RuleAction.DENY
        rule_engine.add_rule(mock_rule)
        
        # Test
        result = rule_engine.evaluate(mock_evaluation_context)
        
        # Assertions
        assert result.allowed is False
        assert result.reason == "Rule 'Test Rule' matched"
        assert result.matched_rules == ["rule1"]
    
    def test_evaluate_rule_expired(self, rule_engine, mock_rule, mock_evaluation_context):
        """Test rule evaluation with expired rule."""
        # Modify rule to be expired
        mock_rule.expires_at = datetime.now() - timedelta(hours=1)
        rule_engine.add_rule(mock_rule)
        
        # Test
        result = rule_engine.evaluate(mock_evaluation_context)
        
        # Assertions
        assert result.allowed is False
        assert result.reason == "No applicable rules matched"
    
    def test_evaluate_rule_wrong_tenant(self, rule_engine, mock_rule, mock_evaluation_context):
        """Test rule evaluation with wrong tenant."""
        # Modify rule for different tenant
        mock_rule.tenant_id = "tenant-2"
        rule_engine.add_rule(mock_rule)
        
        # Test
        result = rule_engine.evaluate(mock_evaluation_context)
        
        # Assertions
        assert result.allowed is False
        assert result.reason == "No applicable rules matched"
    
    def test_evaluate_rule_wrong_user(self, rule_engine, mock_rule, mock_evaluation_context):
        """Test rule evaluation with wrong user."""
        # Modify rule for specific user
        mock_rule.user_id = "user2"
        rule_engine.add_rule(mock_rule)
        
        # Test
        result = rule_engine.evaluate(mock_evaluation_context)
        
        # Assertions
        assert result.allowed is False
        assert result.reason == "No applicable rules matched"
    
    def test_evaluate_rule_disabled(self, rule_engine, mock_rule, mock_evaluation_context):
        """Test rule evaluation with disabled rule."""
        # Disable rule
        mock_rule.enabled = False
        rule_engine.add_rule(mock_rule)
        
        # Test
        result = rule_engine.evaluate(mock_evaluation_context)
        
        # Assertions
        assert result.allowed is False
        assert result.reason == "No rules found for resource"
    
    def test_evaluate_rule_priority_order(self, rule_engine, mock_evaluation_context):
        """Test rule evaluation with priority ordering."""
        # Create two rules with different priorities
        rule1 = Rule(
            rule_id="rule1",
            name="Low Priority Rule",
            description="Low priority rule",
            resource=RuleResource.INSTRUMENT,
            action=RuleAction.DENY,
            conditions=[],
            priority=10,
            enabled=True,
            tenant_id="tenant-1"
        )
        
        rule2 = Rule(
            rule_id="rule2",
            name="High Priority Rule",
            description="High priority rule",
            resource=RuleResource.INSTRUMENT,
            action=RuleAction.ALLOW,
            conditions=[],
            priority=100,
            enabled=True,
            tenant_id="tenant-1"
        )
        
        # Add rules
        rule_engine.add_rule(rule1)
        rule_engine.add_rule(rule2)
        
        # Test
        result = rule_engine.evaluate(mock_evaluation_context)
        
        # Assertions
        assert result.allowed is True  # High priority rule should win
        assert result.matched_rules == ["rule2"]
    
    def test_evaluate_condition_equals(self, rule_engine, mock_evaluation_context):
        """Test condition evaluation with EQUALS operator."""
        # Create rule with equals condition
        rule = Rule(
            rule_id="rule1",
            name="Equals Rule",
            description="Rule with equals condition",
            resource=RuleResource.INSTRUMENT,
            action=RuleAction.ALLOW,
            conditions=[
                RuleCondition(
                    field="user_roles",
                    operator=RuleConditionOperator.EQUALS,
                    value=["admin", "user"]
                )
            ],
            priority=100,
            enabled=True,
            tenant_id="tenant-1"
        )
        
        rule_engine.add_rule(rule)
        
        # Test
        result = rule_engine.evaluate(mock_evaluation_context)
        
        # Assertions
        assert result.allowed is False  # ["admin", "user"] != ["admin", "user"] (reference equality)
    
    def test_evaluate_condition_not_equals(self, rule_engine, mock_evaluation_context):
        """Test condition evaluation with NOT_EQUALS operator."""
        # Create rule with not equals condition
        rule = Rule(
            rule_id="rule1",
            name="Not Equals Rule",
            description="Rule with not equals condition",
            resource=RuleResource.INSTRUMENT,
            action=RuleAction.ALLOW,
            conditions=[
                RuleCondition(
                    field="user_roles",
                    operator=RuleConditionOperator.NOT_EQUALS,
                    value=["superuser"]
                )
            ],
            priority=100,
            enabled=True,
            tenant_id="tenant-1"
        )
        
        rule_engine.add_rule(rule)
        
        # Test
        result = rule_engine.evaluate(mock_evaluation_context)
        
        # Assertions
        assert result.allowed is True
    
    def test_evaluate_condition_in(self, rule_engine, mock_evaluation_context):
        """Test condition evaluation with IN operator."""
        # Create rule with in condition
        rule = Rule(
            rule_id="rule1",
            name="In Rule",
            description="Rule with in condition",
            resource=RuleResource.INSTRUMENT,
            action=RuleAction.ALLOW,
            conditions=[
                RuleCondition(
                    field="user_roles",
                    operator=RuleConditionOperator.IN,
                    value=["admin", "user", "analyst"]
                )
            ],
            priority=100,
            enabled=True,
            tenant_id="tenant-1"
        )
        
        rule_engine.add_rule(rule)
        
        # Test
        result = rule_engine.evaluate(mock_evaluation_context)
        
        # Assertions
        assert result.allowed is True
    
    def test_evaluate_condition_not_in(self, rule_engine, mock_evaluation_context):
        """Test condition evaluation with NOT_IN operator."""
        # Create rule with not in condition
        rule = Rule(
            rule_id="rule1",
            name="Not In Rule",
            description="Rule with not in condition",
            resource=RuleResource.INSTRUMENT,
            action=RuleAction.ALLOW,
            conditions=[
                RuleCondition(
                    field="user_roles",
                    operator=RuleConditionOperator.NOT_IN,
                    value=["superuser", "guest"]
                )
            ],
            priority=100,
            enabled=True,
            tenant_id="tenant-1"
        )
        
        rule_engine.add_rule(rule)
        
        # Test
        result = rule_engine.evaluate(mock_evaluation_context)
        
        # Assertions
        assert result.allowed is True
    
    def test_evaluate_condition_greater_than(self, rule_engine, mock_evaluation_context):
        """Test condition evaluation with GREATER_THAN operator."""
        # Add numeric field to context
        mock_evaluation_context.context["price"] = 100
        
        # Create rule with greater than condition
        rule = Rule(
            rule_id="rule1",
            name="Greater Than Rule",
            description="Rule with greater than condition",
            resource=RuleResource.INSTRUMENT,
            action=RuleAction.ALLOW,
            conditions=[
                RuleCondition(
                    field="price",
                    operator=RuleConditionOperator.GREATER_THAN,
                    value=50
                )
            ],
            priority=100,
            enabled=True,
            tenant_id="tenant-1"
        )
        
        rule_engine.add_rule(rule)
        
        # Test
        result = rule_engine.evaluate(mock_evaluation_context)
        
        # Assertions
        assert result.allowed is True
    
    def test_evaluate_condition_less_than(self, rule_engine, mock_evaluation_context):
        """Test condition evaluation with LESS_THAN operator."""
        # Add numeric field to context
        mock_evaluation_context.context["price"] = 25
        
        # Create rule with less than condition
        rule = Rule(
            rule_id="rule1",
            name="Less Than Rule",
            description="Rule with less than condition",
            resource=RuleResource.INSTRUMENT,
            action=RuleAction.ALLOW,
            conditions=[
                RuleCondition(
                    field="price",
                    operator=RuleConditionOperator.LESS_THAN,
                    value=50
                )
            ],
            priority=100,
            enabled=True,
            tenant_id="tenant-1"
        )
        
        rule_engine.add_rule(rule)
        
        # Test
        result = rule_engine.evaluate(mock_evaluation_context)
        
        # Assertions
        assert result.allowed is True
    
    def test_evaluate_condition_contains(self, rule_engine, mock_evaluation_context):
        """Test condition evaluation with CONTAINS operator."""
        # Create rule with contains condition
        rule = Rule(
            rule_id="rule1",
            name="Contains Rule",
            description="Rule with contains condition",
            resource=RuleResource.INSTRUMENT,
            action=RuleAction.ALLOW,
            conditions=[
                RuleCondition(
                    field="user_roles",
                    operator=RuleConditionOperator.CONTAINS,
                    value="admin"
                )
            ],
            priority=100,
            enabled=True,
            tenant_id="tenant-1"
        )
        
        rule_engine.add_rule(rule)
        
        # Test
        result = rule_engine.evaluate(mock_evaluation_context)
        
        # Assertions
        assert result.allowed is True
    
    def test_evaluate_condition_starts_with(self, rule_engine, mock_evaluation_context):
        """Test condition evaluation with STARTS_WITH operator."""
        # Add string field to context
        mock_evaluation_context.context["username"] = "admin_user"
        
        # Create rule with starts with condition
        rule = Rule(
            rule_id="rule1",
            name="Starts With Rule",
            description="Rule with starts with condition",
            resource=RuleResource.INSTRUMENT,
            action=RuleAction.ALLOW,
            conditions=[
                RuleCondition(
                    field="username",
                    operator=RuleConditionOperator.STARTS_WITH,
                    value="admin"
                )
            ],
            priority=100,
            enabled=True,
            tenant_id="tenant-1"
        )
        
        rule_engine.add_rule(rule)
        
        # Test
        result = rule_engine.evaluate(mock_evaluation_context)
        
        # Assertions
        assert result.allowed is True
    
    def test_evaluate_condition_ends_with(self, rule_engine, mock_evaluation_context):
        """Test condition evaluation with ENDS_WITH operator."""
        # Add string field to context
        mock_evaluation_context.context["username"] = "user_admin"
        
        # Create rule with ends with condition
        rule = Rule(
            rule_id="rule1",
            name="Ends With Rule",
            description="Rule with ends with condition",
            resource=RuleResource.INSTRUMENT,
            action=RuleAction.ALLOW,
            conditions=[
                RuleCondition(
                    field="username",
                    operator=RuleConditionOperator.ENDS_WITH,
                    value="admin"
                )
            ],
            priority=100,
            enabled=True,
            tenant_id="tenant-1"
        )
        
        rule_engine.add_rule(rule)
        
        # Test
        result = rule_engine.evaluate(mock_evaluation_context)
        
        # Assertions
        assert result.allowed is True
    
    def test_evaluate_condition_nested_field(self, rule_engine, mock_evaluation_context):
        """Test condition evaluation with nested field."""
        # Add nested field to context
        mock_evaluation_context.context["resource"] = {
            "instrument": {
                "type": "commodity"
            }
        }
        
        # Create rule with nested field condition
        rule = Rule(
            rule_id="rule1",
            name="Nested Field Rule",
            description="Rule with nested field condition",
            resource=RuleResource.INSTRUMENT,
            action=RuleAction.ALLOW,
            conditions=[
                RuleCondition(
                    field="resource.instrument.type",
                    operator=RuleConditionOperator.EQUALS,
                    value="commodity"
                )
            ],
            priority=100,
            enabled=True,
            tenant_id="tenant-1"
        )
        
        rule_engine.add_rule(rule)
        
        # Test
        result = rule_engine.evaluate(mock_evaluation_context)
        
        # Assertions
        assert result.allowed is True
    
    def test_evaluate_condition_missing_field(self, rule_engine, mock_evaluation_context):
        """Test condition evaluation with missing field."""
        # Create rule with missing field condition
        rule = Rule(
            rule_id="rule1",
            name="Missing Field Rule",
            description="Rule with missing field condition",
            resource=RuleResource.INSTRUMENT,
            action=RuleAction.ALLOW,
            conditions=[
                RuleCondition(
                    field="nonexistent_field",
                    operator=RuleConditionOperator.EQUALS,
                    value="value"
                )
            ],
            priority=100,
            enabled=True,
            tenant_id="tenant-1"
        )
        
        rule_engine.add_rule(rule)
        
        # Test
        result = rule_engine.evaluate(mock_evaluation_context)
        
        # Assertions
        assert result.allowed is False
        assert result.reason == "No applicable rules matched"
    
    def test_evaluate_condition_error(self, rule_engine, mock_evaluation_context):
        """Test condition evaluation with error."""
        # Create rule with error-prone condition
        rule = Rule(
            rule_id="rule1",
            name="Error Rule",
            description="Rule with error condition",
            resource=RuleResource.INSTRUMENT,
            action=RuleAction.ALLOW,
            conditions=[
                RuleCondition(
                    field="user_roles",
                    operator=RuleConditionOperator.GREATER_THAN,  # Invalid operator for list
                    value=50
                )
            ],
            priority=100,
            enabled=True,
            tenant_id="tenant-1"
        )
        
        rule_engine.add_rule(rule)
        
        # Test
        result = rule_engine.evaluate(mock_evaluation_context)
        
        # Assertions
        assert result.allowed is False
        assert result.reason == "No applicable rules matched"
    
    def test_get_engine_stats(self, rule_engine, mock_rule):
        """Test engine statistics retrieval."""
        # Add rule
        rule_engine.add_rule(mock_rule)
        
        # Test
        stats = rule_engine.get_engine_stats()
        
        # Assertions
        assert stats["total_rules"] == 1
        assert stats["enabled_rules"] == 1
        assert stats["cached_resources"] == 0
        assert "instrument" in stats["resources"]
    
    def test_clear_all_rules(self, rule_engine, mock_rule):
        """Test clearing all rules."""
        # Add rule
        rule_engine.add_rule(mock_rule)
        
        # Test
        rule_engine.clear_all_rules()
        
        # Assertions
        assert len(rule_engine.rules) == 0
        assert len(rule_engine.rule_cache) == 0
    
    def test_get_rules_by_tenant(self, rule_engine, mock_rule):
        """Test rules retrieval by tenant."""
        # Add rule
        rule_engine.add_rule(mock_rule)
        
        # Test
        rules = rule_engine.get_rules_by_tenant("tenant-1")
        
        # Assertions
        assert len(rules) == 1
        assert rules[0] == mock_rule
    
    def test_get_rules_by_user(self, rule_engine, mock_rule):
        """Test rules retrieval by user."""
        # Modify rule for specific user
        mock_rule.user_id = "user1"
        rule_engine.add_rule(mock_rule)
        
        # Test
        rules = rule_engine.get_rules_by_user("user1")
        
        # Assertions
        assert len(rules) == 1
        assert rules[0] == mock_rule
