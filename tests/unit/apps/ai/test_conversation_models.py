"""
Unit tests for AI conversation Pydantic models.

Tests input validation and model structure.
"""

import pytest
from pydantic import ValidationError


class TestAIMessageInputModel:
    """Tests for AIMessageInputModel."""

    def test_model_exists(self):
        """Test AIMessageInputModel exists."""
        from lys.apps.ai.modules.conversation.models import AIMessageInputModel
        assert AIMessageInputModel is not None

    def test_model_inherits_from_base_model(self):
        """Test AIMessageInputModel inherits from BaseModel."""
        from lys.apps.ai.modules.conversation.models import AIMessageInputModel
        from pydantic import BaseModel
        assert issubclass(AIMessageInputModel, BaseModel)

    def test_model_has_message_field(self):
        """Test model has message field."""
        from lys.apps.ai.modules.conversation.models import AIMessageInputModel
        assert "message" in AIMessageInputModel.model_fields

    def test_model_has_conversation_id_field(self):
        """Test model has conversation_id field."""
        from lys.apps.ai.modules.conversation.models import AIMessageInputModel
        assert "conversation_id" in AIMessageInputModel.model_fields

    def test_model_accepts_valid_data(self):
        """Test model accepts valid data."""
        from lys.apps.ai.modules.conversation.models import AIMessageInputModel

        model = AIMessageInputModel(message="Hello, AI!")
        assert model.message == "Hello, AI!"
        assert model.conversation_id is None

    def test_model_accepts_conversation_id(self):
        """Test model accepts a conversation GlobalID and stores the raw id."""
        from lys.apps.ai.modules.conversation.models import AIMessageInputModel
        from lys.core.graphql.client import build_global_id

        raw_id = "550e8400-e29b-41d4-a716-446655440000"
        model = AIMessageInputModel(
            message="Hello",
            conversation_id=build_global_id("AIConversationNode", raw_id),
        )
        assert model.message == "Hello"
        assert model.conversation_id == raw_id

    def test_model_rejects_non_global_id_conversation_id(self):
        """A plain string that isn't a GlobalID must be refused, not silently accepted."""
        from lys.apps.ai.modules.conversation.models import AIMessageInputModel

        with pytest.raises(ValidationError):
            AIMessageInputModel(message="Hello", conversation_id="conv-123")

    def test_model_requires_message(self):
        """Test message field is required."""
        from lys.apps.ai.modules.conversation.models import AIMessageInputModel

        with pytest.raises(ValidationError):
            AIMessageInputModel(conversation_id="conv-123")

    def test_conversation_id_is_optional(self):
        """Test conversation_id field is optional."""
        from lys.apps.ai.modules.conversation.models import AIMessageInputModel

        model = AIMessageInputModel(message="Test")
        assert model.conversation_id is None


class TestAIToolResultModel:
    """Tests for AIToolResultModel."""

    def test_model_exists(self):
        """Test AIToolResultModel exists."""
        from lys.apps.ai.modules.conversation.models import AIToolResultModel
        assert AIToolResultModel is not None

    def test_model_inherits_from_base_model(self):
        """Test AIToolResultModel inherits from BaseModel."""
        from lys.apps.ai.modules.conversation.models import AIToolResultModel
        from pydantic import BaseModel
        assert issubclass(AIToolResultModel, BaseModel)

    def test_model_has_tool_name_field(self):
        """Test model has tool_name field."""
        from lys.apps.ai.modules.conversation.models import AIToolResultModel
        assert "tool_name" in AIToolResultModel.model_fields

    def test_model_has_result_field(self):
        """Test model has result field."""
        from lys.apps.ai.modules.conversation.models import AIToolResultModel
        assert "result" in AIToolResultModel.model_fields

    def test_model_has_success_field(self):
        """Test model has success field."""
        from lys.apps.ai.modules.conversation.models import AIToolResultModel
        assert "success" in AIToolResultModel.model_fields

    def test_model_accepts_valid_data(self):
        """Test model accepts valid data."""
        from lys.apps.ai.modules.conversation.models import AIToolResultModel

        model = AIToolResultModel(
            tool_name="get_weather",
            result="Sunny, 25C",
            success=True
        )
        assert model.tool_name == "get_weather"
        assert model.result == "Sunny, 25C"
        assert model.success is True

    def test_model_requires_all_fields(self):
        """Test all fields are required."""
        from lys.apps.ai.modules.conversation.models import AIToolResultModel

        with pytest.raises(ValidationError):
            AIToolResultModel(tool_name="test")

        with pytest.raises(ValidationError):
            AIToolResultModel(tool_name="test", result="ok")


class TestExtractConversationId:
    """Tests for extract_conversation_id."""

    def test_extracts_raw_id_from_global_id(self):
        from lys.apps.ai.modules.conversation.models import extract_conversation_id
        from lys.core.graphql.client import build_global_id

        raw_id = "550e8400-e29b-41d4-a716-446655440000"
        global_id = build_global_id("AIConversationNode", raw_id)

        assert extract_conversation_id(global_id) == raw_id

    def test_rejects_plain_string(self):
        from lys.apps.ai.modules.conversation.models import extract_conversation_id

        with pytest.raises(ValueError, match="Invalid conversation ID format"):
            extract_conversation_id("conv-123")

    def test_rejects_global_id_not_carrying_a_uuid(self):
        """A well-formed GlobalID whose id part isn't a UUID must still be refused."""
        from lys.apps.ai.modules.conversation.models import extract_conversation_id
        from lys.core.graphql.client import build_global_id

        global_id = build_global_id("AIConversationNode", "not-a-uuid")

        with pytest.raises(ValueError, match="Invalid conversation ID format"):
            extract_conversation_id(global_id)

    def test_rejects_malformed_base64(self):
        from lys.apps.ai.modules.conversation.models import extract_conversation_id

        with pytest.raises(ValueError, match="Invalid conversation ID format"):
            extract_conversation_id("not-valid-base64!!!")


class TestUpdateAIConversationTitleInputModel:
    """Tests for UpdateAIConversationTitleInputModel."""

    def test_accepts_valid_title(self):
        from lys.apps.ai.modules.conversation.models import UpdateAIConversationTitleInputModel

        model = UpdateAIConversationTitleInputModel(title="Budget review")
        assert model.title == "Budget review"

    def test_strips_surrounding_whitespace(self):
        from lys.apps.ai.modules.conversation.models import UpdateAIConversationTitleInputModel

        model = UpdateAIConversationTitleInputModel(title="  Budget review  ")
        assert model.title == "Budget review"

    def test_rejects_blank_title(self):
        from lys.apps.ai.modules.conversation.models import UpdateAIConversationTitleInputModel

        with pytest.raises(ValidationError):
            UpdateAIConversationTitleInputModel(title="   ")

    def test_rejects_empty_title(self):
        from lys.apps.ai.modules.conversation.models import UpdateAIConversationTitleInputModel

        with pytest.raises(ValidationError):
            UpdateAIConversationTitleInputModel(title="")

    def test_rejects_title_over_max_length(self):
        from lys.apps.ai.modules.conversation.models import UpdateAIConversationTitleInputModel
        from lys.apps.ai.modules.conversation.consts import DISPLAY_TITLE_MAX_LENGTH

        with pytest.raises(ValidationError):
            UpdateAIConversationTitleInputModel(title="x" * (DISPLAY_TITLE_MAX_LENGTH + 1))
