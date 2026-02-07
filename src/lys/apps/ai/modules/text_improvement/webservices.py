"""
AI Text Improvement webservices.

GraphQL mutations for text improvement.
"""

import strawberry

from lys.apps.ai.modules.text_improvement.inputs import ImproveTextInput
from lys.apps.ai.modules.text_improvement.nodes import ImprovedTextNode
from lys.core.consts.webservices import CONNECTED_ACCESS_LEVEL
from lys.core.contexts import Info
from lys.core.graphql.fields import lys_field
from lys.core.graphql.registries import register_mutation
from lys.core.graphql.types import Mutation


@register_mutation()
@strawberry.type
class TextImprovementMutation(Mutation):
    """Mutation class for text improvement operations."""

    @lys_field(
        ensure_type=ImprovedTextNode,
        is_public=False,
        access_levels=[CONNECTED_ACCESS_LEVEL],
        is_licenced=False,
        description="Improve text using AI (fix spelling, clarify, keep meaning).",
        options={"generate_tool": False}
    )
    async def improve_text(
        self,
        inputs: ImproveTextInput,
        info: Info
    ) -> ImprovedTextNode:
        """
        Improve text using AI.

        Args:
            inputs: Input containing the text to improve and options
            info: GraphQL context

        Returns:
            ImprovedTextNode with the improved text
        """
        input_data = inputs.to_pydantic()

        text_improvement_service = info.context.app_manager.get_service("text_improvement")
        improved_text = await text_improvement_service.improve(
            text=input_data.text,
            language=input_data.language,
            context=input_data.context,
            max_length=input_data.max_length,
        )

        return ImprovedTextNode(improved_text=improved_text)