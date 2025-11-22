"""
GraphQL webservices for language module.
"""

import strawberry
from sqlalchemy import Select, select

from lys.apps.base.modules.language.nodes import LanguageNode
from lys.apps.base.modules.language.services import LanguageService
from lys.core.contexts import Info
from lys.core.graphql.connection import lys_connection
from lys.core.graphql.registers import register_query
from lys.core.graphql.types import Query


@register_query()
@strawberry.type
class LanguageQuery(Query):
    """
    GraphQL queries for languages.
    """

    @lys_connection(
        LanguageNode,
        is_public=True,
        is_licenced=False,
        description="List all supported languages. Filter by 'enabled' status. Use to get valid language codes for user settings.",
        options={"generate_tool": True}
    )
    async def all_languages(self, info: Info, enabled: bool | None = None) -> Select:
        """
        Query all languages with optional filtering by enabled status.

        Args:
            info: GraphQL context
            enabled: Optional filter for enabled languages

        Returns:
            SQLAlchemy Select statement
        """
        entity_type = info.context.app_manager.get_entity("language")
        stmt = select(entity_type).order_by(entity_type.id.asc())

        if enabled is not None:
            stmt = stmt.where(entity_type.enabled == enabled)

        return stmt