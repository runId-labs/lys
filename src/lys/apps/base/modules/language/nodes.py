"""
GraphQL nodes for language module.
"""

from lys.apps.base.modules.language.services import LanguageService
from lys.core.graphql.nodes import parametric_node
from lys.core.registers import register_node


@register_node()
@parametric_node(LanguageService)
class LanguageNode:
    """
    GraphQL node for Language entity.

    Automatically includes:
    - id: Language code (fr, en, etc.)
    - enabled: Whether the language is active
    """
    pass