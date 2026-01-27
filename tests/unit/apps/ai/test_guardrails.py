"""
Unit tests for AI Guardrails.

Tests the AIGuardrailService which provides safety middleware for AI tool execution,
including confirmation requirements for risky operations (CREATE, UPDATE, DELETE).
"""

import pytest
from datetime import datetime, timedelta, UTC
from unittest.mock import MagicMock, AsyncMock, patch

from lys.apps.ai.utils.guardrails import (
    AIGuardrailService,
    CONFIRMATION_REQUIRED_LEVELS,
    CONFIRM_ACTION_TOOL,
    _pending_actions,
)
from lys.core.consts.ai import ToolRiskLevel


class TestAIGuardrailServiceProcessToolCall:
    """Tests for process_tool_call method."""

    @pytest.fixture(autouse=True)
    def clear_pending_actions(self):
        """Clear pending actions before and after each test."""
        _pending_actions.clear()
        yield
        _pending_actions.clear()

    @pytest.fixture
    def mock_info(self):
        """Create mock GraphQL info context."""
        info = MagicMock()
        info.context.connected_user = {"sub": "user-123"}
        return info

    @pytest.mark.asyncio
    async def test_safe_operation_returns_execute(self, mock_info):
        """Test that READ operations return execute status immediately."""
        tool_data = {"risk_level": ToolRiskLevel.READ}
        tool_args = {"id": "123"}

        result = await AIGuardrailService.process_tool_call(
            tool_name="get_user",
            tool_data=tool_data,
            tool_args=tool_args,
            info=mock_info
        )

        assert result["status"] == "execute"
        assert result["tool_args"] == tool_args

    @pytest.mark.asyncio
    async def test_no_risk_level_defaults_to_safe(self, mock_info):
        """Test that missing risk_level defaults to READ (safe)."""
        tool_data = {}  # No risk_level
        tool_args = {"name": "test"}

        result = await AIGuardrailService.process_tool_call(
            tool_name="some_tool",
            tool_data=tool_data,
            tool_args=tool_args,
            info=mock_info
        )

        assert result["status"] == "execute"

    @pytest.mark.asyncio
    async def test_create_operation_requires_confirmation(self, mock_info):
        """Test that CREATE operations require confirmation."""
        tool_data = {"risk_level": ToolRiskLevel.CREATE}
        tool_args = {"name": "new item"}

        result = await AIGuardrailService.process_tool_call(
            tool_name="create_item",
            tool_data=tool_data,
            tool_args=tool_args,
            info=mock_info
        )

        assert result["status"] == "confirmation_required"
        assert "action_id" in result
        assert "preview" in result
        assert "message" in result
        assert "create_item" in result["message"]

    @pytest.mark.asyncio
    async def test_update_operation_requires_confirmation(self, mock_info):
        """Test that UPDATE operations require confirmation."""
        tool_data = {"risk_level": ToolRiskLevel.UPDATE}
        tool_args = {"id": "123", "name": "updated"}

        result = await AIGuardrailService.process_tool_call(
            tool_name="update_item",
            tool_data=tool_data,
            tool_args=tool_args,
            info=mock_info
        )

        assert result["status"] == "confirmation_required"
        assert "action_id" in result

    @pytest.mark.asyncio
    async def test_delete_operation_requires_confirmation(self, mock_info):
        """Test that DELETE operations require confirmation."""
        tool_data = {"risk_level": ToolRiskLevel.DELETE}
        tool_args = {"id": "123"}

        result = await AIGuardrailService.process_tool_call(
            tool_name="delete_item",
            tool_data=tool_data,
            tool_args=tool_args,
            info=mock_info
        )

        assert result["status"] == "confirmation_required"
        assert "irreversible" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_pending_action_stored_correctly(self, mock_info):
        """Test that pending action is stored with correct data."""
        tool_data = {"risk_level": ToolRiskLevel.UPDATE}
        tool_args = {"id": "123", "name": "updated"}

        result = await AIGuardrailService.process_tool_call(
            tool_name="update_item",
            tool_data=tool_data,
            tool_args=tool_args,
            info=mock_info
        )

        action_id = result["action_id"]
        assert action_id in _pending_actions

        stored = _pending_actions[action_id]
        assert stored["tool_name"] == "update_item"
        assert stored["tool_args"] == tool_args
        assert stored["user_id"] == "user-123"
        assert "created_at" in stored
        assert "expires_at" in stored


class TestAIGuardrailServiceConfirmAction:
    """Tests for confirm_action method."""

    @pytest.fixture(autouse=True)
    def clear_pending_actions(self):
        """Clear pending actions before and after each test."""
        _pending_actions.clear()
        yield
        _pending_actions.clear()

    @pytest.fixture
    def mock_info(self):
        """Create mock GraphQL info context."""
        info = MagicMock()
        info.context.connected_user = {"sub": "user-123"}
        return info

    @pytest.fixture
    def pending_action(self):
        """Create a pending action for testing."""
        action_id = "test-action-123"
        _pending_actions[action_id] = {
            "tool_name": "update_item",
            "tool_data": {"risk_level": ToolRiskLevel.UPDATE},
            "tool_args": {"id": "123", "name": "updated"},
            "user_id": "user-123",
            "created_at": datetime.now(UTC),
            "expires_at": datetime.now(UTC) + timedelta(minutes=5),
            "preview": {"changes": {"name": "updated"}}
        }
        return action_id

    @pytest.mark.asyncio
    async def test_confirm_action_success(self, mock_info, pending_action):
        """Test confirming an action returns execute status."""
        result = await AIGuardrailService.confirm_action(
            action_id=pending_action,
            confirmed=True,
            info=mock_info
        )

        assert result["status"] == "execute"
        assert result["tool_name"] == "update_item"
        assert result["tool_args"] == {"id": "123", "name": "updated"}
        assert pending_action not in _pending_actions

    @pytest.mark.asyncio
    async def test_cancel_action(self, mock_info, pending_action):
        """Test cancelling an action."""
        result = await AIGuardrailService.confirm_action(
            action_id=pending_action,
            confirmed=False,
            info=mock_info
        )

        assert result["status"] == "cancelled"
        assert pending_action not in _pending_actions

    @pytest.mark.asyncio
    async def test_action_not_found(self, mock_info):
        """Test error when action ID is not found."""
        result = await AIGuardrailService.confirm_action(
            action_id="nonexistent-action",
            confirmed=True,
            info=mock_info
        )

        assert result["status"] == "error"
        assert "not found" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_action_expired(self, mock_info):
        """Test error when action has expired."""
        action_id = "expired-action"
        _pending_actions[action_id] = {
            "tool_name": "update_item",
            "tool_data": {},
            "tool_args": {},
            "user_id": "user-123",
            "created_at": datetime.now(UTC) - timedelta(minutes=10),
            "expires_at": datetime.now(UTC) - timedelta(minutes=5),  # Expired
            "preview": {}
        }

        result = await AIGuardrailService.confirm_action(
            action_id=action_id,
            confirmed=True,
            info=mock_info
        )

        assert result["status"] == "error"
        assert "expired" in result["message"].lower()
        assert action_id not in _pending_actions

    @pytest.mark.asyncio
    async def test_wrong_user_cannot_confirm(self, pending_action):
        """Test that another user cannot confirm someone else's action."""
        info = MagicMock()
        info.context.connected_user = {"sub": "different-user"}

        result = await AIGuardrailService.confirm_action(
            action_id=pending_action,
            confirmed=True,
            info=info
        )

        assert result["status"] == "error"
        assert "unauthorized" in result["message"].lower()


class TestAIGuardrailServiceHelpers:
    """Tests for helper methods."""

    def test_get_nested_value_simple(self):
        """Test getting a simple nested value."""
        obj = {"name": "test"}
        result = AIGuardrailService._get_nested_value(obj, "name")
        assert result == "test"

    def test_get_nested_value_deep(self):
        """Test getting a deeply nested value."""
        obj = {"client": {"organization": {"name": "Test Corp"}}}
        result = AIGuardrailService._get_nested_value(obj, "client.organization.name")
        assert result == "Test Corp"

    def test_get_nested_value_missing(self):
        """Test getting a missing nested value returns None."""
        obj = {"name": "test"}
        result = AIGuardrailService._get_nested_value(obj, "nonexistent.path")
        assert result is None

    def test_get_nested_value_partial_path(self):
        """Test getting value when partial path exists."""
        obj = {"client": {"name": "test"}}
        result = AIGuardrailService._get_nested_value(obj, "client.organization.name")
        assert result is None

    def test_get_confirmation_message_create(self):
        """Test confirmation message for CREATE operations."""
        message = AIGuardrailService._get_confirmation_message(
            ToolRiskLevel.CREATE, "create_user"
        )
        assert "confirm" in message.lower()
        assert "creation" in message.lower()
        assert "create_user" in message

    def test_get_confirmation_message_update(self):
        """Test confirmation message for UPDATE operations."""
        message = AIGuardrailService._get_confirmation_message(
            ToolRiskLevel.UPDATE, "update_user"
        )
        assert "confirm" in message.lower()
        assert "modification" in message.lower()

    def test_get_confirmation_message_delete(self):
        """Test confirmation message for DELETE operations."""
        message = AIGuardrailService._get_confirmation_message(
            ToolRiskLevel.DELETE, "delete_user"
        )
        assert "confirm" in message.lower()
        assert "deletion" in message.lower()
        assert "irreversible" in message.lower()


class TestConfirmActionTool:
    """Tests for the CONFIRM_ACTION_TOOL definition."""

    def test_tool_definition_structure(self):
        """Test that CONFIRM_ACTION_TOOL has correct structure."""
        assert CONFIRM_ACTION_TOOL["type"] == "function"
        assert "function" in CONFIRM_ACTION_TOOL

        func = CONFIRM_ACTION_TOOL["function"]
        assert func["name"] == "confirm_action"
        assert "description" in func
        assert "parameters" in func

    def test_tool_parameters(self):
        """Test that tool parameters are correct."""
        params = CONFIRM_ACTION_TOOL["function"]["parameters"]
        assert params["type"] == "object"
        assert "action_id" in params["properties"]
        assert "confirmed" in params["properties"]
        assert params["properties"]["action_id"]["type"] == "string"
        assert params["properties"]["confirmed"]["type"] == "boolean"
        assert set(params["required"]) == {"action_id", "confirmed"}


class TestConfirmationRequiredLevels:
    """Tests for CONFIRMATION_REQUIRED_LEVELS constant."""

    def test_read_not_in_confirmation_required(self):
        """Test that READ is not in confirmation required levels."""
        assert ToolRiskLevel.READ not in CONFIRMATION_REQUIRED_LEVELS

    def test_create_in_confirmation_required(self):
        """Test that CREATE is in confirmation required levels."""
        assert ToolRiskLevel.CREATE in CONFIRMATION_REQUIRED_LEVELS

    def test_update_in_confirmation_required(self):
        """Test that UPDATE is in confirmation required levels."""
        assert ToolRiskLevel.UPDATE in CONFIRMATION_REQUIRED_LEVELS

    def test_delete_in_confirmation_required(self):
        """Test that DELETE is in confirmation required levels."""
        assert ToolRiskLevel.DELETE in CONFIRMATION_REQUIRED_LEVELS
