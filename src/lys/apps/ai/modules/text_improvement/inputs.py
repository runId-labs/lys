"""
AI Text Improvement inputs.

GraphQL input types for text improvement mutations.
"""

import strawberry

from lys.apps.ai.modules.text_improvement.models import ImproveTextInputModel


@strawberry.experimental.pydantic.input(model=ImproveTextInputModel)
class ImproveTextInput:
    """Input for improving text with AI."""

    text: strawberry.auto
    context: strawberry.auto
    language: strawberry.auto
    max_length: strawberry.auto