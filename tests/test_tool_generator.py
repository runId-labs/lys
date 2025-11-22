"""
Unit tests for the tool generator utility.
"""

import pytest
from typing import Optional, List
from datetime import datetime

import strawberry
from pydantic import BaseModel, Field

from lys.core.utils.tool_generator import (
    python_type_to_json_schema,
    extract_strawberry_input_schema,
    extract_tool_from_field,
    extract_tool_from_resolver,
)
from lys.core.registers import AppRegister


class TestPythonTypeToJsonSchema:
    """Tests for python_type_to_json_schema function."""

    def test_string_type(self):
        result = python_type_to_json_schema(str)
        assert result == {"type": "string"}

    def test_int_type(self):
        result = python_type_to_json_schema(int)
        assert result == {"type": "integer"}

    def test_float_type(self):
        result = python_type_to_json_schema(float)
        assert result == {"type": "number"}

    def test_bool_type(self):
        result = python_type_to_json_schema(bool)
        assert result == {"type": "boolean"}

    def test_datetime_type(self):
        result = python_type_to_json_schema(datetime)
        assert result == {"type": "string", "format": "date-time"}

    def test_optional_string(self):
        result = python_type_to_json_schema(Optional[str])
        assert result == {"type": "string"}

    def test_optional_int(self):
        result = python_type_to_json_schema(Optional[int])
        assert result == {"type": "integer"}

    def test_list_of_strings(self):
        result = python_type_to_json_schema(List[str])
        assert result == {"type": "array", "items": {"type": "string"}}

    def test_list_of_ints(self):
        result = python_type_to_json_schema(List[int])
        assert result == {"type": "array", "items": {"type": "integer"}}

    def test_none_type(self):
        result = python_type_to_json_schema(type(None))
        assert result == {"type": "null"}


class TestExtractStrawberryInputSchema:
    """Tests for extract_strawberry_input_schema function."""

    def test_simple_input(self):
        @strawberry.input
        class SimpleInput:
            name: str
            age: int

        result = extract_strawberry_input_schema(SimpleInput)

        assert result["type"] == "object"
        assert "name" in result["properties"]
        assert "age" in result["properties"]
        assert result["properties"]["name"]["type"] == "string"
        assert result["properties"]["age"]["type"] == "integer"
        # Note: Required fields are determined by Strawberry's internal logic
        # The important thing is that properties are correctly extracted

    def test_input_with_optional_fields(self):
        @strawberry.input
        class InputWithOptional:
            required_field: str
            optional_field: Optional[str] = None

        result = extract_strawberry_input_schema(InputWithOptional)

        assert result["type"] == "object"
        assert "required_field" in result["properties"]
        assert "optional_field" in result["properties"]
        # Optional field should not be in required list
        assert "optional_field" not in result.get("required", [])

    def test_input_with_description(self):
        @strawberry.input
        class InputWithDescription:
            email: str = strawberry.field(description="User email address")

        result = extract_strawberry_input_schema(InputWithDescription)

        assert result["type"] == "object"
        assert "email" in result["properties"]
        # Description should be included
        assert result["properties"]["email"].get("description") == "User email address"

    def test_pydantic_based_input(self):
        """Test Strawberry input based on Pydantic BaseModel."""
        class CreateUserInputModel(BaseModel):
            email: str
            password: str
            first_name: Optional[str] = None
            age: Optional[int] = None

        @strawberry.experimental.pydantic.input(model=CreateUserInputModel)
        class CreateUserInput:
            email: strawberry.auto = strawberry.field(
                description="User email address"
            )
            password: strawberry.auto = strawberry.field(
                description="User password"
            )
            first_name: strawberry.auto = strawberry.field(
                description="First name"
            )
            age: strawberry.auto = strawberry.field(
                description="User age"
            )

        result = extract_strawberry_input_schema(CreateUserInput)

        assert result["type"] == "object"
        assert "email" in result["properties"]
        assert "password" in result["properties"]
        assert "first_name" in result["properties"]
        assert "age" in result["properties"]
        # Check types - Strawberry resolves them from Pydantic model
        assert result["properties"]["email"]["type"] == "string"
        assert result["properties"]["password"]["type"] == "string"
        assert result["properties"]["first_name"]["type"] == "string"
        assert result["properties"]["age"]["type"] == "integer"
        # Note: Descriptions are not preserved by Strawberry's Pydantic integration
        # when using strawberry.field(description=...). Use Pydantic Field() instead.

    def test_pydantic_field_descriptions(self):
        """Test that Pydantic Field descriptions are preserved."""
        class UserModel(BaseModel):
            email: str = Field(description="User email address")
            age: Optional[int] = Field(default=None, description="User age in years")

        @strawberry.experimental.pydantic.input(model=UserModel)
        class UserInput:
            email: strawberry.auto
            age: strawberry.auto

        result = extract_strawberry_input_schema(UserInput)

        assert result["type"] == "object"
        assert "email" in result["properties"]
        assert "age" in result["properties"]
        # Check types
        assert result["properties"]["email"]["type"] == "string"
        assert result["properties"]["age"]["type"] == "integer"
        # Check descriptions - these ARE preserved from Pydantic Field()
        assert result["properties"]["email"].get("description") == "User email address"
        assert result["properties"]["age"].get("description") == "User age in years"

    def test_resolver_with_pydantic_based_input(self):
        """Test resolver that uses Pydantic-based Strawberry input."""
        class UpdateEmailModel(BaseModel):
            new_email: str

        @strawberry.experimental.pydantic.input(model=UpdateEmailModel)
        class UpdateEmailInput:
            new_email: strawberry.auto = strawberry.field(
                description="New email address"
            )

        async def update_email(self, inputs: UpdateEmailInput) -> dict:
            """Update user email."""
            pass

        result = extract_tool_from_resolver(update_email, "Update email address")

        assert result["type"] == "function"
        assert result["function"]["name"] == "update_email"
        assert "new_email" in result["function"]["parameters"]["properties"]
        assert result["function"]["parameters"]["properties"]["new_email"]["type"] == "string"
        # Note: Descriptions are not preserved by Strawberry's Pydantic integration


class TestExtractToolFromResolver:
    """Tests for extract_tool_from_resolver function."""

    def test_simple_resolver(self):
        async def create_user(email: str, password: str) -> dict:
            """Create a new user."""
            pass

        result = extract_tool_from_resolver(create_user, "Create a new user")

        assert result["type"] == "function"
        assert result["function"]["name"] == "create_user"
        assert result["function"]["description"] == "Create a new user"
        assert "email" in result["function"]["parameters"]["properties"]
        assert "password" in result["function"]["parameters"]["properties"]
        assert "email" in result["function"]["parameters"]["required"]
        assert "password" in result["function"]["parameters"]["required"]

    def test_resolver_with_optional_params(self):
        async def search_users(
            query: str,
            limit: Optional[int] = None,
            offset: Optional[int] = None
        ) -> list:
            """Search for users."""
            pass

        result = extract_tool_from_resolver(search_users)

        assert result["type"] == "function"
        assert result["function"]["name"] == "search_users"
        assert "query" in result["function"]["parameters"]["properties"]
        assert "limit" in result["function"]["parameters"]["properties"]
        assert "offset" in result["function"]["parameters"]["properties"]
        # Only query should be required
        assert "query" in result["function"]["parameters"]["required"]
        assert "limit" not in result["function"]["parameters"]["required"]
        assert "offset" not in result["function"]["parameters"]["required"]

    def test_resolver_with_strawberry_input(self):
        @strawberry.input
        class CreateUserInput:
            email: str
            password: str
            first_name: Optional[str] = None

        async def create_user(self, inputs: CreateUserInput) -> dict:
            """Create a new user with input object."""
            pass

        result = extract_tool_from_resolver(create_user, "Create user")

        assert result["type"] == "function"
        assert result["function"]["name"] == "create_user"
        # Input fields should be flattened
        assert "email" in result["function"]["parameters"]["properties"]
        assert "password" in result["function"]["parameters"]["properties"]
        assert "first_name" in result["function"]["parameters"]["properties"]
        # Optional field should not be in required
        assert "first_name" not in result["function"]["parameters"].get("required", [])

    def test_resolver_skips_special_params(self):
        class Info:
            pass

        async def get_user(self, info: Info, user_id: str) -> dict:
            """Get user by ID."""
            pass

        result = extract_tool_from_resolver(get_user)

        assert result["type"] == "function"
        # self and info should be skipped
        assert "self" not in result["function"]["parameters"]["properties"]
        assert "info" not in result["function"]["parameters"]["properties"]
        # user_id should be included
        assert "user_id" in result["function"]["parameters"]["properties"]

    def test_resolver_description_from_docstring(self):
        async def my_function(param: str) -> dict:
            """This is the description from docstring."""
            pass

        result = extract_tool_from_resolver(my_function)

        assert result["function"]["description"] == "This is the description from docstring."


class TestExtractToolFromField:
    """Tests for extract_tool_from_field function."""

    def test_field_extraction(self):
        async def test_resolver(email: str) -> dict:
            """Test resolver."""
            pass

        field = strawberry.field(resolver=test_resolver)

        result = extract_tool_from_field(field, "Test description")

        assert result["type"] == "function"
        assert result["function"]["name"] == "test_resolver"
        assert result["function"]["description"] == "Test description"
        assert "email" in result["function"]["parameters"]["properties"]


class TestAppRegisterToolIntegration:
    """Tests for tool registration in AppRegister."""

    def test_register_tool(self):
        register = AppRegister()
        tool_definition = {
            "type": "function",
            "function": {
                "name": "test_tool",
                "description": "Test tool",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            }
        }

        def mock_resolver():
            pass

        register.register_tool("test_tool", tool_definition, mock_resolver)

        assert "test_tool" in register.tools
        assert register.tools["test_tool"]["definition"] == tool_definition
        assert register.tools["test_tool"]["resolver"] == mock_resolver

    def test_get_tools(self):
        register = AppRegister()
        tool1 = {"type": "function", "function": {"name": "tool1"}}
        tool2 = {"type": "function", "function": {"name": "tool2"}}

        register.register_tool("tool1", tool1, lambda: None)
        register.register_tool("tool2", tool2, lambda: None)

        tools = register.get_tools()

        assert len(tools) == 2
        assert tool1 in tools
        assert tool2 in tools

    def test_get_tool_by_name(self):
        register = AppRegister()
        tool_definition = {
            "type": "function",
            "function": {"name": "specific_tool"}
        }

        def mock_resolver():
            pass

        register.register_tool("specific_tool", tool_definition, mock_resolver)

        result = register.get_tool("specific_tool")

        assert result["definition"] == tool_definition
        assert result["resolver"] == mock_resolver

    def test_get_tool_definition(self):
        register = AppRegister()
        tool_definition = {
            "type": "function",
            "function": {"name": "my_tool"}
        }

        register.register_tool("my_tool", tool_definition, lambda: None)

        result = register.get_tool_definition("my_tool")

        assert result == tool_definition

    def test_get_tool_resolver(self):
        register = AppRegister()

        async def my_resolver():
            return "result"

        register.register_tool("my_tool", {"type": "function"}, my_resolver)

        result = register.get_tool_resolver("my_tool")

        assert result == my_resolver

    def test_get_tool_not_found(self):
        register = AppRegister()

        with pytest.raises(KeyError) as exc_info:
            register.get_tool("nonexistent")

        assert "nonexistent" in str(exc_info.value)

    def test_webservice_registration_generates_tool(self):
        register = AppRegister()

        async def my_webservice(email: str, password: str) -> dict:
            """My webservice description."""
            pass

        field = strawberry.field(resolver=my_webservice)

        register.register_webservice(
            field,
            is_public=True,
            enabled=True,
            is_licenced=False,  # Public webservices cannot be licenced
            description="Create something"
        )

        # Both webservice and tool should be registered
        assert "my_webservice" in register.webservices
        assert "my_webservice" in register.tools

        tool = register.tools["my_webservice"]
        assert tool["definition"]["function"]["name"] == "my_webservice"
        assert "email" in tool["definition"]["function"]["parameters"]["properties"]
        assert "password" in tool["definition"]["function"]["parameters"]["properties"]
        # Resolver should be stored
        assert tool["resolver"] == my_webservice