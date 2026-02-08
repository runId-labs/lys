"""
Integration tests for AI MessageFeedbackService.

Tests cover:
- Rating a message (create + update)
- Adding a comment
"""

import pytest
from uuid import uuid4

from lys.apps.ai.modules.conversation.consts import AIFeedbackRating, AIMessageRole


class TestAIMessageFeedbackService:
    """Test AIMessageFeedbackService operations."""

    @pytest.mark.asyncio
    async def test_rate_message_creates_feedback(self, ai_app_manager):
        """Test rating a message creates a new feedback entry."""
        conversation_service = ai_app_manager.get_service("ai_conversations")
        message_service = ai_app_manager.get_service("ai_messages")
        feedback_service = ai_app_manager.get_service("ai_message_feedback")
        user_id = str(uuid4())

        async with ai_app_manager.database.get_session() as session:
            conversation = await conversation_service.get_or_create(user_id, session)
            message = await message_service.create(
                session,
                conversation_id=conversation.id,
                role=AIMessageRole.ASSISTANT.value,
                content="Test response"
            )

            feedback = await feedback_service.rate_message(
                message_id=message.id,
                user_id=user_id,
                rating=AIFeedbackRating.THUMBS_UP,
                session=session
            )

            assert feedback.message_id == message.id
            assert feedback.user_id == user_id
            assert feedback.rating == "thumbs_up"

    @pytest.mark.asyncio
    async def test_rate_message_updates_existing(self, ai_app_manager):
        """Test rating a message again updates the existing feedback."""
        conversation_service = ai_app_manager.get_service("ai_conversations")
        message_service = ai_app_manager.get_service("ai_messages")
        feedback_service = ai_app_manager.get_service("ai_message_feedback")
        user_id = str(uuid4())

        async with ai_app_manager.database.get_session() as session:
            conversation = await conversation_service.get_or_create(user_id, session)
            message = await message_service.create(
                session,
                conversation_id=conversation.id,
                role=AIMessageRole.ASSISTANT.value,
                content="Test response for update"
            )

            # First rating
            feedback1 = await feedback_service.rate_message(
                message_id=message.id,
                user_id=user_id,
                rating=AIFeedbackRating.THUMBS_UP,
                session=session
            )

            # Update rating
            feedback2 = await feedback_service.rate_message(
                message_id=message.id,
                user_id=user_id,
                rating=AIFeedbackRating.THUMBS_DOWN,
                session=session
            )

            assert feedback2.id == feedback1.id
            assert feedback2.rating == "thumbs_down"

    @pytest.mark.asyncio
    async def test_add_comment_creates_feedback(self, ai_app_manager):
        """Test adding a comment creates feedback if none exists."""
        conversation_service = ai_app_manager.get_service("ai_conversations")
        message_service = ai_app_manager.get_service("ai_messages")
        feedback_service = ai_app_manager.get_service("ai_message_feedback")
        user_id = str(uuid4())

        async with ai_app_manager.database.get_session() as session:
            conversation = await conversation_service.get_or_create(user_id, session)
            message = await message_service.create(
                session,
                conversation_id=conversation.id,
                role=AIMessageRole.ASSISTANT.value,
                content="Response to comment on"
            )

            feedback = await feedback_service.add_comment(
                message_id=message.id,
                user_id=user_id,
                comment="This was very helpful!",
                session=session
            )

            assert feedback.comment == "This was very helpful!"
            assert feedback.rating is None  # No rating set

    @pytest.mark.asyncio
    async def test_add_comment_to_existing_feedback(self, ai_app_manager):
        """Test adding a comment to an existing feedback with a rating."""
        conversation_service = ai_app_manager.get_service("ai_conversations")
        message_service = ai_app_manager.get_service("ai_messages")
        feedback_service = ai_app_manager.get_service("ai_message_feedback")
        user_id = str(uuid4())

        async with ai_app_manager.database.get_session() as session:
            conversation = await conversation_service.get_or_create(user_id, session)
            message = await message_service.create(
                session,
                conversation_id=conversation.id,
                role=AIMessageRole.ASSISTANT.value,
                content="Response with rating and comment"
            )

            # Rate first
            await feedback_service.rate_message(
                message_id=message.id,
                user_id=user_id,
                rating=AIFeedbackRating.THUMBS_UP,
                session=session
            )

            # Then add comment
            feedback = await feedback_service.add_comment(
                message_id=message.id,
                user_id=user_id,
                comment="Great answer!",
                session=session
            )

            assert feedback.rating == "thumbs_up"
            assert feedback.comment == "Great answer!"
