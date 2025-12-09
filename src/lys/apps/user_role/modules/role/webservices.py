from typing import Annotated

import strawberry
from sqlalchemy import Select, select

from lys.apps.user_role.modules.role.nodes import RoleNode
from lys.core.consts.webservices import CONNECTED_ACCESS_LEVEL
from lys.core.contexts import Info
from lys.core.graphql.connection import lys_connection
from lys.core.graphql.registries import register_query
from lys.core.graphql.types import Query


@register_query()
@strawberry.type
class RoleQuery(Query):
    @lys_connection(
        ensure_type=RoleNode,
        is_public=False,
        access_levels=[CONNECTED_ACCESS_LEVEL],
        is_licenced=False,
        description="List all available roles for user assignment. Filter by 'enabled' status. Use to get valid role codes.",
        options={"generate_tool": True}
    )
    async def all_roles(
        self,
        info: Info,
        enabled: Annotated[bool | None, strawberry.argument(description="Filter by enabled status: true=active roles, false=disabled roles")] = None
    ) -> Select:
        entity_type = info.context.app_manager.get_entity("role")
        stmt = select(entity_type).order_by(entity_type.id.asc())
        if enabled is not None:
            stmt = stmt.where(entity_type.enabled == enabled)
        return stmt