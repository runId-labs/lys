"""
GraphQL webservices for file import module.
"""
from typing import Optional

import strawberry
from sqlalchemy import select, func, Select
from strawberry import relay

from lys.apps.file_management.modules.file_import.consts import (
    FILE_IMPORT_STATUS_PENDING,
    FILE_IMPORT_STATUS_PROCESSING,
)
from lys.apps.file_management.modules.file_import.nodes import (
    ActiveFileImportsCountNode,
    FileImportNode,
)
from lys.apps.organization.consts import ORGANIZATION_ROLE_ACCESS_LEVEL
from lys.apps.user_role.consts import ROLE_ACCESS_LEVEL
from lys.core.consts.permissions import ORGANIZATION_ROLE_ACCESS_KEY
from lys.core.contexts import Info
from lys.core.graphql.connection import lys_connection
from lys.core.graphql.fields import lys_field
from lys.core.graphql.registries import register_query
from lys.core.graphql.types import Query


@strawberry.type
@register_query()
class FileImportQuery(Query):
    """GraphQL queries for file imports."""

    @lys_connection(
        FileImportNode,
        is_public=False,
        access_levels=[ROLE_ACCESS_LEVEL, ORGANIZATION_ROLE_ACCESS_LEVEL],
        is_licenced=False,
        description="List all file imports with optional filters, ordered by creation date (newest first)."
    )
    async def all_file_imports(
        self,
        info: Info,
        client_id: Optional[relay.GlobalID] = None,
        status_id: Optional[str] = None,
        type_id: Optional[str] = None,
    ) -> Select:
        file_import_entity = info.context.app_manager.get_entity("file_import")

        stmt = select(file_import_entity).order_by(file_import_entity.created_at.desc())

        if client_id:
            stmt = stmt.where(file_import_entity.client_id == client_id.node_id)
        if status_id:
            stmt = stmt.where(file_import_entity.status_id == status_id)
        if type_id:
            stmt = stmt.where(file_import_entity.type_id == type_id)

        return stmt

    @lys_field(
        ensure_type=ActiveFileImportsCountNode,
        is_public=False,
        access_levels=[ROLE_ACCESS_LEVEL, ORGANIZATION_ROLE_ACCESS_LEVEL],
        is_licenced=False,
        description="Get the count of active file imports (PENDING or PROCESSING)."
    )
    async def active_file_imports_count(self, info: Info) -> ActiveFileImportsCountNode:
        file_import_entity = info.context.app_manager.get_entity("file_import")
        session = info.context.session

        stmt = select(func.count(file_import_entity.id)).where(
            file_import_entity.status_id.in_([
                FILE_IMPORT_STATUS_PENDING,
                FILE_IMPORT_STATUS_PROCESSING,
            ])
        )

        # Apply organization access filters from JWT claims
        access_type = info.context.access_type
        if isinstance(access_type, dict):
            org_dict = access_type.get(ORGANIZATION_ROLE_ACCESS_KEY, {})
            if org_dict:
                stmt, conditions = file_import_entity.organization_accessing_filters(
                    stmt, org_dict
                )
                for condition in conditions:
                    stmt = stmt.where(condition)

        result = await session.execute(stmt)
        count = result.scalar() or 0

        return ActiveFileImportsCountNode(active_count=count)
