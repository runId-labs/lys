"""
Unit tests for AI Conversation services.

Tests AIConversationService, AIMessageService, and AIMessageFeedbackService
using mocks to avoid database dependencies.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch, PropertyMock
from datetime import datetime, UTC

from lys.apps.ai.modules.conversation.consts import (
    AIMessageRole,
    AIFeedbackRating,
    AI_PURPOSE_CHATBOT,
)


# Note: _build_messages tests are in integration tests because they require
# real SQLAlchemy entities for select() statements


class TestAIConversationServiceGetOrCreate:
    """Tests for get_or_create method."""

    @pytest.fixture
    def mock_app_manager(self):
        """Create mock app_manager."""
        return MagicMock()

    @pytest.fixture
    def mock_session(self):
        """Create mock async session."""
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_get_or_create_with_existing_conversation(self, mock_app_manager, mock_session):
        """Test getting existing conversation."""
        from lys.apps.ai.modules.conversation.services import AIConversationService

        existing_conv = MagicMock()
        existing_conv.user_id = "user-123"

        with patch.object(AIConversationService, "get_by_id", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = existing_conv

            result = await AIConversationService.get_or_create(
                user_id="user-123",
                session=mock_session,
                conversation_id="conv-123"
            )

        assert result == existing_conv
        mock_get.assert_called_once_with("conv-123", mock_session)

    @pytest.mark.asyncio
    async def test_get_or_create_creates_new_when_not_found(self, mock_app_manager, mock_session):
        """Test creating new conversation when not found."""
        from lys.apps.ai.modules.conversation.services import AIConversationService

        new_conv = MagicMock()

        with patch.object(AIConversationService, "get_by_id", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None

            with patch.object(AIConversationService, "create", new_callable=AsyncMock) as mock_create:
                mock_create.return_value = new_conv

                result = await AIConversationService.get_or_create(
                    user_id="user-123",
                    session=mock_session,
                    conversation_id="nonexistent"
                )

        assert result == new_conv
        mock_create.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_or_create_without_conversation_id(self, mock_app_manager, mock_session):
        """Test creating new conversation when no ID provided."""
        from lys.apps.ai.modules.conversation.services import AIConversationService

        new_conv = MagicMock()

        with patch.object(AIConversationService, "create", new_callable=AsyncMock) as mock_create:
            mock_create.return_value = new_conv

            result = await AIConversationService.get_or_create(
                user_id="user-123",
                session=mock_session,
                conversation_id=None
            )

        assert result == new_conv
        mock_create.assert_called_once_with(
            mock_session,
            user_id="user-123",
            purpose=AI_PURPOSE_CHATBOT,
        )

    @pytest.mark.asyncio
    async def test_get_or_create_wrong_user_creates_new(self, mock_app_manager, mock_session):
        """Test that wrong user's conversation triggers new creation."""
        from lys.apps.ai.modules.conversation.services import AIConversationService

        existing_conv = MagicMock()
        existing_conv.user_id = "other-user"  # Different user

        new_conv = MagicMock()

        with patch.object(AIConversationService, "get_by_id", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = existing_conv

            with patch.object(AIConversationService, "create", new_callable=AsyncMock) as mock_create:
                mock_create.return_value = new_conv

                result = await AIConversationService.get_or_create(
                    user_id="user-123",
                    session=mock_session,
                    conversation_id="conv-123"
                )

        assert result == new_conv


class TestAIConversationServiceArchive:
    """Tests for archive method."""

    @pytest.mark.asyncio
    async def test_archive_conversation(self):
        """Test archiving a conversation."""
        from lys.apps.ai.modules.conversation.services import AIConversationService

        mock_session = AsyncMock()
        updated_conv = MagicMock()

        with patch.object(AIConversationService, "update", new_callable=AsyncMock) as mock_update:
            mock_update.return_value = updated_conv

            result = await AIConversationService.archive("conv-123", mock_session)

        assert result is True
        mock_update.assert_called_once()
        call_args = mock_update.call_args
        assert call_args[0][0] == "conv-123"
        assert call_args[0][1] == mock_session
        assert "archived_at" in call_args[1]

    @pytest.mark.asyncio
    async def test_archive_nonexistent_conversation(self):
        """Test archiving a nonexistent conversation returns False."""
        from lys.apps.ai.modules.conversation.services import AIConversationService

        mock_session = AsyncMock()

        with patch.object(AIConversationService, "update", new_callable=AsyncMock) as mock_update:
            mock_update.return_value = None

            result = await AIConversationService.archive("nonexistent", mock_session)

        assert result is False


class TestAIMessageServiceAddToolResult:
    """Tests for AIMessageService.add_tool_result method."""

    @pytest.mark.asyncio
    async def test_add_tool_result(self):
        """Test adding a tool result message."""
        from lys.apps.ai.modules.conversation.services import AIMessageService

        mock_session = AsyncMock()
        mock_message = MagicMock()

        with patch.object(AIMessageService, "create", new_callable=AsyncMock) as mock_create:
            mock_create.return_value = mock_message

            result = await AIMessageService.add_tool_result(
                conversation_id="conv-123",
                tool_call_id="call-456",
                result={"data": "test result"},
                session=mock_session
            )

        assert result == mock_message
        mock_create.assert_called_once_with(
            mock_session,
            conversation_id="conv-123",
            role=AIMessageRole.TOOL.value,
            tool_call_id="call-456",
            tool_result={"data": "test result"},
        )


class TestAIMessageFeedbackServiceRateMessage:
    """Tests for AIMessageFeedbackService.rate_message method."""

    @pytest.fixture
    def mock_session(self):
        """Create mock async session."""
        session = AsyncMock()
        session.flush = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_rate_message_new_feedback(self, mock_session):
        """Test rating a message creates new feedback."""
        from lys.apps.ai.modules.conversation.services import AIMessageFeedbackService

        mock_feedback = MagicMock()

        with patch.object(
            AIMessageFeedbackService,
            "_get_or_create_feedback",
            new_callable=AsyncMock
        ) as mock_get_create:
            mock_get_create.return_value = mock_feedback

            result = await AIMessageFeedbackService.rate_message(
                message_id="msg-123",
                user_id="user-123",
                rating=AIFeedbackRating.THUMBS_UP,
                session=mock_session,
                comment="Great response!"
            )

        assert result == mock_feedback
        assert mock_feedback.rating == AIFeedbackRating.THUMBS_UP.value
        assert mock_feedback.comment == "Great response!"
        mock_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_rate_message_without_comment(self, mock_session):
        """Test rating without comment doesn't override existing comment."""
        from lys.apps.ai.modules.conversation.services import AIMessageFeedbackService

        mock_feedback = MagicMock()
        mock_feedback.comment = "Existing comment"

        with patch.object(
            AIMessageFeedbackService,
            "_get_or_create_feedback",
            new_callable=AsyncMock
        ) as mock_get_create:
            mock_get_create.return_value = mock_feedback

            result = await AIMessageFeedbackService.rate_message(
                message_id="msg-123",
                user_id="user-123",
                rating=AIFeedbackRating.THUMBS_DOWN,
                session=mock_session,
                comment=None
            )

        assert mock_feedback.rating == AIFeedbackRating.THUMBS_DOWN.value
        # Comment should not be modified when None is passed
        assert mock_feedback.comment == "Existing comment"


class TestAIMessageFeedbackServiceAddComment:
    """Tests for AIMessageFeedbackService.add_comment method."""

    @pytest.fixture
    def mock_session(self):
        """Create mock async session."""
        session = AsyncMock()
        session.flush = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_add_comment(self, mock_session):
        """Test adding a comment to feedback."""
        from lys.apps.ai.modules.conversation.services import AIMessageFeedbackService

        mock_feedback = MagicMock()

        with patch.object(
            AIMessageFeedbackService,
            "_get_or_create_feedback",
            new_callable=AsyncMock
        ) as mock_get_create:
            mock_get_create.return_value = mock_feedback

            result = await AIMessageFeedbackService.add_comment(
                message_id="msg-123",
                user_id="user-123",
                comment="This was helpful",
                session=mock_session
            )

        assert result == mock_feedback
        assert mock_feedback.comment == "This was helpful"
        mock_session.flush.assert_called_once()


class TestAIConversationServiceBuildSystemPrompt:
    """Tests for _build_system_prompt method."""

    @pytest.fixture
    def mock_session(self):
        """Create mock async session."""
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_build_system_prompt_returns_empty_without_config(self, mock_session):
        """Test building system prompt returns empty without configuration."""
        from lys.apps.ai.modules.conversation.services import AIConversationService

        connected_user = {
            "sub": "user-123",
            "is_super_user": False,
        }
        chatbot_config = {}

        result = await AIConversationService._build_system_prompt(
            mock_session, connected_user, chatbot_config, tools_count=5
        )

        assert result == ""

    @pytest.mark.asyncio
    async def test_build_system_prompt_with_custom_prompt(self, mock_session):
        """Test that custom system prompt is included."""
        from lys.apps.ai.modules.conversation.services import AIConversationService

        connected_user = None
        chatbot_config = {
            "system_prompt": "You are a helpful assistant for ACME Corp."
        }

        result = await AIConversationService._build_system_prompt(
            mock_session, connected_user, chatbot_config, tools_count=0
        )

        assert "ACME Corp" in result

    @pytest.mark.asyncio
    async def test_build_system_prompt_with_page_behaviour(self, mock_session):
        """Test that page-specific prompt is included."""
        from lys.apps.ai.modules.conversation.services import AIConversationService

        connected_user = None
        chatbot_config = {}
        page_behaviour = {
            "prompt": "Focus on helping with customer support tasks."
        }

        result = await AIConversationService._build_system_prompt(
            mock_session, connected_user, chatbot_config, tools_count=0,
            page_behaviour=page_behaviour
        )

        assert "customer support" in result

    @pytest.mark.asyncio
    async def test_build_system_prompt_with_context_data(self, mock_session):
        """Test that context data is included."""
        from lys.apps.ai.modules.conversation.services import AIConversationService

        connected_user = None
        chatbot_config = {}
        context_data = {
            "Current Order": "Order #12345 - Status: Pending"
        }

        result = await AIConversationService._build_system_prompt(
            mock_session, connected_user, chatbot_config, tools_count=0,
            context_data=context_data
        )

        assert "Contexte dynamique" in result
        assert "Current Order" in result
        assert "Order #12345" in result
