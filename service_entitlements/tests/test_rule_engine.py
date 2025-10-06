"""
Unit tests for Entitlements Rule Engine.
"""

import pytest
import time
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
from typing import Dict, Any, List

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

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
    def sample_rule(self):
        """Create sample rule."""
        conditions = [
            RuleCondition(
                field="tenant_id",
                operator=RuleConditionOperator.EQUALS,
                value="tenant-1",
                description="Tenant must be tenant-1"
            ),
            RuleCondition(
                field="user_roles",
                operator=RuleConditionOperator.CONTAINS,
                value="analyst",
                description="User must have analyst role"
            )
        ]

        return Rule(
            rule_id="rule-1",
            name="Test Rule",
            description="Test entitlement rule",
            resource=RuleResource.CURVE,
            action=RuleAction.ALLOW,
            conditions=conditions,
            priority=100,
            tenant_id="tenant-1",
            user_id=None
        )

    @pytest.fixture
    def evaluation_context(self):
        """Create evaluation context."""
        return EvaluationContext(
            user_id="user-123",
            tenant_id="tenant-1",
            resource="curve",
            action="read",
            context={
                "user_roles": ["user", "analyst"],
                "resource_id": "curve-1",
                "commodity": "oil"
            }
        )

    def test_add_rule_success(self, rule_engine, sample_rule):
        """Test successful rule addition."""
        success = rule_engine.add_rule(sample_rule)

        assert success is True
        assert sample_rule.rule_id in rule_engine.rules
        assert rule_engine.rules[sample_rule.rule_id] == sample_rule

    def test_add_rule_duplicate(self, rule_engine, sample_rule):
        """Test adding duplicate rule."""
        rule_engine.add_rule(sample_rule)
        
        # Adding same rule again should update it
        success = rule_engine.add_rule(sample_rule)
        assert success is True
        assert len(rule_engine.rules) == 1

    def test_remove_rule_success(self, rule_engine, sample_rule):
        """Test successful rule removal."""
        rule_engine.add_rule(sample_rule)
        
        success = rule_engine.remove_rule(sample_rule.rule_id)
        
        assert success is True
        assert sample_rule.rule_id not in rule_engine.rules

    def test_remove_rule_not_found(self, rule_engine):
        """Test removing non-existent rule."""
        success = rule_engine.remove_rule("non-existent-rule")
        
        assert success is False

    def test_update_rule_success(self, rule_engine, sample_rule):
        """Test successful rule update."""
        rule_engine.add_rule(sample_rule)
        
        # Update rule
        sample_rule.name = "Updated Rule"
        sample_rule.description = "Updated description"
        
        success = rule_engine.update_rule(sample_rule)
        
        assert success is True
        assert rule_engine.rules[sample_rule.rule_id].name == "Updated Rule"
        assert rule_engine.rules[sample_rule.rule_id].description == "Updated description"

    def test_update_rule_not_found(self, rule_engine, sample_rule):
        """Test updating non-existent rule."""
        success = rule_engine.update_rule(sample_rule)
        
        assert success is False

    def test_get_rule_success(self, rule_engine, sample_rule):
        """Test successful rule retrieval."""
        rule_engine.add_rule(sample_rule)
        
        retrieved_rule = rule_engine.get_rule(sample_rule.rule_id)
        
        assert retrieved_rule is not None
        assert retrieved_rule.rule_id == sample_rule.rule_id
        assert retrieved_rule.name == sample_rule.name

    def test_get_rule_not_found(self, rule_engine):
        """Test retrieving non-existent rule."""
        retrieved_rule = rule_engine.get_rule("non-existent-rule")
        
        assert retrieved_rule is None

    def test_get_rules_for_resource(self, rule_engine, sample_rule):
        """Test getting rules for specific resource."""
        rule_engine.add_rule(sample_rule)
        
        rules = rule_engine.get_rules_for_resource("curve")
        
        assert len(rules) == 1
        assert rules[0].rule_id == sample_rule.rule_id

    def test_get_rules_for_resource_not_found(self, rule_engine):
        """Test getting rules for non-existent resource."""
        rules = rule_engine.get_rules_for_resource("non-existent-resource")
        
        assert len(rules) == 0

    def test_get_rules_by_tenant(self, rule_engine, sample_rule):
        """Test getting rules by tenant."""
        rule_engine.add_rule(sample_rule)
        
        rules = rule_engine.get_rules_by_tenant("tenant-1")
        
        assert len(rules) == 1
        assert rules[0].rule_id == sample_rule.rule_id

    def test_get_rules_by_tenant_not_found(self, rule_engine):
        """Test getting rules for non-existent tenant."""
        rules = rule_engine.get_rules_by_tenant("non-existent-tenant")
        
        assert len(rules) == 0

    def test_get_rules_by_user(self, rule_engine, sample_rule):
        """Test getting rules by user."""
        # Create user-specific rule
        user_rule = Rule(
            rule_id="user-rule-1",
            name="User Rule",
            description="User-specific rule",
            resource=RuleResource.CURVE,
            action=RuleAction.ALLOW,
            conditions=[],
            priority=50,
            tenant_id="tenant-1",
            user_id="user-123"
        )
        
        rule_engine.add_rule(sample_rule)
        rule_engine.add_rule(user_rule)
        
        rules = rule_engine.get_rules_by_user("user-123")
        
        assert len(rules) == 1
        assert rules[0].rule_id == "user-rule-1"

    def test_evaluate_rule_success(self, rule_engine, sample_rule, evaluation_context):
        """Test successful rule evaluation."""
        rule_engine.add_rule(sample_rule)
        
        result = rule_engine.evaluate(evaluation_context)
        
        assert result.allowed is True
        assert result.reason == "Rule 'Test Rule' matched"
        assert sample_rule.rule_id in result.matched_rules
        assert result.evaluation_time_ms > 0

    def test_evaluate_rule_deny(self, rule_engine, evaluation_context):
        """Test rule evaluation with deny action."""
        deny_rule = Rule(
            rule_id="deny-rule-1",
            name="Deny Rule",
            description="Rule that denies access",
            resource=RuleResource.CURVE,
            action=RuleAction.DENY,
            conditions=[
                RuleCondition(
                    field="tenant_id",
                    operator=RuleConditionOperator.EQUALS,
                    value="tenant-1"
                )
            ],
            priority=100,
            tenant_id="tenant-1"
        )
        
        rule_engine.add_rule(deny_rule)
        
        result = rule_engine.evaluate(evaluation_context)
        
        assert result.allowed is False
        assert result.reason == "Rule 'Deny Rule' matched"
        assert deny_rule.rule_id in result.matched_rules

    def test_evaluate_rule_no_match(self, rule_engine, evaluation_context):
        """Test rule evaluation with no matching rules."""
        no_match_rule = Rule(
            rule_id="no-match-rule-1",
            name="No Match Rule",
            description="Rule that doesn't match",
            resource=RuleResource.CURVE,
            action=RuleAction.ALLOW,
            conditions=[
                RuleCondition(
                    field="tenant_id",
                    operator=RuleConditionOperator.EQUALS,
                    value="different-tenant"
                )
            ],
            priority=100,
            tenant_id="different-tenant"
        )
        
        rule_engine.add_rule(no_match_rule)
        
        result = rule_engine.evaluate(evaluation_context)
        
        assert result.allowed is False
        assert result.reason == "No applicable rules matched"
        assert len(result.matched_rules) == 0

    def test_evaluate_rule_no_rules(self, rule_engine, evaluation_context):
        """Test rule evaluation with no rules."""
        result = rule_engine.evaluate(evaluation_context)
        
        assert result.allowed is False
        assert result.reason == "No rules found for resource"
        assert len(result.matched_rules) == 0

    def test_evaluate_rule_priority_order(self, rule_engine, evaluation_context):
        """Test rule evaluation with priority ordering."""
        # Lower priority rule (should be evaluated first)
        low_priority_rule = Rule(
            rule_id="low-priority-rule",
            name="Low Priority Rule",
            description="Low priority rule",
            resource=RuleResource.CURVE,
            action=RuleAction.DENY,
            conditions=[
                RuleCondition(
                    field="tenant_id",
                    operator=RuleConditionOperator.EQUALS,
                    value="tenant-1"
                )
            ],
            priority=50,
            tenant_id="tenant-1"
        )
        
        # Higher priority rule (should be evaluated second)
        high_priority_rule = Rule(
            rule_id="high-priority-rule",
            name="High Priority Rule",
            description="High priority rule",
            resource=RuleResource.CURVE,
            action=RuleAction.ALLOW,
            conditions=[
                RuleCondition(
                    field="tenant_id",
                    operator=RuleConditionOperator.EQUALS,
                    value="tenant-1"
                )
            ],
            priority=100,
            tenant_id="tenant-1"
        )
        
        rule_engine.add_rule(high_priority_rule)
        rule_engine.add_rule(low_priority_rule)
        
        result = rule_engine.evaluate(evaluation_context)
        
        # Should match the first rule (low priority) and deny
        assert result.allowed is False
        assert result.reason == "Rule 'Low Priority Rule' matched"
        assert "low-priority-rule" in result.matched_rules

    def test_evaluate_rule_expired(self, rule_engine, evaluation_context):
        """Test rule evaluation with expired rule."""
        expired_rule = Rule(
            rule_id="expired-rule-1",
            name="Expired Rule",
            description="Expired rule",
            resource=RuleResource.CURVE,
            action=RuleAction.ALLOW,
            conditions=[
                RuleCondition(
                    field="tenant_id",
                    operator=RuleConditionOperator.EQUALS,
                    value="tenant-1"
                )
            ],
            priority=100,
            tenant_id="tenant-1",
            expires_at=datetime.now() - timedelta(days=1)  # Expired yesterday
        )
        
        rule_engine.add_rule(expired_rule)
        
        result = rule_engine.evaluate(evaluation_context)
        
        assert result.allowed is False
        assert result.reason == "No applicable rules matched"

    def test_evaluate_rule_disabled(self, rule_engine, evaluation_context):
        """Test rule evaluation with disabled rule."""
        disabled_rule = Rule(
            rule_id="disabled-rule-1",
            name="Disabled Rule",
            description="Disabled rule",
            resource=RuleResource.CURVE,
            action=RuleAction.ALLOW,
            conditions=[
                RuleCondition(
                    field="tenant_id",
                    operator=RuleConditionOperator.EQUALS,
                    value="tenant-1"
                )
            ],
            priority=100,
            tenant_id="tenant-1",
            enabled=False
        )
        
        rule_engine.add_rule(disabled_rule)
        
        result = rule_engine.evaluate(evaluation_context)
        
        assert result.allowed is False
        assert result.reason == "No applicable rules matched"

    def test_evaluate_rule_condition_operators(self, rule_engine, evaluation_context):
        """Test rule evaluation with different condition operators."""
        # Test EQUALS operator
        equals_rule = Rule(
            rule_id="equals-rule",
            name="Equals Rule",
            description="Rule with equals condition",
            resource=RuleResource.CURVE,
            action=RuleAction.ALLOW,
            conditions=[
                RuleCondition(
                    field="tenant_id",
                    operator=RuleConditionOperator.EQUALS,
                    value="tenant-1"
                )
            ],
            priority=100,
            tenant_id="tenant-1"
        )
        
        rule_engine.add_rule(equals_rule)
        result = rule_engine.evaluate(evaluation_context)
        assert result.allowed is True

        # Test NOT_EQUALS operator
        rule_engine.remove_rule("equals-rule")
        not_equals_rule = Rule(
            rule_id="not-equals-rule",
            name="Not Equals Rule",
            description="Rule with not equals condition",
            resource=RuleResource.CURVE,
            action=RuleAction.ALLOW,
            conditions=[
                RuleCondition(
                    field="tenant_id",
                    operator=RuleConditionOperator.NOT_EQUALS,
                    value="different-tenant"
                )
            ],
            priority=100,
            tenant_id="tenant-1"
        )
        
        rule_engine.add_rule(not_equals_rule)
        result = rule_engine.evaluate(evaluation_context)
        assert result.allowed is True

        # Test CONTAINS operator
        rule_engine.remove_rule("not-equals-rule")
        contains_rule = Rule(
            rule_id="contains-rule",
            name="Contains Rule",
            description="Rule with contains condition",
            resource=RuleResource.CURVE,
            action=RuleAction.ALLOW,
            conditions=[
                RuleCondition(
                    field="user_roles",
                    operator=RuleConditionOperator.CONTAINS,
                    value="analyst"
                )
            ],
            priority=100,
            tenant_id="tenant-1"
        )
        
        rule_engine.add_rule(contains_rule)
        result = rule_engine.evaluate(evaluation_context)
        assert result.allowed is True

    def test_evaluate_rule_error_handling(self, rule_engine, evaluation_context):
        """Test rule evaluation error handling."""
        # Create rule with invalid condition
        invalid_rule = Rule(
            rule_id="invalid-rule",
            name="Invalid Rule",
            description="Rule with invalid condition",
            resource=RuleResource.CURVE,
            action=RuleAction.ALLOW,
            conditions=[
                RuleCondition(
                    field="nonexistent_field",
                    operator=RuleConditionOperator.EQUALS,
                    value="tenant-1"
                )
            ],
            priority=100,
            tenant_id="tenant-1"
        )
        
        rule_engine.add_rule(invalid_rule)
        
        result = rule_engine.evaluate(evaluation_context)
        
        assert result.allowed is False
        assert result.reason == "Rule evaluation error"

    def test_get_engine_stats(self, rule_engine, sample_rule):
        """Test getting engine statistics."""
        rule_engine.add_rule(sample_rule)
        
        stats = rule_engine.get_engine_stats()
        
        assert "total_rules" in stats
        assert "enabled_rules" in stats
        assert "disabled_rules" in stats
        assert "expired_rules" in stats
        assert stats["total_rules"] == 1
        assert stats["enabled_rules"] == 1
        assert stats["disabled_rules"] == 0
        assert stats["expired_rules"] == 0

    def test_cache_invalidation(self, rule_engine, sample_rule):
        """Test cache invalidation."""
        rule_engine.add_rule(sample_rule)
        
        # Cache should be populated
        rules = rule_engine.get_rules_for_resource("curve")
        assert len(rules) == 1
        
        # Remove rule
        rule_engine.remove_rule(sample_rule.rule_id)
        
        # Cache should be invalidated
        rules = rule_engine.get_rules_for_resource("curve")
        assert len(rules) == 0

    def test_rule_condition_evaluation(self, rule_engine):
        """Test individual rule condition evaluation."""
        context = EvaluationContext(
            user_id="user-123",
            tenant_id="tenant-1",
            resource="curve",
            action="read",
            context={
                "user_roles": ["user", "analyst"],
                "resource_id": "curve-1"
            }
        )
        
        # Test EQUALS condition
        condition = RuleCondition(
            field="tenant_id",
            operator=RuleConditionOperator.EQUALS,
            value="tenant-1"
        )
        
        result = rule_engine._evaluate_rule_conditions(
            Rule(rule_id="test", name="test", resource=RuleResource.CURVE, action=RuleAction.ALLOW, conditions=[condition]),
            context
        )
        
        assert result is True
        
        # Test NOT_EQUALS condition
        condition = RuleCondition(
            field="tenant_id",
            operator=RuleConditionOperator.NOT_EQUALS,
            value="different-tenant"
        )
        
        result = rule_engine._evaluate_rule_conditions(
            Rule(rule_id="test", name="test", resource=RuleResource.CURVE, action=RuleAction.ALLOW, conditions=[condition]),
            context
        )
        
        assert result is True
        
        # Test CONTAINS condition
        condition = RuleCondition(
            field="user_roles",
            operator=RuleConditionOperator.CONTAINS,
            value="analyst"
        )
        
        result = rule_engine._evaluate_rule_conditions(
            Rule(rule_id="test", name="test", resource=RuleResource.CURVE, action=RuleAction.ALLOW, conditions=[condition]),
            context
        )
        
        assert result is True