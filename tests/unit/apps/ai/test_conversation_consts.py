"""
Unit tests for AI Conversation constants.
"""

import pytest

from lys.apps.ai.modules.conversation.consts import (
    AI_PURPOSE_CHATBOT,
    AIMessageRole,
    AIFeedbackRating,
)


class TestAIPurposeConstants:
    """Tests for AI purpose constants."""

    def test_chatbot_purpose_value(self):
        """Test that chatbot purpose has expected value."""
        assert AI_PURPOSE_CHATBOT == "chatbot"


class TestAIMessageRole:
    """Tests for AIMessageRole enum."""

    def test_system_role(self):
        """Test SYSTEM role value."""
        assert AIMessageRole.SYSTEM.value == "system"

    def test_user_role(self):
        """Test USER role value."""
        assert AIMessageRole.USER.value == "user"

    def test_assistant_role(self):
        """Test ASSISTANT role value."""
        assert AIMessageRole.ASSISTANT.value == "assistant"

    def test_tool_role(self):
        """Test TOOL role value."""
        assert AIMessageRole.TOOL.value == "tool"

    def test_role_is_string_enum(self):
        """Test that roles can be used as strings."""
        assert AIMessageRole.USER.value == "user"
        assert AIMessageRole.ASSISTANT.value == "assistant"
        # String enum comparison
        assert AIMessageRole.USER == AIMessageRole.USER

    def test_all_roles_defined(self):
        """Test that all expected roles are defined."""
        roles = {role.value for role in AIMessageRole}
        expected = {"system", "user", "assistant", "tool"}
        assert roles == expected


class TestAIFeedbackRating:
    """Tests for AIFeedbackRating enum."""

    def test_thumbs_up_value(self):
        """Test THUMBS_UP rating value."""
        assert AIFeedbackRating.THUMBS_UP.value == "thumbs_up"

    def test_thumbs_down_value(self):
        """Test THUMBS_DOWN rating value."""
        assert AIFeedbackRating.THUMBS_DOWN.value == "thumbs_down"

    def test_rating_is_string_enum(self):
        """Test that ratings can be used as strings."""
        assert AIFeedbackRating.THUMBS_UP == "thumbs_up"

    def test_all_ratings_defined(self):
        """Test that all expected ratings are defined."""
        ratings = {rating.value for rating in AIFeedbackRating}
        expected = {"thumbs_up", "thumbs_down"}
        assert ratings == expected
