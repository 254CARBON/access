"""
Rule evaluation engine for Entitlements Service.
"""

import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import sys
import os

# Add shared directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from shared.logging import get_logger
from shared.errors import AccessLayerException
from .models import (
    Rule, RuleCondition, RuleConditionOperator, RuleAction,
    EvaluationContext, EvaluationResult
)


class RuleEngine:
    """Rule evaluation engine."""
    
    def __init__(self):
        self.logger = get_logger("entitlements.rule_engine")
        self.rules: Dict[str, Rule] = {}
        self.rule_cache: Dict[str, List[Rule]] = {}  # resource -> rules
    
    def add_rule(self, rule: Rule) -> bool:
        """Add a rule to the engine."""
        try:
            self.rules[rule.rule_id] = rule
            self._invalidate_cache()
            self.logger.info("Rule added", rule_id=rule.rule_id, name=rule.name)
            return True
        except Exception as e:
            self.logger.error("Error adding rule", rule_id=rule.rule_id, error=str(e))
            return False
    
    def remove_rule(self, rule_id: str) -> bool:
        """Remove a rule from the engine."""
        if rule_id in self.rules:
            rule = self.rules[rule_id]
            del self.rules[rule_id]
            self._invalidate_cache()
            self.logger.info("Rule removed", rule_id=rule_id, name=rule.name)
            return True
        return False
    
    def update_rule(self, rule: Rule) -> bool:
        """Update a rule in the engine."""
        if rule.rule_id in self.rules:
            self.rules[rule.rule_id] = rule
            self._invalidate_cache()
            self.logger.info("Rule updated", rule_id=rule.rule_id, name=rule.name)
            return True
        return False
    
    def get_rule(self, rule_id: str) -> Optional[Rule]:
        """Get a rule by ID."""
        return self.rules.get(rule_id)
    
    def get_rules_for_resource(self, resource: str) -> List[Rule]:
        """Get all rules for a resource."""
        if resource in self.rule_cache:
            return self.rule_cache[resource]
        
        # Filter rules for resource
        rules = [
            rule for rule in self.rules.values()
            if rule.resource.value == resource and rule.enabled
        ]
        
        # Sort by priority (higher priority first)
        rules.sort(key=lambda r: r.priority, reverse=True)
        
        # Cache result
        self.rule_cache[resource] = rules
        
        return rules
    
    def evaluate(self, context: EvaluationContext) -> EvaluationResult:
        """Evaluate rules against context."""
        start_time = time.time()
        
        try:
            # Get applicable rules
            rules = self.get_rules_for_resource(context.resource)
            
            if not rules:
                # No rules found - default deny
                return EvaluationResult(
                    allowed=False,
                    reason="No rules found for resource",
                    evaluation_time_ms=(time.time() - start_time) * 1000
                )
            
            # Evaluate rules in priority order
            for rule in rules:
                if self._is_rule_applicable(rule, context):
                    if self._evaluate_rule_conditions(rule, context):
                        # Rule matched - return result
                        result = EvaluationResult(
                            allowed=(rule.action == RuleAction.ALLOW),
                            reason=f"Rule '{rule.name}' matched",
                            matched_rules=[rule.rule_id],
                            evaluation_time_ms=(time.time() - start_time) * 1000
                        )
                        
                        self.logger.debug(
                            "Rule evaluation result",
                            rule_id=rule.rule_id,
                            allowed=result.allowed,
                            reason=result.reason
                        )
                        
                        return result
            
            # No rules matched - default deny
            return EvaluationResult(
                allowed=False,
                reason="No applicable rules matched",
                evaluation_time_ms=(time.time() - start_time) * 1000
            )
            
        except Exception as e:
            self.logger.error("Rule evaluation error", error=str(e))
            return EvaluationResult(
                allowed=False,
                reason="Rule evaluation error",
                evaluation_time_ms=(time.time() - start_time) * 1000
            )
    
    def _is_rule_applicable(self, rule: Rule, context: EvaluationContext) -> bool:
        """Check if a rule is applicable to the context."""
        # Check tenant match
        if rule.tenant_id and rule.tenant_id != context.tenant_id:
            return False
        
        # Check user match
        if rule.user_id and rule.user_id != context.user_id:
            return False
        
        # Check expiration
        if rule.expires_at and rule.expires_at < context.timestamp:
            return False
        
        return True
    
    def _evaluate_rule_conditions(self, rule: Rule, context: EvaluationContext) -> bool:
        """Evaluate rule conditions against context."""
        if not rule.conditions:
            return True
        
        for condition in rule.conditions:
            if not self._evaluate_condition(condition, context):
                return False
        
        return True
    
    def _evaluate_condition(self, condition: RuleCondition, context: EvaluationContext) -> bool:
        """Evaluate a single condition."""
        try:
            # Get field value from context
            field_value = self._get_field_value(condition.field, context)
            
            if field_value is None:
                return False
            
            # Evaluate based on operator
            if condition.operator == RuleConditionOperator.EQUALS:
                return field_value == condition.value
            
            elif condition.operator == RuleConditionOperator.NOT_EQUALS:
                return field_value != condition.value
            
            elif condition.operator == RuleConditionOperator.IN:
                return field_value in condition.value
            
            elif condition.operator == RuleConditionOperator.NOT_IN:
                return field_value not in condition.value
            
            elif condition.operator == RuleConditionOperator.GREATER_THAN:
                return field_value > condition.value
            
            elif condition.operator == RuleConditionOperator.LESS_THAN:
                return field_value < condition.value
            
            elif condition.operator == RuleConditionOperator.CONTAINS:
                return str(condition.value) in str(field_value)
            
            elif condition.operator == RuleConditionOperator.STARTS_WITH:
                return str(field_value).startswith(str(condition.value))
            
            elif condition.operator == RuleConditionOperator.ENDS_WITH:
                return str(field_value).endswith(str(condition.value))
            
            else:
                self.logger.warning("Unknown condition operator", operator=condition.operator)
                return False
                
        except Exception as e:
            self.logger.error("Error evaluating condition", error=str(e))
            return False
    
    def _get_field_value(self, field: str, context: EvaluationContext) -> Any:
        """Get field value from context."""
        # Check direct context fields
        if field in context.context:
            return context.context[field]
        
        # Check special fields
        if field == "user_id":
            return context.user_id
        
        if field == "tenant_id":
            return context.tenant_id
        
        if field == "resource":
            return context.resource
        
        if field == "action":
            return context.action
        
        # Check nested fields (e.g., "resource.curve_id")
        if "." in field:
            parts = field.split(".")
            value = context.context
            
            for part in parts:
                if isinstance(value, dict) and part in value:
                    value = value[part]
                else:
                    return None
            
            return value
        
        return None
    
    def _invalidate_cache(self):
        """Invalidate rule cache."""
        self.rule_cache.clear()
    
    def get_engine_stats(self) -> Dict[str, Any]:
        """Get engine statistics."""
        return {
            "total_rules": len(self.rules),
            "enabled_rules": len([r for r in self.rules.values() if r.enabled]),
            "cached_resources": len(self.rule_cache),
            "resources": list(set(r.resource.value for r in self.rules.values()))
        }
    
    def clear_all_rules(self):
        """Clear all rules from the engine."""
        self.rules.clear()
        self._invalidate_cache()
        self.logger.info("All rules cleared")
    
    def get_rules_by_tenant(self, tenant_id: str) -> List[Rule]:
        """Get all rules for a tenant."""
        return [
            rule for rule in self.rules.values()
            if rule.tenant_id == tenant_id
        ]
    
    def get_rules_by_user(self, user_id: str) -> List[Rule]:
        """Get all rules for a user."""
        return [
            rule for rule in self.rules.values()
            if rule.user_id == user_id
        ]