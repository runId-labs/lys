"""
GraphQL nodes for stored file module.
"""
from datetime import datetime
from typing import Optional

import strawberry
from strawberry import relay

from lys.apps.file_management.modules.stored_file.entities import StoredFile
from lys.apps.file_management.modules.stored_file.services import StoredFileService
from lys.core.graphql.nodes import EntityNode, ServiceNode
from lys.core.registries import register_node


@register_node()
class StoredFileNode(EntityNode[StoredFileService], relay.Node):
    """GraphQL node for StoredFile entity."""
    id: relay.NodeID[str]
    original_name: str
    size: int
    mime_type: str
    type_id: str
    created_at: datetime
    updated_at: Optional[datetime]
    _entity: strawberry.Private[StoredFile]


@register_node()
class PresignedUploadUrlNode(ServiceNode[StoredFileService]):
    """Response node containing presigned URL and object key for direct upload."""
    presigned_url: str
    object_key: str