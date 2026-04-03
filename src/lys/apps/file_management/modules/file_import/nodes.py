"""
GraphQL nodes for file import module.
"""
from datetime import datetime
from typing import Optional

import strawberry
from strawberry import relay
from strawberry.types import Info

from lys.apps.file_management.modules.file_import.entities import FileImport
from lys.apps.file_management.modules.file_import.services import (
    FileImportService,
    FileImportStatusService,
    FileImportTypeService,
)
from lys.apps.file_management.modules.stored_file.nodes import StoredFileNode
from lys.core.graphql.nodes import EntityNode, ServiceNode
from lys.core.registries import register_node


@register_node()
class FileImportTypeNode(EntityNode[FileImportTypeService], relay.Node):
    """GraphQL node for FileImportType parametric entity."""
    id: relay.NodeID[str]
    enabled: bool
    description: Optional[str]


@register_node()
class FileImportStatusNode(EntityNode[FileImportStatusService], relay.Node):
    """GraphQL node for FileImportStatus parametric entity."""
    id: relay.NodeID[str]
    enabled: bool
    description: Optional[str]


@register_node()
class FileImportNode(EntityNode[FileImportService], relay.Node):
    """GraphQL node for FileImport entity."""
    id: relay.NodeID[str]
    client_id: str
    status_id: str
    type_id: str
    total_rows: Optional[int]
    processed_rows: Optional[int]
    success_rows: Optional[int]
    error_rows: Optional[int]
    extra_data: Optional[strawberry.scalars.JSON]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime
    updated_at: Optional[datetime]
    _entity: strawberry.Private[FileImport]

    @strawberry.field(description="The uploaded file metadata")
    async def stored_file(self, info: Info) -> Optional[StoredFileNode]:
        return await self._lazy_load_relation("stored_file", StoredFileNode, info)

    @strawberry.field(description="Import type (e.g. DSN_FINANCIAL_IMPORT, FEC_IMPORT)")
    async def type(self, info: Info) -> Optional[FileImportTypeNode]:
        return await self._lazy_load_relation("type", FileImportTypeNode, info)

    @strawberry.field(description="Import status (PENDING, PROCESSING, COMPLETED, FAILED)")
    async def status(self, info: Info) -> Optional[FileImportStatusNode]:
        return await self._lazy_load_relation("status", FileImportStatusNode, info)


@register_node()
class ActiveFileImportsCountNode(ServiceNode[FileImportService]):
    """Node for active file imports count query (badge display)."""
    active_count: int
