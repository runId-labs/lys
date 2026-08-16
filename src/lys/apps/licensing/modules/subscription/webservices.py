"""
Subscription webservices for licensing app.
"""

import strawberry

from lys.apps.licensing.modules.subscription.entities import Subscription
from lys.apps.licensing.modules.subscription.inputs import SubscribeManuallyInput
from lys.apps.licensing.modules.subscription.nodes import SubscriptionNode
from lys.apps.organization.consts import ORGANIZATION_ROLE_ACCESS_LEVEL
from lys.apps.user_role.consts import ROLE_ACCESS_LEVEL
from lys.core.contexts import Info
from lys.core.graphql.edit import lys_edition
from lys.core.graphql.getter import lys_getter
from lys.core.graphql.registries import register_mutation, register_query
from lys.core.graphql.types import Mutation, Query


@strawberry.type
@register_query()
class SubscriptionQuery(Query):
    @lys_getter(
        SubscriptionNode,
        is_public=False,
        access_levels=[ROLE_ACCESS_LEVEL, ORGANIZATION_ROLE_ACCESS_LEVEL],
        is_licenced=False,
        description="Get a specific subscription by ID. Accessible to license administrators."
    )
    async def subscription(self, obj: Subscription, info: Info):
        pass

@strawberry.type
@register_mutation()
class ManualSubscriptionMutation(Mutation):
    """
    Subscription management for collection handled outside the application.

    These are commercial acts performed by a licensing administrator on behalf
    of a client, never by the client themselves: unlike the checkout mutations,
    they grant a paid plan without taking any payment. They are therefore
    restricted to the licensing administrator role, and deliberately not opened
    to organization roles.
    """

    @lys_edition(
        ensure_type=SubscriptionNode,
        is_public=False,
        access_levels=[ROLE_ACCESS_LEVEL],
        is_licenced=False,
        description="Place a subscription on a plan billed outside the application"
    )
    async def subscribe_client_manually(
        self,
        obj: Subscription,
        input: SubscribeManuallyInput,
        info: Info
    ):
        """
        Place a subscription on a plan collected by other means.

        No payment is taken and no provider is called. The subscription still
        records the exact price agreed to, so entitlements, commitment and
        renewal behave as they do under provider billing.

        Args:
            obj: The subscription, resolved and permission-checked by the decorator
            input: Price agreed to
            info: GraphQL context
        """
        data = input.to_pydantic()
        subscription_service = info.context.app_manager.get_service("subscription")

        await subscription_service.subscribe_manually(
            subscription=obj,
            plan_version_price_id=data.plan_version_price_id,
            session=info.context.session
        )

    @lys_edition(
        ensure_type=SubscriptionNode,
        is_public=False,
        access_levels=[ROLE_ACCESS_LEVEL],
        is_licenced=False,
        description="Change how a subscription is collected"
    )
    async def set_subscription_billing_mode(
        self,
        obj: Subscription,
        billing_mode_id: str,
        info: Info
    ):
        """
        Change how a subscription is collected.

        This is the migration path between the two modes: an application
        adopting a payment provider releases its manually billed clients one by
        one, so that they can subscribe through checkout.

        Args:
            obj: The subscription, resolved and permission-checked by the decorator
            billing_mode_id: Target billing mode
            info: GraphQL context
        """
        subscription_service = info.context.app_manager.get_service("subscription")

        await subscription_service.set_billing_mode(
            subscription=obj,
            billing_mode_id=billing_mode_id,
            session=info.context.session
        )
