"""
Unit tests for user_role user module Strawberry inputs.

Tests GraphQL input types for user creation and role management.
"""

import pytest


class TestCreateUserWithRolesInputStructure:
    """Tests for CreateUserWithRolesInput Strawberry input class."""

    def test_input_exists(self):
        """Test CreateUserWithRolesInput class exists."""
        from lys.apps.user_role.modules.user.inputs import CreateUserWithRolesInput
        assert CreateUserWithRolesInput is not None

    def test_input_has_email_field(self):
        """Test input has email field."""
        from lys.apps.user_role.modules.user.inputs import CreateUserWithRolesInput
        field_names = [f.name for f in CreateUserWithRolesInput.__strawberry_definition__.fields]
        assert "email" in field_names

    def test_input_has_password_field(self):
        """Test input has password field."""
        from lys.apps.user_role.modules.user.inputs import CreateUserWithRolesInput
        field_names = [f.name for f in CreateUserWithRolesInput.__strawberry_definition__.fields]
        assert "password" in field_names

    def test_input_has_language_code_field(self):
        """Test input has language_code field."""
        from lys.apps.user_role.modules.user.inputs import CreateUserWithRolesInput
        field_names = [f.name for f in CreateUserWithRolesInput.__strawberry_definition__.fields]
        assert "language_code" in field_names

    def test_input_has_role_codes_field(self):
        """Test input has role_codes field."""
        from lys.apps.user_role.modules.user.inputs import CreateUserWithRolesInput
        field_names = [f.name for f in CreateUserWithRolesInput.__strawberry_definition__.fields]
        assert "role_codes" in field_names

    def test_input_has_first_name_field(self):
        """Test input has first_name field."""
        from lys.apps.user_role.modules.user.inputs import CreateUserWithRolesInput
        field_names = [f.name for f in CreateUserWithRolesInput.__strawberry_definition__.fields]
        assert "first_name" in field_names

    def test_input_has_last_name_field(self):
        """Test input has last_name field."""
        from lys.apps.user_role.modules.user.inputs import CreateUserWithRolesInput
        field_names = [f.name for f in CreateUserWithRolesInput.__strawberry_definition__.fields]
        assert "last_name" in field_names

    def test_input_has_gender_code_field(self):
        """Test input has gender_code field."""
        from lys.apps.user_role.modules.user.inputs import CreateUserWithRolesInput
        field_names = [f.name for f in CreateUserWithRolesInput.__strawberry_definition__.fields]
        assert "gender_code" in field_names

    def test_input_is_strawberry_pydantic_input(self):
        """Test input is a Strawberry Pydantic input."""
        from lys.apps.user_role.modules.user.inputs import CreateUserWithRolesInput
        assert hasattr(CreateUserWithRolesInput, "__strawberry_definition__")
        assert CreateUserWithRolesInput.__strawberry_definition__.is_input is True

    def test_input_has_to_pydantic_method(self):
        """Test input has to_pydantic method."""
        from lys.apps.user_role.modules.user.inputs import CreateUserWithRolesInput
        assert hasattr(CreateUserWithRolesInput, "to_pydantic")


class TestUpdateUserRolesInputStructure:
    """Tests for UpdateUserRolesInput Strawberry input class."""

    def test_input_exists(self):
        """Test UpdateUserRolesInput class exists."""
        from lys.apps.user_role.modules.user.inputs import UpdateUserRolesInput
        assert UpdateUserRolesInput is not None

    def test_input_has_role_codes_field(self):
        """Test input has role_codes field."""
        from lys.apps.user_role.modules.user.inputs import UpdateUserRolesInput
        field_names = [f.name for f in UpdateUserRolesInput.__strawberry_definition__.fields]
        assert "role_codes" in field_names

    def test_input_is_strawberry_pydantic_input(self):
        """Test input is a Strawberry Pydantic input."""
        from lys.apps.user_role.modules.user.inputs import UpdateUserRolesInput
        assert hasattr(UpdateUserRolesInput, "__strawberry_definition__")
        assert UpdateUserRolesInput.__strawberry_definition__.is_input is True

    def test_input_has_to_pydantic_method(self):
        """Test input has to_pydantic method."""
        from lys.apps.user_role.modules.user.inputs import UpdateUserRolesInput
        assert hasattr(UpdateUserRolesInput, "to_pydantic")


class TestInputFieldDescriptions:
    """Tests for input field descriptions."""

    def test_create_user_input_fields_have_descriptions(self):
        """Test CreateUserWithRolesInput fields have descriptions."""
        from lys.apps.user_role.modules.user.inputs import CreateUserWithRolesInput

        for field in CreateUserWithRolesInput.__strawberry_definition__.fields:
            assert field.description is not None, f"Field {field.name} has no description"

    def test_update_roles_input_fields_have_descriptions(self):
        """Test UpdateUserRolesInput fields have descriptions."""
        from lys.apps.user_role.modules.user.inputs import UpdateUserRolesInput

        for field in UpdateUserRolesInput.__strawberry_definition__.fields:
            assert field.description is not None, f"Field {field.name} has no description"


class TestCreateUserWithRolesInputModel:
    """Tests for input model structure (via models module)."""

    def test_input_model_has_role_codes(self):
        """Test that CreateUserWithRolesInputModel has role_codes field."""
        from lys.apps.user_role.modules.user.models import CreateUserWithRolesInputModel

        assert "role_codes" in CreateUserWithRolesInputModel.model_fields

    def test_input_model_inherits_base(self):
        """Test that CreateUserWithRolesInputModel inherits from CreateUserInputModel."""
        from lys.apps.user_role.modules.user.models import CreateUserWithRolesInputModel
        from lys.apps.user_auth.modules.user.models import CreateUserInputModel

        assert issubclass(CreateUserWithRolesInputModel, CreateUserInputModel)


class TestUpdateUserRolesInputModel:
    """Tests for UpdateUserRolesInputModel structure."""

    def test_input_model_has_role_codes(self):
        """Test that UpdateUserRolesInputModel has role_codes field."""
        from lys.apps.user_role.modules.user.models import UpdateUserRolesInputModel

        assert "role_codes" in UpdateUserRolesInputModel.model_fields

    def test_input_model_inherits_base_model(self):
        """Test that UpdateUserRolesInputModel inherits from BaseModel."""
        from lys.apps.user_role.modules.user.models import UpdateUserRolesInputModel
        from pydantic import BaseModel

        assert issubclass(UpdateUserRolesInputModel, BaseModel)
