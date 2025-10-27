import strawberry
from sqlalchemy import Select

from lys.apps.base.modules.webservice.nodes import WebserviceNode
from lys.apps.base.modules.webservice.services import WebserviceService
from lys.core.contexts import Info
from lys.core.graphql.connection import lys_connection
from lys.core.graphql.registers import register_query
from lys.core.graphql.types import Query


@register_query("graphql")
@strawberry.type
class WebserviceQuery(Query):
    @lys_connection(
        ensure_type=WebserviceNode,
        is_public=True,
        is_licenced=False,
        description="Get all accessible webservices by a user (connected or not) corresponding by his roles, "
                    "the list can be filtered by module."
    )
    async def all_accessible_webservices(self, info: Info) -> Select:
        webservice_service: type[WebserviceService] | None = info.context.service_class
        connected_user = info.context.connected_user
        return await webservice_service.accessible_webservices(connected_user)
