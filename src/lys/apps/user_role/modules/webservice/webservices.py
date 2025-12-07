"""
Webservice queries for user_role app.

Extends base WebserviceQuery to add role-based filtering.
"""

from typing import Annotated

import strawberry
from sqlalchemy import Select

from lys.apps.base.modules.webservice.nodes import AccessedWebserviceNode
from lys.core.contexts import Info
from lys.core.graphql.connection import lys_connection
from lys.core.graphql.registries import register_query
from lys.core.graphql.types import Query


@register_query()
@strawberry.type
class RoleWebserviceQuery(Query):
    @lys_connection(
        ensure_type=AccessedWebserviceNode,
        is_public=True,
        is_licenced=False,
        description="Get all accessible webservices by a user. Optionally filter by role code.",
        options={"generate_tool": False},
        allow_override=True
    )
    async def all_accessible_webservices(
        self,
        info: Info,
        role_code: Annotated[
            str | None,
            strawberry.argument(description="Filter webservices assigned to this role code")
        ] = None
    ) -> Select:
        webservice_service = info.context.app_manager.get_service("webservice")
        connected_user = info.context.connected_user
        return await webservice_service.accessible_webservices(connected_user, role_code=role_code)