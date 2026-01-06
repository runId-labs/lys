"""
AI Webservice queries and mutations.

Extends webservice queries with AI-specific filters and mutations with AI tool support.
"""

from typing import List, Optional

import strawberry
from sqlalchemy import Select, select

from lys.apps.ai.modules.webservice.inputs import WebserviceFixturesInput
from lys.apps.ai.modules.webservice.nodes import WebserviceNode
from lys.apps.base.modules.webservice.nodes import RegisterWebservicesNode
from lys.apps.base.modules.webservice.services import WebserviceService
from lys.core.consts.webservices import INTERNAL_SERVICE_ACCESS_LEVEL
from lys.core.contexts import Info
from lys.core.graphql.connection import lys_connection
from lys.core.graphql.fields import lys_field
from lys.core.graphql.registries import register_query, register_mutation
from lys.core.graphql.types import Query, Mutation


@register_query()
@strawberry.type
class WebserviceQuery(Query):
    @lys_connection(
        ensure_type=WebserviceNode,
        access_levels=[INTERNAL_SERVICE_ACCESS_LEVEL],
        is_licenced=False,
        description="Get all webservices with optional filters.",
        options={"generate_tool": False},
        allow_override=True,
    )
    async def all_webservices(
        self,
        info: Info,
        is_ai_tool: Optional[bool] = None,
        enabled: Optional[bool] = None,
        app_name: Optional[str] = None,
    ) -> Select:
        webservice_service = info.context.app_manager.get_service("webservice")
        entity_type = webservice_service.entity_class

        stmt = select(entity_type).order_by(entity_type.id.asc())

        # Filter by AI tool status
        if is_ai_tool is True:
            stmt = stmt.where(entity_type.ai_tool.isnot(None))
        elif is_ai_tool is False:
            stmt = stmt.where(entity_type.ai_tool.is_(None))

        # Filter by enabled status
        if enabled is not None:
            stmt = stmt.where(entity_type.enabled == enabled)

        # Filter by app_name
        if app_name is not None:
            stmt = stmt.where(entity_type.app_name == app_name)

        return stmt


@register_mutation()
@strawberry.type
class WebserviceMutation(Mutation):
    @lys_field(
        ensure_type=RegisterWebservicesNode,
        access_levels=[INTERNAL_SERVICE_ACCESS_LEVEL],
        is_licenced=False,
        description="Register webservices from a business microservice with AI tool support.",
        options={"generate_tool": False},
        allow_override=True,
    )
    async def register_webservices(
        self,
        info: Info,
        webservices: List[WebserviceFixturesInput]
    ) -> RegisterWebservicesNode:
        """
        Register webservices from a business microservice with AI tool support.

        This mutation extends the base register_webservices to support AI tool
        definitions in the webservice configuration.

        Args:
            info: GraphQL context
            webservices: List of webservice configurations including AI tools

        Returns:
            RegisterWebservicesNode with success status and count
        """
        node = RegisterWebservicesNode.get_effective_node()
        webservice_service: type[WebserviceService] = node.service_class
        session = info.context.session

        # Get app_name from service caller context (set by ServiceAuthMiddleware)
        service_caller = info.context.service_caller
        app_name = service_caller.get("service_name") if service_caller else None

        registered_count = await webservice_service.register_webservices(
            webservices=[ws.to_pydantic() for ws in webservices],
            app_name=app_name,
            session=session
        )

        return node(
            success=True,
            registered_count=registered_count
        )