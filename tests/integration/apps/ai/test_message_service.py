"""
Integration tests for AI MessageService.

Tests cover:
- Creating messages with different roles
- Tool result messages
- Message ordering
"""

import pytest
from uuid import uuid4

from sqlalchemy import select

from lys.apps.ai.modules.conversation.consts import AIMessageRole


class TestAIMessageService:
    """Test AIMessageService operations."""

    @pytest.mark.asyncio
    async def test_create_user_message(self, ai_app_manager):
        """Test creating a user message."""
        conversation_service = ai_app_manager.get_service("ai_conversations")
        message_service = ai_app_manager.get_service("ai_messages")
        user_id = str(uuid4())

        async with ai_app_manager.database.get_session() as session:
            conversation = await conversation_service.get_or_create(user_id, session)

            message = await message_service.create(
                session,
                conversation_id=conversation.id,
                role=AIMessageRole.USER.value,
                content="Hello, how are you?"
            )

            assert message.id is not None
            assert message.role == "user"
            assert message.content == "Hello, how are you?"
            assert message.conversation_id == conversation.id

    @pytest.mark.asyncio
    async def test_create_assistant_message_with_metrics(self, ai_app_manager):
        """Test creating an assistant message with token metrics."""
        conversation_service = ai_app_manager.get_service("ai_conversations")
        message_service = ai_app_manager.get_service("ai_messages")
        user_id = str(uuid4())

        async with ai_app_manager.database.get_session() as session:
            conversation = await conversation_service.get_or_create(user_id, session)

            message = await message_service.create(
                session,
                conversation_id=conversation.id,
                role=AIMessageRole.ASSISTANT.value,
                content="I am doing well!",
                provider="anthropic",
                model="claude-3",
                tokens_in=50,
                tokens_out=20,
                latency_ms=350
            )

            assert message.role == "assistant"
            assert message.provider == "anthropic"
            assert message.model == "claude-3"
            assert message.tokens_in == 50
            assert message.tokens_out == 20
            assert message.latency_ms == 350

    @pytest.mark.asyncio
    async def test_add_tool_result(self, ai_app_manager):
        """Test adding a tool result message."""
        conversation_service = ai_app_manager.get_service("ai_conversations")
        message_service = ai_app_manager.get_service("ai_messages")
        user_id = str(uuid4())

        async with ai_app_manager.database.get_session() as session:
            conversation = await conversation_service.get_or_create(user_id, session)

            tool_result = await message_service.add_tool_result(
                conversation_id=conversation.id,
                tool_call_id="call_abc123",
                result={"data": [1, 2, 3], "count": 3},
                session=session
            )

            assert tool_result.role == "tool"
            assert tool_result.tool_call_id == "call_abc123"
            assert tool_result.tool_result == {"data": [1, 2, 3], "count": 3}

    @pytest.mark.asyncio
    async def test_messages_ordered_by_created_at(self, ai_app_manager):
        """Test that conversation messages are ordered by creation time."""
        conversation_service = ai_app_manager.get_service("ai_conversations")
        message_service = ai_app_manager.get_service("ai_messages")
        user_id = str(uuid4())

        async with ai_app_manager.database.get_session() as session:
            conversation = await conversation_service.get_or_create(user_id, session)

            msg1 = await message_service.create(
                session,
                conversation_id=conversation.id,
                role=AIMessageRole.USER.value,
                content="First message"
            )
            msg2 = await message_service.create(
                session,
                conversation_id=conversation.id,
                role=AIMessageRole.ASSISTANT.value,
                content="Second message"
            )
            msg3 = await message_service.create(
                session,
                conversation_id=conversation.id,
                role=AIMessageRole.USER.value,
                content="Third message"
            )

        async with ai_app_manager.database.get_session() as session:
            message_entity = ai_app_manager.get_entity("ai_messages")
            stmt = (
                select(message_entity)
                .where(message_entity.conversation_id == conversation.id)
                .order_by(message_entity.created_at)
            )
            result = await session.execute(stmt)
            messages = list(result.scalars().all())

            assert len(messages) == 3
            assert messages[0].content == "First message"
            assert messages[1].content == "Second message"
            assert messages[2].content == "Third message"
