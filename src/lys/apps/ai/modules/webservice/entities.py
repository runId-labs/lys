"""
AI Webservice entity extension.

Adds AI-specific fields to the Webservice entity:
- ai_tool: JSON tool definition for LLM function calling
"""

from typing import Optional

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from lys.apps.user_auth.modules.webservice.entities import AuthWebservice
from lys.core.registries import register_entity


@register_entity()
class Webservice(AuthWebservice):
    """Webservice entity with AI tool support."""

    # AI Tool definition for LLM function calling (null = not an AI tool)
    ai_tool: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="AI tool definition for LLM function calling"
    )