import strawberry
from sqlalchemy import Select, select

from lys.apps.user_role.consts import ROLE_ACCESS_LEVEL
from lys.apps.user_role.modules.role.nodes import RoleNode
from lys.core.contexts import Info
from lys.core.graphql.connection import lys_connection
from lys.core.graphql.registers import register_query
from lys.core.graphql.types import Query


@register_query()
@strawberry.type
class RoleQuery(Query):
    @lys_connection(
        ensure_type=RoleNode,
        is_public=False,
        access_levels=[ROLE_ACCESS_LEVEL],
        is_licenced=False,
        description="Return all roles."
    )
    async def all_roles(self, info: Info, enabled: bool | None = None) -> Select:
        entity_type = info.context.service_class.entity_class
        stmt = select(entity_type).order_by(entity_type.id.asc())
        if enabled is not None:
            stmt = stmt.where(entity_type.enabled == enabled)
        return stmt