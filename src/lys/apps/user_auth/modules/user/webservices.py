import strawberry
from sqlalchemy import Select, select

from lys.apps.user_auth.modules.user.nodes import UserNode, UserStatusNode
from lys.apps.user_auth.modules.user.services import UserStatusService
from lys.core.consts.webservices import OWNER_ACCESS_LEVEL
from lys.core.contexts import Info
from lys.core.graphql.connection import lys_connection
from lys.core.graphql.getter import lys_getter
from lys.core.graphql.registers import register_query
from lys.core.graphql.types import Query


@register_query("graphql")
@strawberry.type
class UserQuery(Query):
    @lys_getter(
        UserNode,
        is_public=False,
        access_levels=[OWNER_ACCESS_LEVEL],
        is_licenced=False,
        description="Return user information."
    )
    async def user(self):
        pass


@register_query("graphql")
@strawberry.type
class UserStatusQuery(Query):
    @lys_connection(
        UserStatusNode,
        is_public=True,
        is_licenced=False,
        description="Return all possible user statuses."
    )
    async def all_user_statuses(self, info: Info, enabled: bool | None = None) -> Select:
        service_class: type[UserStatusService] | None = info.context.service_class
        entity_type = service_class.get_entity_by_name("user_status")
        stmt = select(entity_type).order_by(entity_type.id.asc())
        if enabled is not None:
            stmt = stmt.where(entity_type.enabled == enabled)
        return stmt