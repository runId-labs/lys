"""
Unit tests for organization user Pydantic models.

Tests input models for client user creation.
"""

import pytest
from pydantic import ValidationError


class TestCreateClientUserInputModel:
    """Tests for CreateClientUserInputModel."""

    def test_model_inherits_from_create_user_with_roles_input_model(self):
        """Test that CreateClientUserInputModel inherits from CreateUserWithRolesInputModel."""
        from lys.apps.organization.modules.user.models import CreateClientUserInputModel
        from lys.apps.user_role.modules.user.models import CreateUserWithRolesInputModel

        assert issubclass(CreateClientUserInputModel, CreateUserWithRolesInputModel)

    def test_has_client_id_field(self):
        """Test that model has client_id field."""
        from lys.apps.organization.modules.user.models import CreateClientUserInputModel

        assert "client_id" in CreateClientUserInputModel.model_fields

    def test_client_id_is_required(self):
        """Test that client_id field is required."""
        from lys.apps.organization.modules.user.models import CreateClientUserInputModel

        field_info = CreateClientUserInputModel.model_fields["client_id"]
        assert field_info.is_required()

    def test_has_client_id_validator(self):
        """Test that model has client_id validator."""
        from lys.apps.organization.modules.user.models import CreateClientUserInputModel

        # Check that the validator exists
        validators = CreateClientUserInputModel.__pydantic_decorators__.field_validators
        assert "validate_client_id" in validators
