"""
Entitlements service for 254Carbon Access Layer.
"""

import asyncio
import json
import sys
import os
import time
from typing import Dict, Any, Optional, List
from datetime import datetime

# Add shared directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from fastapi import HTTPException, Query, Body
from shared.base_service import BaseService
from shared.logging import get_logger
from shared.errors import AccessLayerException
from shared.observability import get_observability_manager, observe_function, observe_operation

from .rules.engine import RuleEngine
from .rules.models import (
    Rule, RuleCondition, RuleConditionOperator, RuleAction,
    EntitlementCheckRequest, EntitlementCheckResponse,
    RuleCreateRequest, RuleUpdateRequest, RuleResponse, RuleListResponse,
    EvaluationContext
)
from .persistence.postgres import PostgreSQLPersistence
from .cache.redis_cache import RedisCache


class EntitlementsService(BaseService):
    """Entitlements service implementation."""
    
    def __init__(self):
        super().__init__("entitlements", 8011)
        
        # Initialize observability
        self.observability = get_observability_manager(
            "entitlements",
            log_level=self.config.log_level,
            otel_exporter=self.config.otel_exporter,
            enable_console=self.config.enable_console_tracing
        )
        
        # Initialize components
        self.rule_engine = RuleEngine()
        self.persistence = PostgreSQLPersistence(self.config.postgres_dsn)
        self.cache = RedisCache(self.config.redis_url)
        
        self._setup_entitlements_routes()
    
    def _setup_entitlements_routes(self):
        """Set up entitlements-specific routes."""
        
        @self.app.get("/")
        async def root():
            """Root endpoint."""
            return {
                "service": "entitlements",
                "message": "254Carbon Access Layer - Entitlements Service",
                "version": "1.0.0",
                "capabilities": ["rule_engine", "caching", "persistence"]
            }
        
        @self.app.post("/entitlements/check")
        @observe_function("entitlements_check")
        async def check_entitlements(request: EntitlementCheckRequest):
            """Check entitlements for a user action."""
            start_time = time.time()
            
            try:
                # Set user context for logging
                self.observability.trace_request(
                    user_id=request.user_id,
                    tenant_id=request.tenant_id
                )
                # Generate context hash for caching
                import hashlib
                context_str = json.dumps({
                    "user_id": request.user_id,
                    "tenant_id": request.tenant_id,
                    "resource": request.resource,
                    "action": request.action,
                    "context": request.context
                }, sort_keys=True)
                context_hash = hashlib.md5(context_str.encode()).hexdigest()
                
                # Check cache first
                cached_result = await self.cache.get_entitlement_result(
                    request.user_id,
                    request.tenant_id,
                    request.resource,
                    request.action,
                    context_hash
                )
                
                if cached_result:
                    # Log cache hit
                    self.observability.log_business_event(
                        "entitlement_cache_hit",
                        user_id=request.user_id,
                        tenant_id=request.tenant_id,
                        resource=request.resource,
                        action=request.action
                    )
                    return cached_result
                
                # Create evaluation context
                context = EvaluationContext(
                    user_id=request.user_id,
                    tenant_id=request.tenant_id,
                    resource=request.resource,
                    action=request.action,
                    context=request.context
                )
                
                # Evaluate rules
                result = self.rule_engine.evaluate(context)
                
                # Create response
                response = EntitlementCheckResponse(
                    allowed=result.allowed,
                    reason=result.reason,
                    matched_rules=result.matched_rules,
                    ttl_seconds=300  # 5 minutes default TTL
                )
                
                # Cache the result
                await self.cache.set_entitlement_result(
                    request.user_id,
                    request.tenant_id,
                    request.resource,
                    request.action,
                    context_hash,
                    response
                )
                
                # Log entitlement check result
                self.observability.log_business_event(
                    "entitlement_check_completed",
                    user_id=request.user_id,
                    tenant_id=request.tenant_id,
                    resource=request.resource,
                    action=request.action,
                    allowed=result.allowed,
                    evaluation_time_ms=result.evaluation_time_ms,
                    cache_hit=False
                )
                
                return response
                
            except Exception as e:
                self.logger.error("Error checking entitlements", error=str(e))
                raise HTTPException(status_code=500, detail="Internal server error")
        
        @self.app.get("/entitlements/rules")
        async def get_rules(
            tenant_id: Optional[str] = Query(None, description="Filter by tenant"),
            user_id: Optional[str] = Query(None, description="Filter by user"),
            resource: Optional[str] = Query(None, description="Filter by resource"),
            page: int = Query(1, ge=1, description="Page number"),
            limit: int = Query(50, ge=1, le=100, description="Items per page")
        ):
            """Get rules with optional filtering."""
            try:
                # Get rules from engine
                if resource:
                    rules = self.rule_engine.get_rules_for_resource(resource)
                elif tenant_id:
                    rules = self.rule_engine.get_rules_by_tenant(tenant_id)
                elif user_id:
                    rules = self.rule_engine.get_rules_by_user(user_id)
                else:
                    rules = list(self.rule_engine.rules.values())
                
                # Apply pagination
                total = len(rules)
                start_idx = (page - 1) * limit
                end_idx = start_idx + limit
                paginated_rules = rules[start_idx:end_idx]
                
                # Convert to response format
                rule_responses = []
                for rule in paginated_rules:
                    rule_responses.append(RuleResponse(
                        rule_id=rule.rule_id,
                        name=rule.name,
                        description=rule.description,
                        resource=rule.resource,
                        action=rule.action,
                        conditions=[
                            {
                                "field": c.field,
                                "operator": c.operator.value,
                                "value": c.value,
                                "description": c.description
                            }
                            for c in rule.conditions
                        ],
                        priority=rule.priority,
                        enabled=rule.enabled,
                        tenant_id=rule.tenant_id,
                        user_id=rule.user_id,
                        created_at=rule.created_at,
                        updated_at=rule.updated_at,
                        expires_at=rule.expires_at
                    ))
                
                return RuleListResponse(
                    rules=rule_responses,
                    total=total,
                    page=page,
                    limit=limit
                )
                
            except Exception as e:
                self.logger.error("Error getting rules", error=str(e))
                raise HTTPException(status_code=500, detail="Internal server error")
        
        @self.app.post("/entitlements/rules")
        async def create_rule(request: RuleCreateRequest):
            """Create a new rule."""
            try:
                # Generate rule ID
                import uuid
                rule_id = str(uuid.uuid4())
                
                # Convert conditions
                conditions = []
                for condition_data in request.conditions:
                    condition = RuleCondition(
                        field=condition_data["field"],
                        operator=RuleConditionOperator(condition_data["operator"]),
                        value=condition_data["value"],
                        description=condition_data.get("description")
                    )
                    conditions.append(condition)
                
                # Create rule
                rule = Rule(
                    rule_id=rule_id,
                    name=request.name,
                    description=request.description,
                    resource=request.resource,
                    action=request.action,
                    conditions=conditions,
                    priority=request.priority,
                    tenant_id=request.tenant_id,
                    user_id=request.user_id,
                    expires_at=request.expires_at
                )
                
                # Add to engine
                success = self.rule_engine.add_rule(rule)
                if not success:
                    raise HTTPException(status_code=500, detail="Failed to add rule to engine")
                
                # Save to database
                success = await self.persistence.save_rule(rule)
                if not success:
                    # Remove from engine if database save failed
                    self.rule_engine.remove_rule(rule_id)
                    raise HTTPException(status_code=500, detail="Failed to save rule to database")
                
                # Invalidate relevant caches
                if rule.tenant_id:
                    await self.cache.invalidate_tenant_entitlements(rule.tenant_id)
                if rule.user_id:
                    await self.cache.invalidate_user_entitlements(rule.user_id)
                await self.cache.invalidate_resource_entitlements(rule.resource.value)
                
                self.logger.info("Rule created", rule_id=rule_id, name=rule.name)
                
                return RuleResponse(
                    rule_id=rule.rule_id,
                    name=rule.name,
                    description=rule.description,
                    resource=rule.resource,
                    action=rule.action,
                    conditions=[
                        {
                            "field": c.field,
                            "operator": c.operator.value,
                            "value": c.value,
                            "description": c.description
                        }
                        for c in rule.conditions
                    ],
                    priority=rule.priority,
                    enabled=rule.enabled,
                    tenant_id=rule.tenant_id,
                    user_id=rule.user_id,
                    created_at=rule.created_at,
                    updated_at=rule.updated_at,
                    expires_at=rule.expires_at
                )
                
            except HTTPException:
                raise
            except Exception as e:
                self.logger.error("Error creating rule", error=str(e))
                raise HTTPException(status_code=500, detail="Internal server error")
        
        @self.app.put("/entitlements/rules/{rule_id}")
        async def update_rule(rule_id: str, request: RuleUpdateRequest):
            """Update an existing rule."""
            try:
                # Get existing rule
                existing_rule = self.rule_engine.get_rule(rule_id)
                if not existing_rule:
                    raise HTTPException(status_code=404, detail="Rule not found")
                
                # Update fields
                if request.name is not None:
                    existing_rule.name = request.name
                if request.description is not None:
                    existing_rule.description = request.description
                if request.resource is not None:
                    existing_rule.resource = request.resource
                if request.action is not None:
                    existing_rule.action = request.action
                if request.priority is not None:
                    existing_rule.priority = request.priority
                if request.enabled is not None:
                    existing_rule.enabled = request.enabled
                if request.expires_at is not None:
                    existing_rule.expires_at = request.expires_at
                if request.conditions is not None:
                    conditions = []
                    for condition_data in request.conditions:
                        condition = RuleCondition(
                            field=condition_data["field"],
                            operator=RuleConditionOperator(condition_data["operator"]),
                            value=condition_data["value"],
                            description=condition_data.get("description")
                        )
                        conditions.append(condition)
                    existing_rule.conditions = conditions
                
                existing_rule.updated_at = datetime.now()
                
                # Update in engine
                success = self.rule_engine.update_rule(existing_rule)
                if not success:
                    raise HTTPException(status_code=500, detail="Failed to update rule in engine")
                
                # Save to database
                success = await self.persistence.save_rule(existing_rule)
                if not success:
                    raise HTTPException(status_code=500, detail="Failed to save rule to database")
                
                # Invalidate relevant caches
                if existing_rule.tenant_id:
                    await self.cache.invalidate_tenant_entitlements(existing_rule.tenant_id)
                if existing_rule.user_id:
                    await self.cache.invalidate_user_entitlements(existing_rule.user_id)
                await self.cache.invalidate_resource_entitlements(existing_rule.resource.value)
                
                self.logger.info("Rule updated", rule_id=rule_id, name=existing_rule.name)
                
                return RuleResponse(
                    rule_id=existing_rule.rule_id,
                    name=existing_rule.name,
                    description=existing_rule.description,
                    resource=existing_rule.resource,
                    action=existing_rule.action,
                    conditions=[
                        {
                            "field": c.field,
                            "operator": c.operator.value,
                            "value": c.value,
                            "description": c.description
                        }
                        for c in existing_rule.conditions
                    ],
                    priority=existing_rule.priority,
                    enabled=existing_rule.enabled,
                    tenant_id=existing_rule.tenant_id,
                    user_id=existing_rule.user_id,
                    created_at=existing_rule.created_at,
                    updated_at=existing_rule.updated_at,
                    expires_at=existing_rule.expires_at
                )
                
            except HTTPException:
                raise
            except Exception as e:
                self.logger.error("Error updating rule", error=str(e))
                raise HTTPException(status_code=500, detail="Internal server error")
        
        @self.app.delete("/entitlements/rules/{rule_id}")
        async def delete_rule(rule_id: str):
            """Delete a rule."""
            try:
                # Get existing rule
                existing_rule = self.rule_engine.get_rule(rule_id)
                if not existing_rule:
                    raise HTTPException(status_code=404, detail="Rule not found")
                
                # Remove from engine
                success = self.rule_engine.remove_rule(rule_id)
                if not success:
                    raise HTTPException(status_code=500, detail="Failed to remove rule from engine")
                
                # Delete from database
                success = await self.persistence.delete_rule(rule_id)
                if not success:
                    # Re-add to engine if database delete failed
                    self.rule_engine.add_rule(existing_rule)
                    raise HTTPException(status_code=500, detail="Failed to delete rule from database")
                
                # Invalidate relevant caches
                if existing_rule.tenant_id:
                    await self.cache.invalidate_tenant_entitlements(existing_rule.tenant_id)
                if existing_rule.user_id:
                    await self.cache.invalidate_user_entitlements(existing_rule.user_id)
                await self.cache.invalidate_resource_entitlements(existing_rule.resource.value)
                
                self.logger.info("Rule deleted", rule_id=rule_id, name=existing_rule.name)
                
                return {"success": True, "message": "Rule deleted successfully"}
                
            except HTTPException:
                raise
            except Exception as e:
                self.logger.error("Error deleting rule", error=str(e))
                raise HTTPException(status_code=500, detail="Internal server error")
        
        @self.app.get("/entitlements/stats")
        async def get_stats():
            """Get entitlements service statistics."""
            try:
                engine_stats = self.rule_engine.get_engine_stats()
                cache_stats = await self.cache.get_cache_stats()
                persistence_stats = await self.persistence.get_rule_stats()
                
                return {
                    "engine": engine_stats,
                    "cache": cache_stats,
                    "persistence": persistence_stats,
                    "timestamp": datetime.now().isoformat()
                }
                
            except Exception as e:
                self.logger.error("Error getting stats", error=str(e))
                raise HTTPException(status_code=500, detail="Internal server error")
    
    async def _check_dependencies(self):
        """Check entitlements service dependencies."""
        dependencies = {}
        
        # Check Redis
        try:
            if await self.cache.health_check():
                dependencies["redis"] = "ok"
            else:
                dependencies["redis"] = "error"
        except Exception:
            dependencies["redis"] = "error"
        
        # Check PostgreSQL
        try:
            if await self.persistence.health_check():
                dependencies["postgres"] = "ok"
            else:
                dependencies["postgres"] = "error"
        except Exception:
            dependencies["postgres"] = "error"
        
        return dependencies
    
    async def start(self):
        """Start entitlements service components."""
        await self.persistence.start()
        await self.cache.start()
        
        # Load rules from database
        rules = await self.persistence.load_all_rules()
        for rule in rules:
            self.rule_engine.add_rule(rule)
        
        self.logger.info(f"Entitlements service started with {len(rules)} rules")
    
    async def stop(self):
        """Stop entitlements service components."""
        await self.persistence.stop()
        await self.cache.stop()
        
        self.logger.info("Entitlements service stopped")


def create_app():
    """Create entitlements service application."""
    service = EntitlementsService()
    return service.app


if __name__ == "__main__":
    service = EntitlementsService()
    service.run()