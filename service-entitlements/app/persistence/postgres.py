"""
PostgreSQL persistence layer for Entitlements Service.
"""

import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime
import sys
import os

# Add shared directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..'))

import asyncpg
from shared.logging import get_logger
from shared.errors import AccessLayerException
from ..rules.models import Rule, RuleCondition, RuleConditionOperator, RuleAction, RuleResource


class PostgreSQLPersistence:
    """PostgreSQL persistence layer for rules."""
    
    def __init__(self, dsn: str):
        self.dsn = dsn
        self.logger = get_logger("entitlements.persistence.postgres")
        self.pool: Optional[asyncpg.Pool] = None
    
    async def start(self):
        """Start the persistence layer."""
        try:
            self.pool = await asyncpg.create_pool(
                self.dsn,
                min_size=2,
                max_size=10,
                command_timeout=30
            )
            
            # Create tables if they don't exist
            await self._create_tables()
            
            self.logger.info("PostgreSQL persistence started")
            
        except Exception as e:
            self.logger.error("Failed to start PostgreSQL persistence", error=str(e))
            raise AccessLayerException("POSTGRES_START_FAILED", str(e))
    
    async def stop(self):
        """Stop the persistence layer."""
        if self.pool:
            await self.pool.close()
            self.logger.info("PostgreSQL persistence stopped")
    
    async def _create_tables(self):
        """Create database tables."""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS rules (
                    rule_id VARCHAR(255) PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    description TEXT,
                    resource VARCHAR(100) NOT NULL,
                    action VARCHAR(20) NOT NULL,
                    conditions JSONB NOT NULL DEFAULT '[]',
                    priority INTEGER NOT NULL DEFAULT 0,
                    enabled BOOLEAN NOT NULL DEFAULT TRUE,
                    tenant_id VARCHAR(255),
                    user_id VARCHAR(255),
                    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                    expires_at TIMESTAMP WITH TIME ZONE
                );
            """)
            
            # Create indexes
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_rules_resource ON rules(resource);
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_rules_tenant ON rules(tenant_id);
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_rules_user ON rules(user_id);
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_rules_enabled ON rules(enabled);
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_rules_priority ON rules(priority DESC);
            """)
    
    async def save_rule(self, rule: Rule) -> bool:
        """Save a rule to the database."""
        try:
            async with self.pool.acquire() as conn:
                # Serialize conditions
                conditions_json = [
                    {
                        "field": c.field,
                        "operator": c.operator.value,
                        "value": c.value,
                        "description": c.description
                    }
                    for c in rule.conditions
                ]
                
                await conn.execute("""
                    INSERT INTO rules (
                        rule_id, name, description, resource, action, conditions,
                        priority, enabled, tenant_id, user_id, created_at, updated_at, expires_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                    ON CONFLICT (rule_id) DO UPDATE SET
                        name = EXCLUDED.name,
                        description = EXCLUDED.description,
                        resource = EXCLUDED.resource,
                        action = EXCLUDED.action,
                        conditions = EXCLUDED.conditions,
                        priority = EXCLUDED.priority,
                        enabled = EXCLUDED.enabled,
                        tenant_id = EXCLUDED.tenant_id,
                        user_id = EXCLUDED.user_id,
                        updated_at = EXCLUDED.updated_at,
                        expires_at = EXCLUDED.expires_at
                """, 
                    rule.rule_id, rule.name, rule.description, rule.resource.value,
                    rule.action.value, conditions_json, rule.priority, rule.enabled,
                    rule.tenant_id, rule.user_id, rule.created_at, rule.updated_at, rule.expires_at
                )
                
                self.logger.info("Rule saved", rule_id=rule.rule_id, name=rule.name)
                return True
                
        except Exception as e:
            self.logger.error("Error saving rule", rule_id=rule.rule_id, error=str(e))
            return False
    
    async def load_rule(self, rule_id: str) -> Optional[Rule]:
        """Load a rule from the database."""
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow("""
                    SELECT * FROM rules WHERE rule_id = $1
                """, rule_id)
                
                if not row:
                    return None
                
                return self._row_to_rule(row)
                
        except Exception as e:
            self.logger.error("Error loading rule", rule_id=rule_id, error=str(e))
            return None
    
    async def load_all_rules(self) -> List[Rule]:
        """Load all rules from the database."""
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT * FROM rules ORDER BY priority DESC, created_at ASC
                """)
                
                return [self._row_to_rule(row) for row in rows]
                
        except Exception as e:
            self.logger.error("Error loading all rules", error=str(e))
            return []
    
    async def load_rules_for_resource(self, resource: str) -> List[Rule]:
        """Load rules for a specific resource."""
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT * FROM rules 
                    WHERE resource = $1 AND enabled = TRUE
                    ORDER BY priority DESC, created_at ASC
                """, resource)
                
                return [self._row_to_rule(row) for row in rows]
                
        except Exception as e:
            self.logger.error("Error loading rules for resource", resource=resource, error=str(e))
            return []
    
    async def load_rules_for_tenant(self, tenant_id: str) -> List[Rule]:
        """Load rules for a specific tenant."""
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT * FROM rules 
                    WHERE tenant_id = $1
                    ORDER BY priority DESC, created_at ASC
                """, tenant_id)
                
                return [self._row_to_rule(row) for row in rows]
                
        except Exception as e:
            self.logger.error("Error loading rules for tenant", tenant_id=tenant_id, error=str(e))
            return []
    
    async def delete_rule(self, rule_id: str) -> bool:
        """Delete a rule from the database."""
        try:
            async with self.pool.acquire() as conn:
                result = await conn.execute("""
                    DELETE FROM rules WHERE rule_id = $1
                """, rule_id)
                
                if result == "DELETE 1":
                    self.logger.info("Rule deleted", rule_id=rule_id)
                    return True
                else:
                    self.logger.warning("Rule not found for deletion", rule_id=rule_id)
                    return False
                
        except Exception as e:
            self.logger.error("Error deleting rule", rule_id=rule_id, error=str(e))
            return False
    
    async def get_rule_count(self) -> int:
        """Get total number of rules."""
        try:
            async with self.pool.acquire() as conn:
                count = await conn.fetchval("SELECT COUNT(*) FROM rules")
                return count or 0
        except Exception as e:
            self.logger.error("Error getting rule count", error=str(e))
            return 0
    
    async def get_rule_stats(self) -> Dict[str, Any]:
        """Get rule statistics."""
        try:
            async with self.pool.acquire() as conn:
                stats = await conn.fetchrow("""
                    SELECT 
                        COUNT(*) as total_rules,
                        COUNT(*) FILTER (WHERE enabled = TRUE) as enabled_rules,
                        COUNT(*) FILTER (WHERE tenant_id IS NOT NULL) as tenant_rules,
                        COUNT(*) FILTER (WHERE user_id IS NOT NULL) as user_rules,
                        COUNT(DISTINCT resource) as unique_resources,
                        COUNT(DISTINCT tenant_id) as unique_tenants
                    FROM rules
                """)
                
                return dict(stats)
                
        except Exception as e:
            self.logger.error("Error getting rule stats", error=str(e))
            return {}
    
    def _row_to_rule(self, row) -> Rule:
        """Convert database row to Rule object."""
        # Deserialize conditions
        conditions = []
        for condition_data in row['conditions']:
            condition = RuleCondition(
                field=condition_data['field'],
                operator=RuleConditionOperator(condition_data['operator']),
                value=condition_data['value'],
                description=condition_data.get('description')
            )
            conditions.append(condition)
        
        return Rule(
            rule_id=row['rule_id'],
            name=row['name'],
            description=row['description'],
            resource=RuleResource(row['resource']),
            action=RuleAction(row['action']),
            conditions=conditions,
            priority=row['priority'],
            enabled=row['enabled'],
            tenant_id=row['tenant_id'],
            user_id=row['user_id'],
            created_at=row['created_at'],
            updated_at=row['updated_at'],
            expires_at=row['expires_at']
        )
    
    async def health_check(self) -> bool:
        """Check database health."""
        try:
            async with self.pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
                return True
        except Exception:
            return False
