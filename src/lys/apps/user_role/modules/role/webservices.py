from typing import Annotated

import strawberry
from sqlalchemy import Select

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
        options={"generate_tool": True},
        description=(
            "The roles a user can be given, each with its code and a description of what it allows. "
            "Read it to explain a role or to advise which roles fit a person. Read-only: assigning "
            "roles is the administrator's act, never yours. Filters: enabled (true = roles that can "
            "be assigned today), supervisor_only (true = internal-team roles, false = roles for an "
            "organization's users). Internal-team roles are hidden from an organization's members."
        ),
    )
    async def all_roles(
        self,
        info: Info,
        enabled: Annotated[
            bool | None,
            strawberry.argument(description="Filter by enabled status: true=active roles, false=disabled roles")
        ] = None,
        supervisor_only: Annotated[
            bool | None,
            strawberry.argument(
                description="Filter by supervisor_only: true=supervisor-only roles, "
                            "false=roles assignable to client users"
            )
        ] = None
    ) -> Select:
        role_service = info.context.app_manager.get_service("role")
        return await role_service.visible_roles_statement(
            info.context.session,
            info.context.connected_user,
            enabled=enabled,
            supervisor_only=supervisor_only
        )
