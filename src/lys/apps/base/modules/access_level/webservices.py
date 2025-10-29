import strawberry
from sqlalchemy import select, Select

from lys.apps.base.modules.access_level.nodes import AccessLevelNode
from lys.core.consts.webservices import CONNECTED_ACCESS_LEVEL
from lys.core.contexts import Info
from lys.core.graphql.connection import lys_connection
from lys.core.graphql.registers import register_query
from lys.core.graphql.types import Query


@register_query("graphql")
@strawberry.type
class AccessLevelQuery(Query):
    @lys_connection(
        ensure_type=AccessLevelNode,
        is_public=True,
        is_licenced=False,
        description="Return possible access levels."
    )
    async def all_access_levels(self, info: Info, enabled: bool | None = None) -> Select:
        entity_type = info.context.service_class.entity_class
        stmt = select(entity_type).order_by(entity_type.id.asc())
        if enabled is not None:
            stmt = stmt.where(entity_type.enabled == enabled)
        return stmt
