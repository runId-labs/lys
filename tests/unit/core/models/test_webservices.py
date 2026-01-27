"""
Unit tests for core models webservices module.

Tests WebserviceFixturesModel pydantic model.
"""

import pytest
from pydantic import ValidationError


class TestWebserviceFixturesModel:
    """Tests for WebserviceFixturesModel class."""

    def test_class_exists(self):
        """Test WebserviceFixturesModel class exists."""
        from lys.core.models.webservices import WebserviceFixturesModel
        assert WebserviceFixturesModel is not None

    def test_inherits_from_parametric_entity_fixtures_model(self):
        """Test WebserviceFixturesModel inherits from ParametricEntityFixturesModel."""
        from lys.core.models.webservices import WebserviceFixturesModel
        from lys.core.models.fixtures import ParametricEntityFixturesModel
        assert issubclass(WebserviceFixturesModel, ParametricEntityFixturesModel)

    def test_has_attributes_model_inner_class(self):
        """Test WebserviceFixturesModel has AttributesModel inner class."""
        from lys.core.models.webservices import WebserviceFixturesModel
        assert hasattr(WebserviceFixturesModel, "AttributesModel")

    def test_attributes_model_has_public_type_field(self):
        """Test AttributesModel has public_type field."""
        from lys.core.models.webservices import WebserviceFixturesModel
        assert "public_type" in WebserviceFixturesModel.AttributesModel.model_fields

    def test_attributes_model_has_is_licenced_field(self):
        """Test AttributesModel has is_licenced field."""
        from lys.core.models.webservices import WebserviceFixturesModel
        assert "is_licenced" in WebserviceFixturesModel.AttributesModel.model_fields

    def test_attributes_model_has_enabled_field(self):
        """Test AttributesModel has enabled field."""
        from lys.core.models.webservices import WebserviceFixturesModel
        assert "enabled" in WebserviceFixturesModel.AttributesModel.model_fields

    def test_attributes_model_has_access_levels_field(self):
        """Test AttributesModel has access_levels field."""
        from lys.core.models.webservices import WebserviceFixturesModel
        assert "access_levels" in WebserviceFixturesModel.AttributesModel.model_fields

    def test_attributes_model_has_operation_type_field(self):
        """Test AttributesModel has operation_type field."""
        from lys.core.models.webservices import WebserviceFixturesModel
        assert "operation_type" in WebserviceFixturesModel.AttributesModel.model_fields

    def test_attributes_model_has_ai_tool_field(self):
        """Test AttributesModel has ai_tool field."""
        from lys.core.models.webservices import WebserviceFixturesModel
        assert "ai_tool" in WebserviceFixturesModel.AttributesModel.model_fields

    def test_has_id_field(self):
        """Test WebserviceFixturesModel has id field."""
        from lys.core.models.webservices import WebserviceFixturesModel
        assert "id" in WebserviceFixturesModel.model_fields

    def test_id_is_required(self):
        """Test WebserviceFixturesModel id is required."""
        from lys.core.models.webservices import WebserviceFixturesModel
        with pytest.raises(ValidationError):
            WebserviceFixturesModel(
                attributes={
                    "public_type": "NO_LIMITATION",
                    "is_licenced": False,
                    "enabled": True,
                    "access_levels": ["CONNECTED"]
                }
            )

    def test_id_must_have_min_length(self):
        """Test WebserviceFixturesModel id must have min length of 1."""
        from lys.core.models.webservices import WebserviceFixturesModel
        with pytest.raises(ValidationError):
            WebserviceFixturesModel(
                id="",
                attributes={
                    "public_type": "NO_LIMITATION",
                    "is_licenced": False,
                    "enabled": True,
                    "access_levels": ["CONNECTED"]
                }
            )

    def test_can_create_with_valid_data(self):
        """Test WebserviceFixturesModel can be created with valid data."""
        from lys.core.models.webservices import WebserviceFixturesModel
        model = WebserviceFixturesModel(
            id="test_webservice",
            attributes={
                "public_type": "NO_LIMITATION",
                "is_licenced": False,
                "enabled": True,
                "access_levels": ["CONNECTED"]
            }
        )
        assert model.id == "test_webservice"
        assert model.attributes.public_type == "NO_LIMITATION"
        assert model.attributes.is_licenced is False
        assert model.attributes.enabled is True
        assert model.attributes.access_levels == ["CONNECTED"]

    def test_operation_type_is_optional(self):
        """Test operation_type field is optional."""
        from lys.core.models.webservices import WebserviceFixturesModel
        model = WebserviceFixturesModel(
            id="test_ws",
            attributes={
                "public_type": "NO_LIMITATION",
                "is_licenced": False,
                "enabled": True,
                "access_levels": []
            }
        )
        assert model.attributes.operation_type is None

    def test_ai_tool_is_optional(self):
        """Test ai_tool field is optional."""
        from lys.core.models.webservices import WebserviceFixturesModel
        model = WebserviceFixturesModel(
            id="test_ws",
            attributes={
                "public_type": "NO_LIMITATION",
                "is_licenced": False,
                "enabled": True,
                "access_levels": []
            }
        )
        assert model.attributes.ai_tool is None

    def test_ai_tool_can_be_dict(self):
        """Test ai_tool field can be a dictionary."""
        from lys.core.models.webservices import WebserviceFixturesModel
        ai_tool_config = {
            "name": "test_tool",
            "description": "A test tool",
            "parameters": {}
        }
        model = WebserviceFixturesModel(
            id="test_ws",
            attributes={
                "public_type": "NO_LIMITATION",
                "is_licenced": False,
                "enabled": True,
                "access_levels": [],
                "ai_tool": ai_tool_config
            }
        )
        assert model.attributes.ai_tool == ai_tool_config
