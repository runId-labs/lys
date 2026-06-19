"""
Integration tests for AI ConversationService.

Tests cover database-only operations:
- get_or_create (new, existing, wrong user)
- archive
- _build_messages (empty, with user/assistant, with tool calls)
"""

from datetime import datetime, timedelta, UTC
from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlalchemy import select

from lys.apps.ai.modules.conversation.consts import AI_PURPOSE_CHATBOT, AIMessageRole


class TestAIConversationServiceGetOrCreate:
    """Test AIConversationService.get_or_create."""

    @pytest.mark.asyncio
    async def test_get_or_create_new_conversation(self, ai_app_manager):
        """Test creating a new conversation when none exists."""
        conversation_service = ai_app_manager.get_service("ai_conversation")
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
        conversation_service = ai_app_manager.get_service("ai_conversation")
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
        conversation_service = ai_app_manager.get_service("ai_conversation")
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
        conversation_service = ai_app_manager.get_service("ai_conversation")
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
        conversation_service = ai_app_manager.get_service("ai_conversation")
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
        conversation_service = ai_app_manager.get_service("ai_conversation")

        async with ai_app_manager.database.get_session() as session:
            result = await conversation_service.archive(str(uuid4()), session)
            assert result is False


# ==============================================================================
# Phase 1A: _build_messages tests
# ==============================================================================


class TestAIConversationServiceBuildMessages:
    """Test AIConversationService._build_messages."""

    @pytest.mark.asyncio
    async def test_build_messages_empty_conversation(self, ai_app_manager):
        """Test _build_messages returns empty list for new conversation."""
        conversation_service = ai_app_manager.get_service("ai_conversation")
        user_id = str(uuid4())

        async with ai_app_manager.database.get_session() as session:
            conversation = await conversation_service.get_or_create(user_id, session)
            messages = await conversation_service._build_messages(conversation, session)
            assert messages == []

    @pytest.mark.asyncio
    async def test_build_messages_with_user_and_assistant(self, ai_app_manager):
        """Test _build_messages includes user and assistant messages in order."""
        conversation_service = ai_app_manager.get_service("ai_conversation")
        message_entity = ai_app_manager.get_entity("ai_message")
        user_id = str(uuid4())

        async with ai_app_manager.database.get_session() as session:
            conversation = await conversation_service.get_or_create(user_id, session)

            # Add user message
            user_msg = message_entity(
                conversation_id=conversation.id,
                role=AIMessageRole.USER.value,
                content="Hello"
            )
            session.add(user_msg)

            # Add assistant message
            assistant_msg = message_entity(
                conversation_id=conversation.id,
                role=AIMessageRole.ASSISTANT.value,
                content="Hi there!"
            )
            session.add(assistant_msg)
            await session.flush()

            messages = await conversation_service._build_messages(conversation, session)

            assert len(messages) == 2
            assert messages[0]["role"] == "user"
            assert messages[0]["content"] == "Hello"
            assert messages[1]["role"] == "assistant"
            assert messages[1]["content"] == "Hi there!"

    @pytest.mark.asyncio
    async def test_build_messages_with_tool_calls(self, ai_app_manager):
        """Test _build_messages correctly handles tool call messages."""
        conversation_service = ai_app_manager.get_service("ai_conversation")
        message_entity = ai_app_manager.get_entity("ai_message")
        user_id = str(uuid4())

        async with ai_app_manager.database.get_session() as session:
            conversation = await conversation_service.get_or_create(user_id, session)

            # Add assistant message with tool_calls
            assistant_msg = message_entity(
                conversation_id=conversation.id,
                role=AIMessageRole.ASSISTANT.value,
                content="Let me check that.",
                tool_calls=[{"id": "call_1", "function": {"name": "get_weather"}}]
            )
            session.add(assistant_msg)

            # Add tool result message
            tool_msg = message_entity(
                conversation_id=conversation.id,
                role=AIMessageRole.TOOL.value,
                tool_result={"temperature": 22},
                tool_call_id="call_1"
            )
            session.add(tool_msg)
            await session.flush()

            messages = await conversation_service._build_messages(conversation, session)

            assert len(messages) == 2
            # Assistant with tool_calls should include tool_calls
            assert messages[0]["role"] == "assistant"
            assert "tool_calls" in messages[0]
            # Tool message should include tool_call_id
            assert messages[1]["role"] == "tool"
            assert messages[1]["tool_call_id"] == "call_1"


# ==============================================================================
# Conversation compaction (summaries) — DB-backed paths
# ==============================================================================


class TestAIConversationServiceCompaction:
    """Test compaction read/window/enqueue paths that build SQL over real columns."""

    @staticmethod
    def _alternating_role(i):
        return AIMessageRole.USER.value if i % 2 == 0 else AIMessageRole.ASSISTANT.value

    @pytest.mark.asyncio
    async def test_load_current_summary_returns_latest_completed_ignoring_pending(self, ai_app_manager):
        """_load_current_summary picks the most recent completed row, skipping pending ones."""
        conversation_service = ai_app_manager.get_service("ai_conversation")
        summary_entity = ai_app_manager.get_entity("ai_conversation_summary")
        message_entity = ai_app_manager.get_entity("ai_message")
        user_id = str(uuid4())

        async with ai_app_manager.database.get_session() as session:
            conv = await conversation_service.get_or_create(user_id, session)
            boundary = message_entity(
                conversation_id=conv.id, role=AIMessageRole.USER.value, content="b"
            )
            session.add(boundary)
            await session.flush()

            base = datetime(2026, 1, 1, tzinfo=UTC)
            session.add_all([
                summary_entity(conversation_id=conv.id, through_message_id=boundary.id,
                               summary="old", completed=True, created_at=base),
                summary_entity(conversation_id=conv.id, through_message_id=boundary.id,
                               summary="latest", completed=True, created_at=base + timedelta(minutes=5)),
                summary_entity(conversation_id=conv.id, through_message_id=boundary.id,
                               summary=None, completed=False, created_at=base + timedelta(minutes=10)),
            ])
            await session.flush()

            current = await conversation_service._load_current_summary(conv.id, session)
            assert current is not None
            assert current.summary == "latest"

    @pytest.mark.asyncio
    async def test_load_current_summary_none_when_only_pending(self, ai_app_manager):
        conversation_service = ai_app_manager.get_service("ai_conversation")
        summary_entity = ai_app_manager.get_entity("ai_conversation_summary")
        message_entity = ai_app_manager.get_entity("ai_message")
        user_id = str(uuid4())

        async with ai_app_manager.database.get_session() as session:
            conv = await conversation_service.get_or_create(user_id, session)
            boundary = message_entity(
                conversation_id=conv.id, role=AIMessageRole.USER.value, content="b"
            )
            session.add(boundary)
            await session.flush()
            session.add(summary_entity(
                conversation_id=conv.id, through_message_id=boundary.id,
                summary=None, completed=False,
            ))
            await session.flush()

            assert await conversation_service._load_current_summary(conv.id, session) is None

    @pytest.mark.asyncio
    async def test_build_messages_returns_only_window_after_boundary(self, ai_app_manager):
        """With a current summary, only messages strictly after its boundary are returned."""
        conversation_service = ai_app_manager.get_service("ai_conversation")
        summary_entity = ai_app_manager.get_entity("ai_conversation_summary")
        message_entity = ai_app_manager.get_entity("ai_message")
        user_id = str(uuid4())

        async with ai_app_manager.database.get_session() as session:
            conv = await conversation_service.get_or_create(user_id, session)
            base = datetime(2026, 1, 1, tzinfo=UTC)
            msgs = []
            for i in range(6):
                m = message_entity(
                    conversation_id=conv.id, role=self._alternating_role(i),
                    content=f"m{i}", created_at=base + timedelta(minutes=i),
                )
                session.add(m)
                msgs.append(m)
            await session.flush()

            summary = summary_entity(
                conversation_id=conv.id, through_message_id=msgs[2].id,
                summary="...", completed=True, created_at=base + timedelta(hours=1),
            )
            session.add(summary)
            await session.flush()

            built = await conversation_service._build_messages(conv, session, current_summary=summary)
            assert [b["content"] for b in built] == ["m3", "m4", "m5"]

    @pytest.mark.asyncio
    async def test_maybe_enqueue_compaction_creates_pending_and_dispatches(self, ai_app_manager):
        """Over the token threshold, a pending summary row is created and the task dispatched."""
        conversation_service = ai_app_manager.get_service("ai_conversation")
        summary_entity = ai_app_manager.get_entity("ai_conversation_summary")
        message_entity = ai_app_manager.get_entity("ai_message")
        user_id = str(uuid4())

        async with ai_app_manager.database.get_session() as session:
            conv = await conversation_service.get_or_create(user_id, session)
            base = datetime(2026, 1, 1, tzinfo=UTC)
            for i in range(14):
                session.add(message_entity(
                    conversation_id=conv.id, role=self._alternating_role(i),
                    content=f"m{i}", created_at=base + timedelta(minutes=i),
                ))
            await session.flush()

            with patch(
                "lys.apps.ai.modules.conversation.services.summarize_conversation"
            ) as mock_task:
                # prompt_tokens above the default threshold (120000).
                await conversation_service.maybe_enqueue_compaction(
                    conv, session, {"prompt_tokens": 200000}
                )

            rows = (await session.execute(
                select(summary_entity).where(summary_entity.conversation_id == conv.id)
            )).scalars().all()
            assert len(rows) == 1
            assert rows[0].completed is False
            mock_task.delay.assert_called_once_with(rows[0].id)

    @pytest.mark.asyncio
    async def test_maybe_enqueue_compaction_noop_below_threshold(self, ai_app_manager):
        conversation_service = ai_app_manager.get_service("ai_conversation")
        summary_entity = ai_app_manager.get_entity("ai_conversation_summary")
        message_entity = ai_app_manager.get_entity("ai_message")
        user_id = str(uuid4())

        async with ai_app_manager.database.get_session() as session:
            conv = await conversation_service.get_or_create(user_id, session)
            base = datetime(2026, 1, 1, tzinfo=UTC)
            for i in range(14):
                session.add(message_entity(
                    conversation_id=conv.id, role=self._alternating_role(i),
                    content=f"m{i}", created_at=base + timedelta(minutes=i),
                ))
            await session.flush()

            with patch(
                "lys.apps.ai.modules.conversation.services.summarize_conversation"
            ) as mock_task:
                await conversation_service.maybe_enqueue_compaction(
                    conv, session, {"prompt_tokens": 10}
                )

            rows = (await session.execute(
                select(summary_entity).where(summary_entity.conversation_id == conv.id)
            )).scalars().all()
            assert rows == []
            mock_task.delay.assert_not_called()
