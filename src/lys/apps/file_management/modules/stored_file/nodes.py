"""
GraphQL nodes for stored file module.
"""
from lys.apps.file_management.modules.stored_file.services import StoredFileService
from lys.core.graphql.nodes import ServiceNode
from lys.core.registries import register_node


@register_node()
class PresignedUploadUrlNode(ServiceNode[StoredFileService]):
    """Response node containing presigned URL and object key for direct upload."""
    presigned_url: str
    object_key: str