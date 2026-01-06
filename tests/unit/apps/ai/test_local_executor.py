"""
Unit tests for LocalToolExecutor.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import inspect

import strawberry
from strawberry import relay

from lys.apps.ai.modules.core.executors.local import LocalToolExecutor


class TestLocalToolExecutorInit:
    """Tests for LocalToolExecutor initialization."""

    def test_init_without_app_manager(self):
        """Test initialization without app_manager."""
        executor = LocalToolExecutor()
        assert executor._app_manager is None
        assert executor._tools == []
        assert executor._info is None

    def test_init_with_app_manager(self):
        """Test initialization with app_manager."""
        mock_app_manager = MagicMock()
        executor = LocalToolExecutor(app_manager=mock_app_manager)
        assert executor._app_manager is mock_app_manager

    @pytest.mark.asyncio
    async def test_initialize_stores_tools_and_info(self):
        """Test that initialize stores tools and info."""
        executor = LocalToolExecutor()
        mock_info = MagicMock()
        tools = [{"type": "function", "function": {"name": "test"}}]

        await executor.initialize(tools=tools, info=mock_info)

        assert executor._tools == tools
        assert executor._info is mock_info


class TestLocalToolExecutorConvertArgs:
    """Tests for _convert_tool_args method."""

    @pytest.fixture
    def executor(self):
        return LocalToolExecutor()

    def test_convert_string_to_global_id(self, executor):
        """Test that string is converted to GlobalID when expected."""

        def resolver(id: relay.GlobalID) -> dict:
            pass

        sig = inspect.signature(resolver)

        class UserNode:
            __name__ = "UserNode"

        result = executor._convert_tool_args(
            sig,
            {"id": "123"},
            node_type=UserNode,
        )

        assert isinstance(result["id"], relay.GlobalID)
        assert result["id"].node_id == "123"
        assert result["id"].type_name == "UserNode"

    def test_convert_non_global_id_unchanged(self, executor):
        """Test that non-GlobalID parameters stay unchanged."""

        def resolver(email: str, count: int) -> dict:
            pass

        sig = inspect.signature(resolver)

        result = executor._convert_tool_args(
            sig,
            {"email": "test@example.com", "count": 5},
            node_type=None,
        )

        assert result["email"] == "test@example.com"
        assert result["count"] == 5

    def test_derive_node_type_from_param_name(self, executor):
        """Test that node type is derived from parameter name like 'user_id'."""
        from typing import Optional

        def resolver(user_id: Optional[relay.GlobalID] = None) -> dict:
            pass

        sig = inspect.signature(resolver)

        result = executor._convert_tool_args(
            sig,
            {"user_id": "uuid-123"},
            node_type=None,
        )

        assert isinstance(result["user_id"], relay.GlobalID)
        assert result["user_id"].type_name == "UserNode"

    def test_unknown_param_passed_through(self, executor):
        """Test that unknown parameters are passed through unchanged."""

        def resolver(name: str) -> dict:
            pass

        sig = inspect.signature(resolver)

        result = executor._convert_tool_args(
            sig,
            {"name": "test", "extra_param": "value"},
            node_type=None,
        )

        assert result["extra_param"] == "value"


class TestLocalToolExecutorReconstructInputArgs:
    """Tests for _reconstruct_input_args method."""

    @pytest.fixture
    def executor(self):
        return LocalToolExecutor()

    def test_reconstruct_strawberry_input(self, executor):
        """Test that flattened args are reconstructed into Strawberry input."""

        @strawberry.input
        class UserInput:
            name: str
            email: str

        def resolver(inputs: UserInput) -> dict:
            pass

        sig = inspect.signature(resolver)

        result = executor._reconstruct_input_args(
            sig,
            {"name": "John", "email": "john@example.com"},
        )

        assert "inputs" in result
        assert isinstance(result["inputs"], UserInput)
        assert result["inputs"].name == "John"
        assert result["inputs"].email == "john@example.com"
        # Original flattened args should be removed
        assert "name" not in result
        assert "email" not in result

    def test_no_reconstruction_for_regular_params(self, executor):
        """Test that regular params are not reconstructed."""

        def resolver(name: str, email: str) -> dict:
            pass

        sig = inspect.signature(resolver)

        result = executor._reconstruct_input_args(
            sig,
            {"name": "John", "email": "john@example.com"},
        )

        assert result["name"] == "John"
        assert result["email"] == "john@example.com"

    def test_skip_special_params(self, executor):
        """Test that self, info, obj are skipped."""

        @strawberry.input
        class DataInput:
            value: str

        class MockInfo:
            pass

        def resolver(self, info: MockInfo, data: DataInput) -> dict:
            pass

        sig = inspect.signature(resolver)

        result = executor._reconstruct_input_args(
            sig,
            {"value": "test"},
        )

        assert "data" in result
        assert isinstance(result["data"], DataInput)


class TestLocalToolExecutorSerializeResult:
    """Tests for _serialize_result method."""

    @pytest.fixture
    def executor(self):
        return LocalToolExecutor()

    def test_serialize_none(self, executor):
        """Test that None returns None."""
        assert executor._serialize_result(None) is None

    def test_serialize_datetime(self, executor):
        """Test that datetime is converted to ISO string."""
        from datetime import datetime

        dt = datetime(2024, 1, 15, 10, 30, 0)
        result = executor._serialize_result(dt)
        assert result == "2024-01-15T10:30:00"

    def test_serialize_uuid(self, executor):
        """Test that UUID is converted to string."""
        import uuid

        uid = uuid.UUID("12345678-1234-5678-1234-567812345678")
        result = executor._serialize_result(uid)
        assert result == "12345678-1234-5678-1234-567812345678"

    def test_serialize_list(self, executor):
        """Test that list items are recursively serialized."""
        from datetime import datetime

        data = [datetime(2024, 1, 1), "string", 123]
        result = executor._serialize_result(data)
        assert result[0] == "2024-01-01T00:00:00"
        assert result[1] == "string"
        assert result[2] == 123

    def test_serialize_dict(self, executor):
        """Test that dict values are recursively serialized."""
        from datetime import datetime

        data = {"date": datetime(2024, 1, 1), "value": 123}
        result = executor._serialize_result(data)
        assert result["date"] == "2024-01-01T00:00:00"
        assert result["value"] == 123

    def test_serialize_basic_types(self, executor):
        """Test that basic types are returned as-is."""
        assert executor._serialize_result("string") == "string"
        assert executor._serialize_result(123) == 123
        assert executor._serialize_result(3.14) == 3.14
        assert executor._serialize_result(True) is True

    def test_serialize_pydantic_model(self, executor):
        """Test that Pydantic model is converted via model_dump."""
        from pydantic import BaseModel

        class TestModel(BaseModel):
            key: str

        model = TestModel(key="value")
        result = executor._serialize_result(model)
        assert result == {"key": "value"}


class TestLocalToolExecutorNavigate:
    """Tests for navigate tool handling."""

    @pytest.fixture
    def executor(self):
        return LocalToolExecutor()

    def test_handle_navigate_success(self, executor):
        """Test successful navigation."""
        mock_info = MagicMock()
        mock_info.context.ai_accessible_routes = [
            {"path": "/users"},
            {"path": "/settings"},
        ]
        mock_info.context.frontend_actions = []

        result = executor._handle_navigate({"path": "/users"}, mock_info)

        assert result["status"] == "navigation_scheduled"
        assert len(mock_info.context.frontend_actions) == 1
        assert mock_info.context.frontend_actions[0]["type"] == "navigate"
        assert mock_info.context.frontend_actions[0]["path"] == "/users"

    def test_handle_navigate_invalid_path(self, executor):
        """Test navigation to invalid path."""
        mock_info = MagicMock()
        mock_info.context.ai_accessible_routes = [
            {"path": "/users"},
        ]

        result = executor._handle_navigate({"path": "/admin"}, mock_info)

        assert result["status"] == "error"
        assert "/admin" in result["message"]

    def test_handle_navigate_creates_frontend_actions_list(self, executor):
        """Test that frontend_actions list is created if not exists."""
        mock_info = MagicMock(spec=[])
        mock_info.context = MagicMock(spec=[])
        mock_info.context.ai_accessible_routes = [{"path": "/users"}]

        # Remove frontend_actions attribute
        del mock_info.context.frontend_actions

        result = executor._handle_navigate({"path": "/users"}, mock_info)

        assert result["status"] == "navigation_scheduled"
        assert hasattr(mock_info.context, "frontend_actions")


class TestLocalToolExecutorExecute:
    """Tests for execute method."""

    @pytest.fixture
    def executor(self):
        mock_app_manager = MagicMock()
        return LocalToolExecutor(app_manager=mock_app_manager)

    @pytest.mark.asyncio
    async def test_execute_requires_info_context(self, executor):
        """Test that execute raises if info context is missing."""
        with pytest.raises(ValueError) as exc_info:
            await executor.execute(
                tool_name="test_tool",
                arguments={},
                context={"session": MagicMock()},
            )

        assert "info context is required" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_execute_navigate_tool(self, executor):
        """Test that navigate tool is handled specially."""
        mock_info = MagicMock()
        mock_info.context.ai_accessible_routes = [{"path": "/users"}]
        mock_info.context.frontend_actions = []

        result = await executor.execute(
            tool_name="navigate",
            arguments={"path": "/users"},
            context={"session": MagicMock(), "info": mock_info},
        )

        assert result["status"] == "navigation_scheduled"

    @pytest.mark.asyncio
    async def test_execute_unknown_tool_raises(self, executor):
        """Test that unknown tool raises ValueError."""
        mock_info = MagicMock()
        mock_info.context.app_manager = executor._app_manager
        executor._app_manager.registry.get_tool.side_effect = KeyError("unknown")

        with pytest.raises(ValueError) as exc_info:
            await executor.execute(
                tool_name="unknown_tool",
                arguments={},
                context={"session": MagicMock(), "info": mock_info},
            )

        assert "not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_execute_calls_resolver(self, executor):
        """Test that execute calls the tool resolver."""
        mock_info = MagicMock()
        mock_info.context.app_manager = executor._app_manager

        async def mock_resolver(info, name: str):
            return {"status": "ok", "name": name}

        executor._app_manager.registry.get_tool.return_value = {
            "resolver": mock_resolver,
            "node_type": None,
        }

        with patch.object(executor, "_process_guardrail", new_callable=AsyncMock) as mock_guardrail:
            mock_guardrail.return_value = None

            result = await executor.execute(
                tool_name="test_tool",
                arguments={"name": "test"},
                context={"session": MagicMock(), "info": mock_info},
            )

        assert result["status"] == "ok"
        assert result["name"] == "test"
