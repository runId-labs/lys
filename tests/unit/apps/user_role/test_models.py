"""
Unit tests for user_role Pydantic models.

Tests the fixture models used for role configuration.
"""

import pytest
from pydantic import ValidationError


class TestRoleFixturesModel:
    """Tests for RoleFixturesModel."""

    def test_model_inherits_from_parametric_entity_fixtures_model(self):
        """Test that RoleFixturesModel inherits correctly."""
        from lys.apps.user_role.models import RoleFixturesModel
        from lys.core.models.fixtures import ParametricEntityFixturesModel

        assert issubclass(RoleFixturesModel, ParametricEntityFixturesModel)

    def test_attributes_model_has_enabled_field(self):
        """Test that AttributesModel has enabled field."""
        from lys.apps.user_role.models import RoleFixturesModel

        # Check the AttributesModel has the enabled field
        assert "enabled" in RoleFixturesModel.AttributesModel.model_fields

    def test_attributes_model_has_role_webservices_field(self):
        """Test that AttributesModel has role_webservices field."""
        from lys.apps.user_role.models import RoleFixturesModel

        assert "role_webservices" in RoleFixturesModel.AttributesModel.model_fields

    def test_valid_role_fixtures_model(self):
        """Test creating a valid RoleFixturesModel."""
        from lys.apps.user_role.models import RoleFixturesModel

        data = {
            "id": "admin_role",
            "attributes": {
                "enabled": True,
                "role_webservices": ["get_users", "update_user"],
                "labels": {"en": "Admin Role", "fr": "Rôle Admin"}
            }
        }

        model = RoleFixturesModel(**data)

        assert model.id == "admin_role"
        assert model.attributes.enabled is True
        assert model.attributes.role_webservices == ["get_users", "update_user"]

    def test_role_fixtures_model_with_empty_webservices(self):
        """Test RoleFixturesModel with empty webservices list."""
        from lys.apps.user_role.models import RoleFixturesModel

        data = {
            "id": "readonly_role",
            "attributes": {
                "enabled": True,
                "role_webservices": [],
                "labels": {"en": "Read Only"}
            }
        }

        model = RoleFixturesModel(**data)

        assert model.attributes.role_webservices == []

    def test_role_fixtures_model_disabled_role(self):
        """Test RoleFixturesModel with disabled role."""
        from lys.apps.user_role.models import RoleFixturesModel

        data = {
            "id": "deprecated_role",
            "attributes": {
                "enabled": False,
                "role_webservices": ["old_webservice"],
                "labels": {"en": "Deprecated"}
            }
        }

        model = RoleFixturesModel(**data)

        assert model.attributes.enabled is False
