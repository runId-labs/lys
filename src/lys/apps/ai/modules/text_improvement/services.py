"""
AI Text Improvement services.

Service for improving text using AI.
"""

from typing import Optional

from lys.apps.ai.modules.text_improvement.consts import TEXT_IMPROVEMENT_SYSTEM_PROMPT
from lys.core.registries import register_service
from lys.core.services import Service


@register_service()
class TextImprovementService(Service):
    """Service for improving text using AI."""

    service_name = "text_improvement"

    @classmethod
    async def improve(
        cls,
        text: str,
        language: str = "fr",
        context: Optional[str] = None,
        max_length: Optional[int] = None,
    ) -> str:
        """
        Improve text using AI.

        Args:
            text: The text to improve
            language: Language of the text (default: "fr")
            context: Optional context hint for the AI
            max_length: Optional max length constraint (will use 90% of this value)

        Returns:
            The improved text
        """
        # Build max length instruction if provided
        max_length_instruction = ""
        if max_length:
            effective_limit = int(max_length * 0.9)
            max_length_instruction = f"- Keep the improved text under {effective_limit} characters"

        # Build system prompt
        system_prompt = TEXT_IMPROVEMENT_SYSTEM_PROMPT.format(
            max_length_instruction=max_length_instruction
        )

        # Build user message
        user_message = f"Improve this text (language: {language}):\n\n{text}"
        if context:
            user_message = f"Context: {context}\n\n{user_message}"

        # Call AI service via app_manager
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]

        ai_service = cls.app_manager.get_service("ai")
        response = await ai_service.chat_with_purpose(messages, "text_improvement")

        return response.content.strip()