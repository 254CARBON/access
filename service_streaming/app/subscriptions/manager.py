"""
Subscription manager for Streaming Service.
"""

import asyncio
from typing import Dict, Any, Optional, Set, List
from dataclasses import dataclass, field
from datetime import datetime
import sys
import os

# Add shared directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from shared.logging import get_logger
from shared.errors import AccessLayerException


@dataclass
class Subscription:
    """Subscription data."""
    subscription_id: str
    connection_id: str
    topic: str
    filters: Dict[str, Any] = field(default_factory=dict)
    user_id: Optional[str] = None
    tenant_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    last_message_at: Optional[datetime] = None
    message_count: int = 0


class SubscriptionManager:
    """Manages topic subscriptions across WebSocket and SSE connections."""
    
    def __init__(self):
        self.logger = get_logger("streaming.subscriptions.manager")
        
        # Subscription storage
        self.subscriptions: Dict[str, Subscription] = {}
        self.connection_subscriptions: Dict[str, Set[str]] = {}  # connection_id -> subscription_ids
        self.topic_subscriptions: Dict[str, Set[str]] = {}  # topic -> subscription_ids
        self.user_subscriptions: Dict[str, Set[str]] = {}  # user_id -> subscription_ids
        self.tenant_subscriptions: Dict[str, Set[str]] = {}  # tenant_id -> subscription_ids
    
    async def create_subscription(
        self,
        connection_id: str,
        topic: str,
        filters: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None
    ) -> str:
        """Create a new subscription."""
        import uuid
        subscription_id = str(uuid.uuid4())
        
        subscription = Subscription(
            subscription_id=subscription_id,
            connection_id=connection_id,
            topic=topic,
            filters=filters or {},
            user_id=user_id,
            tenant_id=tenant_id
        )
        
        # Store subscription
        self.subscriptions[subscription_id] = subscription
        
        # Update indices
        if connection_id not in self.connection_subscriptions:
            self.connection_subscriptions[connection_id] = set()
        self.connection_subscriptions[connection_id].add(subscription_id)
        
        if topic not in self.topic_subscriptions:
            self.topic_subscriptions[topic] = set()
        self.topic_subscriptions[topic].add(subscription_id)
        
        if user_id:
            if user_id not in self.user_subscriptions:
                self.user_subscriptions[user_id] = set()
            self.user_subscriptions[user_id].add(subscription_id)
        
        if tenant_id:
            if tenant_id not in self.tenant_subscriptions:
                self.tenant_subscriptions[tenant_id] = set()
            self.tenant_subscriptions[tenant_id].add(subscription_id)
        
        self.logger.info(
            "Subscription created",
            subscription_id=subscription_id,
            connection_id=connection_id,
            topic=topic,
            user_id=user_id,
            tenant_id=tenant_id
        )
        
        return subscription_id
    
    async def remove_subscription(self, subscription_id: str) -> bool:
        """Remove a subscription."""
        if subscription_id not in self.subscriptions:
            return False
        
        subscription = self.subscriptions[subscription_id]
        
        # Remove from indices
        if subscription.connection_id in self.connection_subscriptions:
            self.connection_subscriptions[subscription.connection_id].discard(subscription_id)
            if not self.connection_subscriptions[subscription.connection_id]:
                del self.connection_subscriptions[subscription.connection_id]
        
        if subscription.topic in self.topic_subscriptions:
            self.topic_subscriptions[subscription.topic].discard(subscription_id)
            if not self.topic_subscriptions[subscription.topic]:
                del self.topic_subscriptions[subscription.topic]
        
        if subscription.user_id and subscription.user_id in self.user_subscriptions:
            self.user_subscriptions[subscription.user_id].discard(subscription_id)
            if not self.user_subscriptions[subscription.user_id]:
                del self.user_subscriptions[subscription.user_id]
        
        if subscription.tenant_id and subscription.tenant_id in self.tenant_subscriptions:
            self.tenant_subscriptions[subscription.tenant_id].discard(subscription_id)
            if not self.tenant_subscriptions[subscription.tenant_id]:
                del self.tenant_subscriptions[subscription.tenant_id]
        
        # Remove subscription
        del self.subscriptions[subscription_id]
        
        self.logger.info(
            "Subscription removed",
            subscription_id=subscription_id,
            topic=subscription.topic
        )
        
        return True
    
    async def remove_connection_subscriptions(self, connection_id: str) -> int:
        """Remove all subscriptions for a connection."""
        if connection_id not in self.connection_subscriptions:
            return 0
        
        subscription_ids = self.connection_subscriptions[connection_id].copy()
        removed_count = 0
        
        for subscription_id in subscription_ids:
            if await self.remove_subscription(subscription_id):
                removed_count += 1
        
        self.logger.info(
            "Removed connection subscriptions",
            connection_id=connection_id,
            count=removed_count
        )
        
        return removed_count
    
    async def get_topic_subscribers(self, topic: str) -> List[str]:
        """Get connection IDs subscribed to a topic."""
        if topic not in self.topic_subscriptions:
            return []
        
        connection_ids = []
        for subscription_id in self.topic_subscriptions[topic]:
            subscription = self.subscriptions.get(subscription_id)
            if subscription:
                connection_ids.append(subscription.connection_id)
        
        return connection_ids
    
    async def get_user_subscriptions(self, user_id: str) -> List[Subscription]:
        """Get all subscriptions for a user."""
        if user_id not in self.user_subscriptions:
            return []
        
        subscriptions = []
        for subscription_id in self.user_subscriptions[user_id]:
            subscription = self.subscriptions.get(subscription_id)
            if subscription:
                subscriptions.append(subscription)
        
        return subscriptions
    
    async def get_tenant_subscriptions(self, tenant_id: str) -> List[Subscription]:
        """Get all subscriptions for a tenant."""
        if tenant_id not in self.tenant_subscriptions:
            return []
        
        subscriptions = []
        for subscription_id in self.tenant_subscriptions[tenant_id]:
            subscription = self.subscriptions.get(subscription_id)
            if subscription:
                subscriptions.append(subscription)
        
        return subscriptions
    
    async def update_subscription_activity(self, subscription_id: str):
        """Update subscription activity timestamp."""
        if subscription_id in self.subscriptions:
            subscription = self.subscriptions[subscription_id]
            subscription.last_message_at = datetime.now()
            subscription.message_count += 1
    
    async def apply_filters(
        self,
        subscription_id: str,
        message_data: Dict[str, Any]
    ) -> bool:
        """Apply subscription filters to message data."""
        if subscription_id not in self.subscriptions:
            return False
        
        subscription = self.subscriptions[subscription_id]
        filters = subscription.filters
        
        if not filters:
            return True
        
        # Simple filter implementation
        # In production, this would be more sophisticated
        for filter_key, filter_value in filters.items():
            if filter_key not in message_data:
                return False
            
            if isinstance(filter_value, dict):
                # Range filter
                if "min" in filter_value and message_data[filter_key] < filter_value["min"]:
                    return False
                if "max" in filter_value and message_data[filter_key] > filter_value["max"]:
                    return False
            elif isinstance(filter_value, list):
                # Value list filter
                if message_data[filter_key] not in filter_value:
                    return False
            else:
                # Exact match filter
                if message_data[filter_key] != filter_value:
                    return False
        
        return True
    
    def get_subscription_stats(self) -> Dict[str, Any]:
        """Get subscription statistics."""
        return {
            "total_subscriptions": len(self.subscriptions),
            "total_topics": len(self.topic_subscriptions),
            "total_users": len(self.user_subscriptions),
            "total_tenants": len(self.tenant_subscriptions),
            "topics": list(self.topic_subscriptions.keys())
        }
    
    def get_topic_stats(self, topic: str) -> Dict[str, Any]:
        """Get statistics for a specific topic."""
        if topic not in self.topic_subscriptions:
            return {
                "topic": topic,
                "subscriber_count": 0,
                "subscriptions": []
            }
        
        subscriptions = []
        for subscription_id in self.topic_subscriptions[topic]:
            subscription = self.subscriptions.get(subscription_id)
            if subscription:
                subscriptions.append({
                    "subscription_id": subscription_id,
                    "connection_id": subscription.connection_id,
                    "user_id": subscription.user_id,
                    "tenant_id": subscription.tenant_id,
                    "message_count": subscription.message_count,
                    "created_at": subscription.created_at.isoformat(),
                    "last_message_at": subscription.last_message_at.isoformat() if subscription.last_message_at else None
                })
        
        return {
            "topic": topic,
            "subscriber_count": len(subscriptions),
            "subscriptions": subscriptions
        }
    
    async def cleanup_inactive_subscriptions(self, max_age_seconds: int = 3600):
        """Clean up inactive subscriptions."""
        current_time = datetime.now()
        inactive_subscriptions = []
        
        for subscription_id, subscription in self.subscriptions.items():
            # Check if subscription is inactive
            last_activity = subscription.last_message_at or subscription.created_at
            age = (current_time - last_activity).total_seconds()
            
            if age > max_age_seconds:
                inactive_subscriptions.append(subscription_id)
        
        # Remove inactive subscriptions
        removed_count = 0
        for subscription_id in inactive_subscriptions:
            if await self.remove_subscription(subscription_id):
                removed_count += 1
        
        if removed_count > 0:
            self.logger.info(
                "Cleaned up inactive subscriptions",
                count=removed_count
            )
        
        return removed_count
