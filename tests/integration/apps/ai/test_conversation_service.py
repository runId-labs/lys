"""
Integration tests for AI ConversationService.

Tests cover database-only operations:
- get_or_create (new, existing, wrong user)
- archive
"""

import pytest
from uuid import uuid4

from lys.apps.ai.modules.conversation.consts import AI_PURPOSE_CHATBOT


class TestAIConversationServiceGetOrCreate:
    """Test AIConversationService.get_or_create."""

    @pytest.mark.asyncio
    async def test_get_or_create_new_conversation(self, ai_app_manager):
        """Test creating a new conversation when none exists."""
        conversation_service = ai_app_manager.get_service("ai_conversations")
        user_id = str(uuid4())

        async with ai_app_manager.database.get_session() as session:
            conversation = await conversation_service.get_or_create(user_id, session)

            assert conversation.id is not None
            assert conversation.user_id == user_id
            assert conversation.purpose == AI_PURPOSE_CHATBOT
            assert conversation.archived_at is None

    @pytest.mark.asyncio
    async def test_get_or_create_existing_conversation(self, ai_app_manager):
        """Test retrieving an existing conversation by ID."""
        conversation_service = ai_app_manager.get_service("ai_conversations")
        user_id = str(uuid4())

        async with ai_app_manager.database.get_session() as session:
            created = await conversation_service.get_or_create(user_id, session)

        async with ai_app_manager.database.get_session() as session:
            retrieved = await conversation_service.get_or_create(
                user_id, session, conversation_id=created.id
            )
            assert retrieved.id == created.id

    @pytest.mark.asyncio
    async def test_get_or_create_wrong_user_creates_new(self, ai_app_manager):
        """Test that accessing another user's conversation creates a new one."""
        conversation_service = ai_app_manager.get_service("ai_conversations")
        user_a = str(uuid4())
        user_b = str(uuid4())

        async with ai_app_manager.database.get_session() as session:
            conv_a = await conversation_service.get_or_create(user_a, session)

        async with ai_app_manager.database.get_session() as session:
            conv_b = await conversation_service.get_or_create(
                user_b, session, conversation_id=conv_a.id
            )
            # Should create a new conversation for user_b
            assert conv_b.id != conv_a.id
            assert conv_b.user_id == user_b

    @pytest.mark.asyncio
    async def test_get_or_create_nonexistent_id_creates_new(self, ai_app_manager):
        """Test that a nonexistent conversation_id creates a new conversation."""
        conversation_service = ai_app_manager.get_service("ai_conversations")
        user_id = str(uuid4())

        async with ai_app_manager.database.get_session() as session:
            conversation = await conversation_service.get_or_create(
                user_id, session, conversation_id=str(uuid4())
            )

            assert conversation.id is not None
            assert conversation.user_id == user_id


class TestAIConversationServiceArchive:
    """Test AIConversationService.archive."""

    @pytest.mark.asyncio
    async def test_archive_conversation(self, ai_app_manager):
        """Test archiving a conversation sets archived_at."""
        conversation_service = ai_app_manager.get_service("ai_conversations")
        user_id = str(uuid4())

        async with ai_app_manager.database.get_session() as session:
            conversation = await conversation_service.get_or_create(user_id, session)
            assert conversation.archived_at is None

        async with ai_app_manager.database.get_session() as session:
            result = await conversation_service.archive(conversation.id, session)
            assert result is True

        async with ai_app_manager.database.get_session() as session:
            archived = await conversation_service.get_by_id(conversation.id, session)
            assert archived.archived_at is not None

    @pytest.mark.asyncio
    async def test_archive_nonexistent_conversation(self, ai_app_manager):
        """Test archiving a nonexistent conversation returns False."""
        conversation_service = ai_app_manager.get_service("ai_conversations")

        async with ai_app_manager.database.get_session() as session:
            result = await conversation_service.archive(str(uuid4()), session)
            assert result is False
