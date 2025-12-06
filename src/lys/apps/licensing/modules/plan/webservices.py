"""
License plan webservices.
"""

import strawberry
from sqlalchemy import Select, select, or_

from lys.apps.licensing.modules.plan.nodes import LicensePlanNode
from lys.core.consts.webservices import CONNECTED_ACCESS_LEVEL
from lys.core.contexts import Info
from lys.core.graphql.connection import lys_connection
from lys.core.graphql.registries import register_query
from lys.core.graphql.types import Query


@strawberry.type
@register_query()
class LicensePlanQuery(Query):
    @lys_connection(
        LicensePlanNode,
        access_levels=[CONNECTED_ACCESS_LEVEL],
        is_licenced=False,
        description="List all active license plans with their current version and pricing.",
        options={"generate_tool": True}
    )
    async def all_active_license_plans(self, info: Info) -> Select:
        """
        Get all active (enabled) license plans available to the connected user.

        Returns:
        - If user has no associated client: only global plans (client_id IS NULL)
        - If user has an associated client: global plans + custom plans for that client
        """
        plan_entity = info.context.app_manager.get_entity("license_plan")
        client_entity = info.context.app_manager.get_entity("client")
        client_user_entity = info.context.app_manager.get_entity("client_user")

        connected_user = info.context.connected_user
        user_id = connected_user["id"]
        session = info.context.session

        # Find user's client_id (owner or member)
        user_client_id = None

        # Check if user is owner of a client
        stmt = select(client_entity.id).where(client_entity.owner_id == user_id)
        result = await session.execute(stmt)
        client_id = result.scalar_one_or_none()

        if client_id:
            user_client_id = client_id
        else:
            # Check if user is member of a client
            stmt = select(client_user_entity.client_id).where(client_user_entity.user_id == user_id)
            result = await session.execute(stmt)
            client_id = result.scalar_one_or_none()
            if client_id:
                user_client_id = client_id

        # Build query based on user's client association
        if user_client_id:
            # User has a client: return global plans + custom plans for their client
            stmt = select(plan_entity).where(
                plan_entity.enabled == True,
                or_(
                    plan_entity.client_id.is_(None),
                    plan_entity.client_id == user_client_id
                )
            ).order_by(plan_entity.id)
        else:
            # User has no client: return only global plans
            stmt = select(plan_entity).where(
                plan_entity.enabled == True,
                plan_entity.client_id.is_(None)
            ).order_by(plan_entity.id)

        return stmt