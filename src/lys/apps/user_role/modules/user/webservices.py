import strawberry

from lys.apps.user_auth.modules.user.nodes import UserNode
from lys.apps.user_role.consts import ROLE_ACCESS_LEVEL
from lys.core.consts.webservices import OWNER_ACCESS_LEVEL
from lys.core.graphql.getter import lys_getter
from lys.core.graphql.registers import register_query
from lys.core.graphql.types import Query


@register_query("graphql")
@strawberry.type
class UserQuery(Query):
    @lys_getter(
        UserNode,
        is_public=False,
        access_levels=[OWNER_ACCESS_LEVEL, ROLE_ACCESS_LEVEL],
        is_licenced=False,
        allow_override=True,
        description="Return user information."
    )
    async def user(self):
        pass