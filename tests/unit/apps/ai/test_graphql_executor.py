"""
Unit tests for GraphQLToolExecutor.

Tests the GraphQL tool executor, particularly the _build_operation method
which reconstructs flattened input parameters into GraphQL input objects.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from lys.apps.ai.modules.core.executors.graphql import GraphQLToolExecutor


class TestGraphQLToolExecutorBuildOperation:
    """Tests for GraphQLToolExecutor._build_operation method."""

    @pytest.fixture
    def executor(self):
        """Create a GraphQLToolExecutor instance for testing."""
        with patch("lys.apps.ai.modules.core.executors.graphql.GraphQLClient"):
            executor = GraphQLToolExecutor(
                gateway_url="http://test-gateway:4000/graphql",
                secret_key="test-secret-key",
                service_name="test-service",
                timeout=30,
            )
            return executor

    def test_build_operation_without_input_wrappers(self, executor):
        """Test building a simple operation without input wrappers."""
        query, variables = executor._build_operation(
            operation_type="mutation",
            operation_name="createUser",
            arguments={"email": "test@example.com", "name": "John"},
            return_fields="id email name",
            properties={
                "email": {"type": "string", "_graphql_type": "String!"},
                "name": {"type": "string", "_graphql_type": "String!"},
            },
            node_type=None,
            input_wrappers=None,
        )

        assert "mutation ToolExecution" in query
        assert "createUser" in query
        assert "$email: String!" in query
        assert "$name: String!" in query
        assert "email: $email" in query
        assert "name: $name" in query
        assert variables == {"email": "test@example.com", "name": "John"}

    def test_build_operation_with_input_wrappers(self, executor):
        """Test building an operation with input wrappers (flattened inputs)."""
        query, variables = executor._build_operation(
            operation_type="mutation",
            operation_name="updateUserPrivateData",
            arguments={
                "bio": "Hello world",
                "first_name": "John",
                "last_name": "Doe",
            },
            return_fields="id bio firstName lastName",
            properties={
                "bio": {"type": "string", "_graphql_type": "String"},
                "first_name": {"type": "string", "_graphql_type": "String"},
                "last_name": {"type": "string", "_graphql_type": "String"},
            },
            node_type=None,
            input_wrappers=[{
                "param_name": "inputs",
                "graphql_type": "UpdateUserPrivateDataInput!",
                "fields": ["bio", "first_name", "last_name"],
            }],
        )

        # Check query structure
        assert "mutation ToolExecution" in query
        assert "updateUserPrivateData" in query
        assert "$inputs: UpdateUserPrivateDataInput!" in query
        assert "inputs: $inputs" in query

        # Individual fields should NOT be in the query
        assert "$bio:" not in query
        assert "$firstName:" not in query
        assert "$lastName:" not in query

        # Check variables - fields should be nested in "inputs"
        assert "inputs" in variables
        assert variables["inputs"]["bio"] == "Hello world"
        assert variables["inputs"]["firstName"] == "John"
        assert variables["inputs"]["lastName"] == "Doe"

    def test_build_operation_with_mixed_arguments(self, executor):
        """Test operation with both wrapped and non-wrapped arguments."""
        query, variables = executor._build_operation(
            operation_type="mutation",
            operation_name="updateUser",
            arguments={
                "id": "user-123",
                "bio": "Updated bio",
                "first_name": "Jane",
            },
            return_fields="id bio firstName",
            properties={
                "id": {"type": "string", "_graphql_type": "ID!"},
                "bio": {"type": "string", "_graphql_type": "String"},
                "first_name": {"type": "string", "_graphql_type": "String"},
            },
            node_type="UserNode",
            input_wrappers=[{
                "param_name": "inputs",
                "graphql_type": "UpdateUserInput!",
                "fields": ["bio", "first_name"],
            }],
        )

        # Check that id is passed directly (not wrapped)
        assert "$id: ID!" in query
        assert "id: $id" in query

        # Check that inputs wrapper is used
        assert "$inputs: UpdateUserInput!" in query
        assert "inputs: $inputs" in query

        # Variables should have both id and inputs
        assert "id" in variables
        assert "inputs" in variables
        assert variables["inputs"]["bio"] == "Updated bio"
        assert variables["inputs"]["firstName"] == "Jane"

    def test_build_operation_converts_snake_case_to_camel_case(self, executor):
        """Test that snake_case field names are converted to camelCase."""
        query, variables = executor._build_operation(
            operation_type="mutation",
            operation_name="updateProfile",
            arguments={
                "phone_number": "+1234567890",
                "date_of_birth": "1990-01-01",
            },
            return_fields="id phoneNumber dateOfBirth",
            properties={
                "phone_number": {"type": "string", "_graphql_type": "String"},
                "date_of_birth": {"type": "string", "_graphql_type": "String"},
            },
            node_type=None,
            input_wrappers=[{
                "param_name": "profile_data",
                "graphql_type": "ProfileDataInput!",
                "fields": ["phone_number", "date_of_birth"],
            }],
        )

        # Check that param name is camelCase
        assert "$profileData: ProfileDataInput!" in query
        assert "profileData: $profileData" in query

        # Check variables use camelCase for nested fields
        assert "profileData" in variables
        assert variables["profileData"]["phoneNumber"] == "+1234567890"
        assert variables["profileData"]["dateOfBirth"] == "1990-01-01"

    def test_build_operation_with_empty_input_wrappers(self, executor):
        """Test operation with empty input_wrappers list."""
        query, variables = executor._build_operation(
            operation_type="query",
            operation_name="getUser",
            arguments={"user_id": "123"},
            return_fields="id email",
            properties={
                "user_id": {"type": "string", "_graphql_type": "String!"},  # Not ID to avoid GlobalID encoding
            },
            node_type=None,
            input_wrappers=[],
        )

        # Should behave as if no wrappers
        assert "$userId: String!" in query
        assert "userId: $userId" in query
        assert variables == {"userId": "123"}

    def test_build_operation_with_no_arguments(self, executor):
        """Test operation with no arguments."""
        query, variables = executor._build_operation(
            operation_type="query",
            operation_name="allUsers",
            arguments={},
            return_fields="id email",
            properties={},
            node_type=None,
            input_wrappers=None,
        )

        # Query should not have variables declaration
        assert "query {" in query
        assert "allUsers {" in query
        assert "ToolExecution" not in query
        assert variables == {}

    def test_build_operation_partial_input_wrapper_fields(self, executor):
        """Test that only provided fields are included in input wrapper."""
        query, variables = executor._build_operation(
            operation_type="mutation",
            operation_name="updateProfile",
            arguments={
                "bio": "New bio",
                # first_name and last_name are NOT provided
            },
            return_fields="id bio",
            properties={
                "bio": {"type": "string", "_graphql_type": "String"},
            },
            node_type=None,
            input_wrappers=[{
                "param_name": "inputs",
                "graphql_type": "UpdateProfileInput!",
                "fields": ["bio", "first_name", "last_name"],
            }],
        )

        # Only bio should be in the input object
        assert "inputs" in variables
        assert variables["inputs"] == {"bio": "New bio"}
        assert "firstName" not in variables["inputs"]
        assert "lastName" not in variables["inputs"]


class TestGraphQLToolExecutorGlobalID:
    """Tests for GlobalID conversion in GraphQLToolExecutor."""

    @pytest.fixture
    def executor(self):
        """Create a GraphQLToolExecutor instance for testing."""
        with patch("lys.apps.ai.modules.core.executors.graphql.GraphQLClient"):
            executor = GraphQLToolExecutor(
                gateway_url="http://test-gateway:4000/graphql",
                secret_key="test-secret-key",
                service_name="test-service",
                timeout=30,
            )
            return executor

    def test_to_global_id_encodes_uuid(self, executor):
        """Test that raw UUIDs are encoded to GlobalID format."""
        import base64

        result = executor._to_global_id(
            param_name="user_id",
            value="550e8400-e29b-41d4-a716-446655440000",
            node_type="UserNode"
        )

        # Decode and verify
        decoded = base64.b64decode(result).decode()
        assert decoded == "UserNode:550e8400-e29b-41d4-a716-446655440000"

    def test_to_global_id_skips_already_encoded(self, executor):
        """Test that already-encoded GlobalIDs are not double-encoded."""
        import base64

        # Pre-encode a GlobalID
        original = "UserNode:550e8400-e29b-41d4-a716-446655440000"
        already_encoded = base64.b64encode(original.encode()).decode()

        result = executor._to_global_id(
            param_name="user_id",
            value=already_encoded,
            node_type="UserNode"
        )

        # Should return the same value
        assert result == already_encoded

    def test_to_global_id_derives_type_from_param_name(self, executor):
        """Test that node type is derived from param name if not provided."""
        import base64

        result = executor._to_global_id(
            param_name="organization_id",
            value="org-123",
            node_type=None  # Not provided
        )

        # Should derive OrganizationNode from organization_id
        decoded = base64.b64decode(result).decode()
        assert decoded == "OrganizationNode:org-123"

    def test_build_operation_converts_ids_in_wrapped_fields(self, executor):
        """Test that IDs in input wrappers are converted to GlobalID."""
        import base64

        query, variables = executor._build_operation(
            operation_type="mutation",
            operation_name="assignRole",
            arguments={
                "user_id": "user-uuid-123",
                "role_id": "role-uuid-456",
            },
            return_fields="id",
            properties={
                "user_id": {"type": "string", "_graphql_type": "ID!"},
                "role_id": {"type": "string", "_graphql_type": "ID!"},
            },
            node_type="UserNode",
            input_wrappers=[{
                "param_name": "inputs",
                "graphql_type": "AssignRoleInput!",
                "fields": ["user_id", "role_id"],
            }],
        )

        # Both IDs should be GlobalID encoded
        user_id_decoded = base64.b64decode(variables["inputs"]["userId"]).decode()
        role_id_decoded = base64.b64decode(variables["inputs"]["roleId"]).decode()

        assert "UserNode:user-uuid-123" == user_id_decoded
        assert "UserNode:role-uuid-456" == role_id_decoded


class TestGraphQLToolExecutorVerifySSL:
    """Tests for verify_ssl parameter in GraphQLToolExecutor."""

    def test_default_verify_ssl_true(self):
        """Test that verify_ssl defaults to True."""
        with patch("lys.apps.ai.modules.core.executors.graphql.GraphQLClient") as MockClient:
            GraphQLToolExecutor(
                gateway_url="http://test:4000/graphql",
                secret_key="secret",
                service_name="test",
            )
            MockClient.assert_called_once_with(
                url="http://test:4000/graphql",
                secret_key="secret",
                service_name="test",
                bearer_token=None,
                timeout=30,
                verify_ssl=True,
            )

    def test_verify_ssl_false_passed_to_client(self):
        """Test that verify_ssl=False is forwarded to GraphQLClient."""
        with patch("lys.apps.ai.modules.core.executors.graphql.GraphQLClient") as MockClient:
            GraphQLToolExecutor(
                gateway_url="http://test:4000/graphql",
                secret_key="secret",
                service_name="test",
                verify_ssl=False,
            )
            MockClient.assert_called_once_with(
                url="http://test:4000/graphql",
                secret_key="secret",
                service_name="test",
                bearer_token=None,
                timeout=30,
                verify_ssl=False,
            )


class TestGraphQLToolExecutorInitialize:
    """Tests for GraphQLToolExecutor initialization."""

    @pytest.mark.asyncio
    async def test_initialize_with_tools_list(self):
        """Test initialization with a list of tools."""
        with patch("lys.apps.ai.modules.core.executors.graphql.GraphQLClient"):
            executor = GraphQLToolExecutor(
                gateway_url="http://test:4000/graphql",
                secret_key="secret",
                service_name="test",
            )

        tools = [
            {
                "ai_tool": {
                    "type": "function",
                    "function": {"name": "get_user"},
                },
                "operation_type": "query",
            },
            {
                "definition": {
                    "type": "function",
                    "function": {"name": "create_user"},
                },
                "operation_type": "mutation",
            },
        ]

        await executor.initialize(tools)

        assert executor._initialized
        assert "get_user" in executor._tools
        assert "create_user" in executor._tools
        assert executor._tools["get_user"]["operation_type"] == "query"
        assert executor._tools["create_user"]["operation_type"] == "mutation"

    def test_add_tool_manually(self):
        """Test manually adding a tool definition."""
        with patch("lys.apps.ai.modules.core.executors.graphql.GraphQLClient"):
            executor = GraphQLToolExecutor(
                gateway_url="http://test:4000/graphql",
                secret_key="secret",
                service_name="test",
            )

        definition = {
            "type": "function",
            "function": {"name": "custom_tool"},
        }

        executor.add_tool("custom_tool", definition, "mutation")

        assert "custom_tool" in executor._tools
        assert executor._tools["custom_tool"]["definition"] == definition
        assert executor._tools["custom_tool"]["operation_type"] == "mutation"


class TestGraphQLToolExecutorExecute:
    """Tests for GraphQLToolExecutor.execute method."""

    @pytest.fixture
    def executor(self):
        """Create an initialized executor with mock client."""
        with patch("lys.apps.ai.modules.core.executors.graphql.GraphQLClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value = mock_client

            executor = GraphQLToolExecutor(
                gateway_url="http://test:4000/graphql",
                secret_key="secret",
                service_name="test",
            )
            executor._client = mock_client
            executor._initialized = True
            executor._tools = {
                "update_user": {
                    "definition": {
                        "type": "function",
                        "function": {
                            "name": "update_user",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "bio": {"type": "string"},
                                    "first_name": {"type": "string"},
                                },
                            },
                        },
                        "_graphql": {
                            "operation_name": "updateUser",
                            "return_fields": "id bio firstName",
                            "node_type": "UserNode",
                            "input_wrappers": [{
                                "param_name": "inputs",
                                "graphql_type": "UpdateUserInput!",
                                "fields": ["bio", "first_name"],
                            }],
                        },
                    },
                    "operation_type": "mutation",
                },
            }

            return executor

    @pytest.mark.asyncio
    async def test_execute_with_input_wrappers(self, executor):
        """Test executing a tool that uses input wrappers."""
        executor._client.execute.return_value = {
            "data": {
                "updateUser": {
                    "id": "user-123",
                    "bio": "Updated bio",
                    "firstName": "John",
                }
            }
        }

        result = await executor.execute(
            tool_name="update_user",
            arguments={"bio": "Updated bio", "first_name": "John"},
            context={},
        )

        assert result["id"] == "user-123"
        assert result["bio"] == "Updated bio"

        # Verify the GraphQL call was made with wrapped inputs
        call_args = executor._client.execute.call_args
        query = call_args[0][0]
        variables = call_args[0][1]

        assert "$inputs: UpdateUserInput!" in query
        assert "inputs" in variables
        assert variables["inputs"]["bio"] == "Updated bio"
        assert variables["inputs"]["firstName"] == "John"

    @pytest.mark.asyncio
    async def test_execute_raises_if_not_initialized(self):
        """Test that execute raises if executor not initialized."""
        with patch("lys.apps.ai.modules.core.executors.graphql.GraphQLClient"):
            executor = GraphQLToolExecutor(
                gateway_url="http://test:4000/graphql",
                secret_key="secret",
                service_name="test",
            )
            # Not calling initialize()

        with pytest.raises(RuntimeError) as exc_info:
            await executor.execute("some_tool", {}, {})

        assert "not initialized" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_execute_raises_for_unknown_tool(self, executor):
        """Test that execute raises for unknown tool."""
        with pytest.raises(ValueError) as exc_info:
            await executor.execute("unknown_tool", {}, {})

        assert "not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_execute_handles_graphql_errors(self, executor):
        """Test that GraphQL errors are returned properly."""
        executor._client.execute.return_value = {
            "errors": [{"message": "Field 'bio' cannot be null"}]
        }

        result = await executor.execute(
            tool_name="update_user",
            arguments={"bio": None, "first_name": "John"},
            context={},
        )

        assert result["status"] == "error"
        assert "bio" in result["message"]
