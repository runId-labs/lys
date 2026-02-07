"""
Mollie GraphQL nodes for subscription management.
"""

from datetime import datetime
from typing import Optional

from lys.apps.licensing.modules.subscription.services import SubscriptionService
from lys.core.graphql.nodes import ServiceNode
from lys.core.registries import register_node


@register_node()
class SubscribeToPlanResultNode(ServiceNode[SubscriptionService]):
    """Result of subscribing to a plan."""
    success: bool
    checkout_url: Optional[str] = None  # If payment required
    effective_date: Optional[datetime] = None  # If scheduled for later (downgrade)
    prorata_amount: Optional[int] = None  # Amount in cents (for display)
    error: Optional[str] = None


@register_node()
class CancelSubscriptionResultNode(ServiceNode[SubscriptionService]):
    """Result of canceling a subscription."""
    success: bool
    effective_date: Optional[datetime] = None  # When cancellation takes effect
    error: Optional[str] = None