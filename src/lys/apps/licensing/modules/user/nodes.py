"""
GraphQL nodes for licensing user module.
"""

import strawberry
from strawberry.types import Info

from lys.apps.organization.modules.user.nodes import UserNode as OrganizationUserNode
from lys.core.registries import register_node


@register_node()
class UserNode(OrganizationUserNode):
    """
    Extended user node with licensing information.

    Adds, on top of the organization UserNode:
    - is_licensed: Whether the user has a license (is in subscription_user table)

    It overrides the organization UserNode when the licensing app is enabled.
    """

    @strawberry.field(description="Whether this user has a license (is associated with a subscription)")
    async def is_licensed(self, info: Info) -> bool:
        """
        Check if this user has a license.

        A user is considered licensed if they are associated with
        any subscription in the subscription_user table.

        Args:
            info: GraphQL context containing the database session

        Returns:
            bool: True if the user has a license
        """
        subscription_service = info.context.app_manager.get_service("subscription")
        session = info.context.session
        return await subscription_service.is_user_licensed(self._entity.id, session)
