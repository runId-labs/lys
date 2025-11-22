import strawberry
from sqlalchemy import Select, select

from lys.apps.base.modules.webservice.nodes import WebserviceNode
from lys.apps.base.modules.webservice.services import WebserviceService
from lys.core.contexts import Info
from lys.core.graphql.connection import lys_connection
from lys.core.graphql.registers import register_query
from lys.core.graphql.types import Query


@register_query()
@strawberry.type
class WebserviceQuery(Query):
    @lys_connection(
        ensure_type=WebserviceNode,
        is_public=True,
        is_licenced=False,
        description="Get all accessible webservices by a user (connected or not) based on their roles.",
        options={"generate_tool": False}
    )
    async def all_accessible_webservices(self, info: Info) -> Select:
        webservice_service = info.context.app_manager.get_service("webservice")
        connected_user = info.context.connected_user
        return await webservice_service.accessible_webservices(connected_user)

    @lys_connection(
        ensure_type=WebserviceNode,
        is_licenced=False,
        description="Get all webservices (super admin only).",
        options={"generate_tool": False}
    )
    async def all_webservices(self, info: Info) -> Select:
        webservice_service = info.context.app_manager.get_service("webservice")
        entity_type = webservice_service.entity_class
        stmt = select(entity_type).order_by(entity_type.id.asc())
        return stmt
