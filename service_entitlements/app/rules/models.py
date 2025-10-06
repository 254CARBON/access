"""
Rule data models for Entitlements Service.
"""

from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import sys
import os

# Add shared directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from pydantic import BaseModel, Field


class RuleAction(str, Enum):
    """Rule action types."""
    ALLOW = "allow"
    DENY = "deny"


class RuleResource(str, Enum):
    """Rule resource types."""
    CURVE = "curve"
    INSTRUMENT = "instrument"
    MARKET_DATA = "market_data"
    USER_PROFILE = "user_profile"
    ADMIN = "admin"


class RuleConditionOperator(str, Enum):
    """Rule condition operators."""
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    IN = "in"
    NOT_IN = "not_in"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    CONTAINS = "contains"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"


@dataclass
class RuleCondition:
    """Rule condition."""
    field: str
    operator: RuleConditionOperator
    value: Union[str, int, float, List[Union[str, int, float]]]
    description: Optional[str] = None


@dataclass
class Rule:
    """Authorization rule."""
    rule_id: str
    name: str
    description: Optional[str] = None
    resource: RuleResource = RuleResource.CURVE
    action: RuleAction = RuleAction.ALLOW
    conditions: List[RuleCondition] = field(default_factory=list)
    priority: int = 0
    enabled: bool = True
    tenant_id: Optional[str] = None
    user_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None


class EntitlementCheckRequest(BaseModel):
    """Request model for entitlement check."""
    user_id: str = Field(..., description="User ID")
    tenant_id: Optional[str] = Field(None, description="Tenant ID")
    resource: str = Field(..., description="Resource type")
    action: str = Field(..., description="Action to perform")
    context: Dict[str, Any] = Field(default_factory=dict, description="Additional context")


class EntitlementCheckResponse(BaseModel):
    """Response model for entitlement check."""
    allowed: bool = Field(..., description="Whether the action is allowed")
    reason: Optional[str] = Field(None, description="Reason for the decision")
    matched_rules: List[str] = Field(default_factory=list, description="Rule IDs that matched")
    expires_at: Optional[datetime] = Field(None, description="When this decision expires")
    ttl_seconds: Optional[int] = Field(None, description="Time to live in seconds")


class RuleCreateRequest(BaseModel):
    """Request model for creating a rule."""
    name: str = Field(..., description="Rule name")
    description: Optional[str] = Field(None, description="Rule description")
    resource: RuleResource = Field(..., description="Resource type")
    action: RuleAction = Field(..., description="Rule action")
    conditions: List[Dict[str, Any]] = Field(default_factory=list, description="Rule conditions")
    priority: int = Field(0, description="Rule priority")
    tenant_id: Optional[str] = Field(None, description="Tenant ID")
    user_id: Optional[str] = Field(None, description="User ID")
    expires_at: Optional[datetime] = Field(None, description="Expiration date")


class RuleUpdateRequest(BaseModel):
    """Request model for updating a rule."""
    name: Optional[str] = Field(None, description="Rule name")
    description: Optional[str] = Field(None, description="Rule description")
    resource: Optional[RuleResource] = Field(None, description="Resource type")
    action: Optional[RuleAction] = Field(None, description="Rule action")
    conditions: Optional[List[Dict[str, Any]]] = Field(None, description="Rule conditions")
    priority: Optional[int] = Field(None, description="Rule priority")
    enabled: Optional[bool] = Field(None, description="Whether rule is enabled")
    expires_at: Optional[datetime] = Field(None, description="Expiration date")


class RuleResponse(BaseModel):
    """Response model for rule operations."""
    rule_id: str
    name: str
    description: Optional[str]
    resource: RuleResource
    action: RuleAction
    conditions: List[Dict[str, Any]]
    priority: int
    enabled: bool
    tenant_id: Optional[str]
    user_id: Optional[str]
    created_at: datetime
    updated_at: datetime
    expires_at: Optional[datetime]


class RuleListResponse(BaseModel):
    """Response model for rule list."""
    rules: List[RuleResponse]
    total: int
    page: int
    limit: int


@dataclass
class EvaluationContext:
    """Context for rule evaluation."""
    user_id: str
    tenant_id: Optional[str]
    resource: str
    action: str
    context: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class EvaluationResult:
    """Result of rule evaluation."""
    allowed: bool
    reason: Optional[str] = None
    matched_rules: List[str] = field(default_factory=list)
    evaluation_time_ms: float = 0.0
    cache_hit: bool = False
