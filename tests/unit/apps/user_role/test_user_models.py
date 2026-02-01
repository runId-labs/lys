"""
Unit tests for user_role user module Pydantic models.

Tests input models for user creation and role management.
"""

import pytest
from pydantic import ValidationError


class TestCreateUserWithRolesInputModel:
    """Tests for CreateUserWithRolesInputModel."""

    def test_model_inherits_from_create_user_input_model(self):
        """Test that CreateUserWithRolesInputModel inherits from CreateUserInputModel."""
        from lys.apps.user_role.modules.user.models import CreateUserWithRolesInputModel
        from lys.apps.user_auth.modules.user.models import CreateUserInputModel

        assert issubclass(CreateUserWithRolesInputModel, CreateUserInputModel)

    def test_has_role_codes_field(self):
        """Test that model has role_codes field."""
        from lys.apps.user_role.modules.user.models import CreateUserWithRolesInputModel

        assert "role_codes" in CreateUserWithRolesInputModel.model_fields

    def test_role_codes_field_is_optional(self):
        """Test that role_codes field is optional."""
        from lys.apps.user_role.modules.user.models import CreateUserWithRolesInputModel

        field_info = CreateUserWithRolesInputModel.model_fields["role_codes"]
        # Optional fields have default=None
        assert field_info.default is None

    def test_valid_model_with_roles(self):
        """Test creating valid model with role_codes."""
        from lys.apps.user_role.modules.user.models import CreateUserWithRolesInputModel

        model = CreateUserWithRolesInputModel(
            email="test@example.com",
            password="password123",
            language_code="en",
            role_codes=["admin", "user"]
        )

        assert model.email == "test@example.com"
        assert model.role_codes == ["admin", "user"]

    def test_valid_model_without_roles(self):
        """Test creating valid model without role_codes."""
        from lys.apps.user_role.modules.user.models import CreateUserWithRolesInputModel

        model = CreateUserWithRolesInputModel(
            email="test@example.com",
            password="password123",
            language_code="en"
        )

        assert model.email == "test@example.com"
        assert model.role_codes is None

    def test_valid_model_with_empty_roles(self):
        """Test creating valid model with empty role_codes list."""
        from lys.apps.user_role.modules.user.models import CreateUserWithRolesInputModel

        model = CreateUserWithRolesInputModel(
            email="test@example.com",
            password="password123",
            language_code="en",
            role_codes=[]
        )

        assert model.role_codes == []


class TestUpdateUserRolesInputModel:
    """Tests for UpdateUserRolesInputModel."""

    def test_inherits_from_base_model(self):
        """Test that UpdateUserRolesInputModel inherits from BaseModel."""
        from lys.apps.user_role.modules.user.models import UpdateUserRolesInputModel
        from pydantic import BaseModel

        assert issubclass(UpdateUserRolesInputModel, BaseModel)

    def test_has_role_codes_field(self):
        """Test that model has role_codes field."""
        from lys.apps.user_role.modules.user.models import UpdateUserRolesInputModel

        assert "role_codes" in UpdateUserRolesInputModel.model_fields

    def test_role_codes_field_is_required(self):
        """Test that role_codes field is required."""
        from lys.apps.user_role.modules.user.models import UpdateUserRolesInputModel

        field_info = UpdateUserRolesInputModel.model_fields["role_codes"]
        # Required fields have is_required() == True
        assert field_info.is_required()

    def test_valid_model_with_roles(self):
        """Test creating valid model with role_codes."""
        from lys.apps.user_role.modules.user.models import UpdateUserRolesInputModel

        model = UpdateUserRolesInputModel(role_codes=["admin", "user"])

        assert model.role_codes == ["admin", "user"]

    def test_valid_model_with_empty_roles(self):
        """Test creating valid model with empty role_codes list."""
        from lys.apps.user_role.modules.user.models import UpdateUserRolesInputModel

        model = UpdateUserRolesInputModel(role_codes=[])

        assert model.role_codes == []

    def test_invalid_model_missing_role_codes(self):
        """Test that model validation fails without role_codes."""
        from lys.apps.user_role.modules.user.models import UpdateUserRolesInputModel

        with pytest.raises(ValidationError):
            UpdateUserRolesInputModel()
