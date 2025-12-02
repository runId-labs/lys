"""
Stripe GraphQL nodes for subscription management.
"""

from typing import Optional

from lys.apps.licensing.modules.stripe.services import StripeSyncService
from lys.core.graphql.nodes import ServiceNode
from lys.core.registries import register_node


@register_node()
class CheckoutSessionNode(ServiceNode[StripeSyncService]):
    """Result of creating a Stripe checkout session."""
    success: bool
    checkout_url: Optional[str] = None
    error: Optional[str] = None


@register_node()
class BillingPortalNode(ServiceNode[StripeSyncService]):
    """Result of creating a Stripe billing portal session."""
    success: bool
    portal_url: Optional[str] = None
    error: Optional[str] = None