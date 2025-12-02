"""
Subscription webservices for licensing app.
"""

import strawberry

from lys.apps.licensing.modules.subscription.entities import Subscription
from lys.apps.licensing.modules.subscription.nodes import SubscriptionNode
from lys.apps.organization.consts import ORGANIZATION_ROLE_ACCESS_LEVEL
from lys.apps.user_role.consts import ROLE_ACCESS_LEVEL
from lys.core.contexts import Info
from lys.core.graphql.getter import lys_getter
from lys.core.graphql.registries import register_query
from lys.core.graphql.types import Query


@strawberry.type
@register_query()
class SubscriptionQuery(Query):
    @lys_getter(
        SubscriptionNode,
        is_public=False,
        access_levels=[ROLE_ACCESS_LEVEL, ORGANIZATION_ROLE_ACCESS_LEVEL],
        is_licenced=False,
        description="Get a specific subscription by ID. Accessible to license administrators.",
        options={"generate_tool": True}
    )
    async def subscription(self, obj: Subscription, info: Info):
        pass