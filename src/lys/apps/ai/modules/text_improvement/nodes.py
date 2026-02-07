"""
AI Text Improvement nodes.

GraphQL node types for text improvement responses.
"""

from lys.core.graphql.nodes import ServiceNode
from lys.core.registries import register_node


@register_node()
class ImprovedTextNode(ServiceNode):
    """Response from text improvement."""

    improved_text: str
    message: str = "Text improved successfully"