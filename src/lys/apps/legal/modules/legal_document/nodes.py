"""
GraphQL nodes for the legal_document module.
"""
from datetime import datetime
from typing import Optional

import strawberry
from strawberry import relay
from strawberry.types import Info

from lys.apps.legal.modules.legal_document.consts import LEGAL_ROUTE_PREFIX
from lys.apps.legal.modules.legal_document.entities import (
    LegalDocumentAcceptance,
    LegalDocumentVersion,
)
from lys.apps.legal.modules.legal_document.services import (
    LegalDocumentAcceptanceService,
    LegalDocumentTypeService,
    LegalDocumentVersionService,
)
from lys.core.graphql.nodes import EntityNode, ServiceNode, parametric_node
from lys.core.registries import register_node


@register_node()
@parametric_node(LegalDocumentTypeService)
class LegalDocumentTypeNode:
    """GraphQL node for LegalDocumentType (parametric): id (code), enabled, description."""
    pass


@register_node()
class LegalDocumentVersionNode(EntityNode[LegalDocumentVersionService], relay.Node):
    """GraphQL node for an immutable legal document version."""
    id: relay.NodeID[str]
    type_id: str
    language_id: str
    version_number: int
    markdown_hash: str
    pdf_hash: str
    effective_date: datetime
    created_at: datetime
    updated_at: Optional[datetime]
    _entity: strawberry.Private[LegalDocumentVersion]

    @strawberry.field(description="Stable public URL of the immutable PDF for this version.")
    def pdf_url(self) -> str:
        return f"/{LEGAL_ROUTE_PREFIX}/versions/{self.id}"


@register_node()
class OutstandingLegalAcceptancesNode(ServiceNode[LegalDocumentAcceptanceService]):
    """Type codes the connected user still owes acceptance for (re-consent gate)."""
    type_ids: list[str]


@register_node()
class LegalDocumentAcceptanceNode(EntityNode[LegalDocumentAcceptanceService], relay.Node):
    """GraphQL node for a consent proof. Owner-scoped read."""
    id: relay.NodeID[str]
    version_id: str
    accepted_by_email: str
    accepted_by_name: Optional[str]
    created_at: datetime
    _entity: strawberry.Private[LegalDocumentAcceptance]

    @strawberry.field(description="The accepted legal document version.")
    async def version(self, info: Info) -> Optional[LegalDocumentVersionNode]:
        return await self._lazy_load_relation("version", LegalDocumentVersionNode, info)
