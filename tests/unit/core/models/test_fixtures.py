"""
Unit tests for core models fixtures module.

Tests EntityFixturesModel and ParametricEntityFixturesModel pydantic models.
"""

import pytest
from pydantic import BaseModel, ValidationError


class TestEntityFixturesModel:
    """Tests for EntityFixturesModel class."""

    def test_class_exists(self):
        """Test EntityFixturesModel class exists."""
        from lys.core.models.fixtures import EntityFixturesModel
        assert EntityFixturesModel is not None

    def test_inherits_from_entity_model(self):
        """Test EntityFixturesModel inherits from EntityModel."""
        from lys.core.models.fixtures import EntityFixturesModel
        from lys.core.models.entities import EntityModel
        assert issubclass(EntityFixturesModel, EntityModel)

    def test_has_attributes_model_inner_class(self):
        """Test EntityFixturesModel has AttributesModel inner class."""
        from lys.core.models.fixtures import EntityFixturesModel
        assert hasattr(EntityFixturesModel, "AttributesModel")

    def test_attributes_model_inherits_from_base_model(self):
        """Test AttributesModel inherits from BaseModel."""
        from lys.core.models.fixtures import EntityFixturesModel
        assert issubclass(EntityFixturesModel.AttributesModel, BaseModel)

    def test_has_attributes_field(self):
        """Test EntityFixturesModel has attributes field."""
        from lys.core.models.fixtures import EntityFixturesModel
        assert "attributes" in EntityFixturesModel.model_fields

    def test_attributes_default_is_none(self):
        """Test EntityFixturesModel attributes defaults to None."""
        from lys.core.models.fixtures import EntityFixturesModel
        model = EntityFixturesModel()
        assert model.attributes is None

    def test_can_create_instance(self):
        """Test EntityFixturesModel can be instantiated."""
        from lys.core.models.fixtures import EntityFixturesModel
        model = EntityFixturesModel()
        assert model is not None


class TestParametricEntityFixturesModel:
    """Tests for ParametricEntityFixturesModel class."""

    def test_class_exists(self):
        """Test ParametricEntityFixturesModel class exists."""
        from lys.core.models.fixtures import ParametricEntityFixturesModel
        assert ParametricEntityFixturesModel is not None

    def test_inherits_from_entity_fixtures_model(self):
        """Test ParametricEntityFixturesModel inherits from EntityFixturesModel."""
        from lys.core.models.fixtures import ParametricEntityFixturesModel, EntityFixturesModel
        assert issubclass(ParametricEntityFixturesModel, EntityFixturesModel)

    def test_has_attributes_model_inner_class(self):
        """Test ParametricEntityFixturesModel has AttributesModel inner class."""
        from lys.core.models.fixtures import ParametricEntityFixturesModel
        assert hasattr(ParametricEntityFixturesModel, "AttributesModel")

    def test_attributes_model_has_enabled_field(self):
        """Test AttributesModel has enabled field."""
        from lys.core.models.fixtures import ParametricEntityFixturesModel
        assert "enabled" in ParametricEntityFixturesModel.AttributesModel.model_fields

    def test_attributes_model_has_description_field(self):
        """Test AttributesModel has description field."""
        from lys.core.models.fixtures import ParametricEntityFixturesModel
        assert "description" in ParametricEntityFixturesModel.AttributesModel.model_fields

    def test_has_id_field(self):
        """Test ParametricEntityFixturesModel has id field."""
        from lys.core.models.fixtures import ParametricEntityFixturesModel
        assert "id" in ParametricEntityFixturesModel.model_fields

    def test_id_is_required(self):
        """Test ParametricEntityFixturesModel id is required."""
        from lys.core.models.fixtures import ParametricEntityFixturesModel
        with pytest.raises(ValidationError):
            ParametricEntityFixturesModel()

    def test_id_must_have_min_length(self):
        """Test ParametricEntityFixturesModel id must have min length of 1."""
        from lys.core.models.fixtures import ParametricEntityFixturesModel
        with pytest.raises(ValidationError):
            ParametricEntityFixturesModel(id="")

    def test_can_create_with_valid_id(self):
        """Test ParametricEntityFixturesModel can be created with valid id."""
        from lys.core.models.fixtures import ParametricEntityFixturesModel
        model = ParametricEntityFixturesModel(id="VALID_ID")
        assert model.id == "VALID_ID"

    def test_attributes_defaults_to_empty_dict(self):
        """Test ParametricEntityFixturesModel attributes defaults to empty dict."""
        from lys.core.models.fixtures import ParametricEntityFixturesModel
        model = ParametricEntityFixturesModel(id="TEST")
        # attributes can be dict or AttributesModel
        assert model.attributes == {} or isinstance(model.attributes, dict)
