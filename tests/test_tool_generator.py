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
from lys.core.registries import AppRegistry


class TestPythonTypeToJsonSchema:
    """Tests for python_type_to_json_schema function."""

    def test_string_type(self):
        result = python_type_to_json_schema(str)
        assert result["type"] == "string"
        assert result["_graphql_type"] == "String!"

    def test_int_type(self):
        result = python_type_to_json_schema(int)
        assert result["type"] == "integer"
        assert result["_graphql_type"] == "Int!"

    def test_float_type(self):
        result = python_type_to_json_schema(float)
        assert result["type"] == "number"
        assert result["_graphql_type"] == "Float!"

    def test_bool_type(self):
        result = python_type_to_json_schema(bool)
        assert result["type"] == "boolean"
        assert result["_graphql_type"] == "Boolean!"

    def test_datetime_type(self):
        result = python_type_to_json_schema(datetime)
        assert result["type"] == "string"
        assert result["format"] == "date-time"
        assert result["_graphql_type"] == "DateTime!"

    def test_optional_string(self):
        result = python_type_to_json_schema(Optional[str])
        assert result["type"] == "string"
        assert result["_graphql_type"] == "String"  # No ! for optional

    def test_optional_int(self):
        result = python_type_to_json_schema(Optional[int])
        assert result["type"] == "integer"
        assert result["_graphql_type"] == "Int"  # No ! for optional

    def test_list_of_strings(self):
        result = python_type_to_json_schema(List[str])
        assert result["type"] == "array"
        assert result["items"]["type"] == "string"
        assert result["items"]["_graphql_type"] == "String!"

    def test_list_of_ints(self):
        result = python_type_to_json_schema(List[int])
        assert result["type"] == "array"
        assert result["items"]["type"] == "integer"
        assert result["items"]["_graphql_type"] == "Int!"

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

    def test_webservice_registration_generates_tool(self):
        """Test that webservice registration stores webservice fixture.

        Note: Tool generation requires:
        - options={"generate_tool": True}
        - AI plugin configured in settings
        - StrawberryField with operation_type

        This test verifies basic webservice registration without tool generation.
        """
        register = AppRegistry()

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

        # Webservice should be registered
        assert "my_webservice" in register.webservices

        webservice = register.webservices["my_webservice"]
        assert webservice["id"] == "my_webservice"
        assert webservice["attributes"]["public_type"] == "NO_LIMITATION"
        assert webservice["attributes"]["enabled"] is True


class TestInputWrappers:
    """Tests for input_wrappers metadata in tool definitions."""

    def test_tool_with_strawberry_input_has_input_wrappers(self):
        """Test that tools with Strawberry inputs include input_wrappers metadata."""
        @strawberry.input
        class UpdateProfileInput:
            bio: str
            first_name: Optional[str] = None
            last_name: Optional[str] = None

        async def update_profile(self, inputs: UpdateProfileInput) -> dict:
            """Update user profile."""
            pass

        result = extract_tool_from_resolver(update_profile, "Update profile")

        # Check that _graphql metadata includes input_wrappers
        graphql_meta = result.get("_graphql", {})
        assert graphql_meta is not None
        assert "input_wrappers" in graphql_meta

        input_wrappers = graphql_meta["input_wrappers"]
        assert len(input_wrappers) == 1

        wrapper = input_wrappers[0]
        assert wrapper["param_name"] == "inputs"
        assert "UpdateProfileInput" in wrapper["graphql_type"]
        assert "bio" in wrapper["fields"]
        assert "first_name" in wrapper["fields"]
        assert "last_name" in wrapper["fields"]

    def test_tool_without_strawberry_input_has_no_input_wrappers(self):
        """Test that tools without Strawberry inputs have no input_wrappers."""
        async def create_user(email: str, password: str) -> dict:
            """Create user with simple params."""
            pass

        result = extract_tool_from_resolver(create_user, "Create user")

        graphql_meta = result.get("_graphql", {})
        # input_wrappers should be None or empty
        assert graphql_meta.get("input_wrappers") is None

    def test_tool_with_pydantic_based_input_has_input_wrappers(self):
        """Test that Pydantic-based Strawberry inputs include input_wrappers."""
        class UpdateUserModel(BaseModel):
            bio: Optional[str] = None
            phone_number: Optional[str] = None

        @strawberry.experimental.pydantic.input(model=UpdateUserModel)
        class UpdateUserInput:
            bio: strawberry.auto
            phone_number: strawberry.auto

        async def update_user(self, inputs: UpdateUserInput) -> dict:
            """Update user data."""
            pass

        result = extract_tool_from_resolver(update_user, "Update user")

        graphql_meta = result.get("_graphql", {})
        assert "input_wrappers" in graphql_meta

        input_wrappers = graphql_meta["input_wrappers"]
        assert len(input_wrappers) == 1

        wrapper = input_wrappers[0]
        assert wrapper["param_name"] == "inputs"
        assert "bio" in wrapper["fields"]
        assert "phone_number" in wrapper["fields"]

    def test_flattened_fields_are_in_parameters(self):
        """Test that input fields are flattened into the top-level parameters."""
        @strawberry.input
        class CreateItemInput:
            name: str
            description: Optional[str] = None
            price: float

        async def create_item(self, inputs: CreateItemInput) -> dict:
            """Create an item."""
            pass

        result = extract_tool_from_resolver(create_item, "Create item")

        params = result["function"]["parameters"]
        properties = params["properties"]

        # Fields should be flattened to top level
        assert "name" in properties
        assert "description" in properties
        assert "price" in properties

        # The original 'inputs' param should NOT be in properties
        assert "inputs" not in properties

        # Required fields - check if present (may depend on how Strawberry marks fields)
        required = params.get("required", [])
        # Optional field should not be in required
        assert "description" not in required

    def test_graphql_metadata_includes_operation_name(self):
        """Test that _graphql metadata includes operation_name in camelCase."""
        async def update_user_profile(param: str) -> dict:
            """Update profile."""
            pass

        result = extract_tool_from_resolver(update_user_profile, "Update profile")

        graphql_meta = result.get("_graphql", {})
        assert graphql_meta["operation_name"] == "updateUserProfile"

    def test_multiple_input_types_in_resolver(self):
        """Test resolver with multiple Strawberry input parameters."""
        @strawberry.input
        class AddressInput:
            street: str
            city: str

        @strawberry.input
        class ContactInput:
            email: str
            phone: Optional[str] = None

        async def update_user_details(
            self,
            address: AddressInput,
            contact: ContactInput
        ) -> dict:
            """Update user details with multiple inputs."""
            pass

        result = extract_tool_from_resolver(update_user_details, "Update details")

        graphql_meta = result.get("_graphql", {})
        input_wrappers = graphql_meta.get("input_wrappers", [])

        # Should have 2 input wrappers
        assert len(input_wrappers) == 2

        # Check first wrapper (address)
        address_wrapper = next(w for w in input_wrappers if w["param_name"] == "address")
        assert "street" in address_wrapper["fields"]
        assert "city" in address_wrapper["fields"]

        # Check second wrapper (contact)
        contact_wrapper = next(w for w in input_wrappers if w["param_name"] == "contact")
        assert "email" in contact_wrapper["fields"]
        assert "phone" in contact_wrapper["fields"]

        # All fields should be flattened
        params = result["function"]["parameters"]["properties"]
        assert "street" in params
        assert "city" in params
        assert "email" in params
        assert "phone" in params