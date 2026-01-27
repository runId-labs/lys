"""
Unit tests for organization client Pydantic models.

Tests input models for client creation and update.
"""

import pytest
from pydantic import ValidationError


class TestCreateClientInputModel:
    """Tests for CreateClientInputModel."""

    def test_model_inherits_from_create_user_input_model(self):
        """Test that CreateClientInputModel inherits from CreateUserInputModel."""
        from lys.apps.organization.modules.client.models import CreateClientInputModel
        from lys.apps.user_auth.modules.user.models import CreateUserInputModel

        assert issubclass(CreateClientInputModel, CreateUserInputModel)

    def test_has_client_name_field(self):
        """Test that model has client_name field."""
        from lys.apps.organization.modules.client.models import CreateClientInputModel

        assert "client_name" in CreateClientInputModel.model_fields

    def test_client_name_is_required(self):
        """Test that client_name field is required."""
        from lys.apps.organization.modules.client.models import CreateClientInputModel

        field_info = CreateClientInputModel.model_fields["client_name"]
        assert field_info.is_required()

    def test_valid_model(self):
        """Test creating valid CreateClientInputModel."""
        from lys.apps.organization.modules.client.models import CreateClientInputModel

        model = CreateClientInputModel(
            client_name="Test Company",
            email="test@example.com",
            password="password123",
            language_code="en"
        )

        assert model.client_name == "Test Company"
        assert model.email == "test@example.com"

    def test_client_name_strips_whitespace(self):
        """Test that client_name validator strips whitespace."""
        from lys.apps.organization.modules.client.models import CreateClientInputModel

        model = CreateClientInputModel(
            client_name="  Test Company  ",
            email="test@example.com",
            password="password123",
            language_code="en"
        )

        assert model.client_name == "Test Company"

    def test_empty_client_name_raises_error(self):
        """Test that empty client_name raises validation error."""
        from lys.apps.organization.modules.client.models import CreateClientInputModel

        with pytest.raises(ValidationError):
            CreateClientInputModel(
                client_name="   ",
                email="test@example.com",
                password="password123",
                language_code="en"
            )

    def test_client_name_max_length(self):
        """Test that client_name respects max length."""
        from lys.apps.organization.modules.client.models import CreateClientInputModel

        field_info = CreateClientInputModel.model_fields["client_name"]
        # In Pydantic v2, max_length constraint is in metadata with MaxLen type
        max_len_constraint = [m for m in field_info.metadata if hasattr(m, "max_length")]
        assert len(max_len_constraint) > 0
        assert max_len_constraint[0].max_length == 255


class TestUpdateClientInputModel:
    """Tests for UpdateClientInputModel."""

    def test_inherits_from_base_model(self):
        """Test that UpdateClientInputModel inherits from BaseModel."""
        from lys.apps.organization.modules.client.models import UpdateClientInputModel
        from pydantic import BaseModel

        assert issubclass(UpdateClientInputModel, BaseModel)

    def test_has_name_field(self):
        """Test that model has name field."""
        from lys.apps.organization.modules.client.models import UpdateClientInputModel

        assert "name" in UpdateClientInputModel.model_fields

    def test_name_is_required(self):
        """Test that name field is required."""
        from lys.apps.organization.modules.client.models import UpdateClientInputModel

        field_info = UpdateClientInputModel.model_fields["name"]
        assert field_info.is_required()

    def test_valid_model(self):
        """Test creating valid UpdateClientInputModel."""
        from lys.apps.organization.modules.client.models import UpdateClientInputModel

        model = UpdateClientInputModel(name="Updated Company")

        assert model.name == "Updated Company"

    def test_name_strips_whitespace(self):
        """Test that name validator strips whitespace."""
        from lys.apps.organization.modules.client.models import UpdateClientInputModel

        model = UpdateClientInputModel(name="  Updated Company  ")

        assert model.name == "Updated Company"

    def test_empty_name_raises_error(self):
        """Test that empty name raises validation error."""
        from lys.apps.organization.modules.client.models import UpdateClientInputModel

        with pytest.raises(ValidationError):
            UpdateClientInputModel(name="   ")

    def test_name_max_length(self):
        """Test that name respects max length."""
        from lys.apps.organization.modules.client.models import UpdateClientInputModel

        field_info = UpdateClientInputModel.model_fields["name"]
        # In Pydantic v2, max_length constraint is in metadata with MaxLen type
        max_len_constraint = [m for m in field_info.metadata if hasattr(m, "max_length")]
        assert len(max_len_constraint) > 0
        assert max_len_constraint[0].max_length == 255
