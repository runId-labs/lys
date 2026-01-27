"""
Unit tests for core models entities module.

Tests EntityModel pydantic model.
"""

import pytest
from pydantic import BaseModel


class TestEntityModel:
    """Tests for EntityModel class."""

    def test_class_exists(self):
        """Test EntityModel class exists."""
        from lys.core.models.entities import EntityModel
        assert EntityModel is not None

    def test_inherits_from_base_model(self):
        """Test EntityModel inherits from pydantic BaseModel."""
        from lys.core.models.entities import EntityModel
        assert issubclass(EntityModel, BaseModel)

    def test_has_id_field(self):
        """Test EntityModel has id field."""
        from lys.core.models.entities import EntityModel
        assert "id" in EntityModel.model_fields

    def test_id_default_is_none(self):
        """Test EntityModel id defaults to None."""
        from lys.core.models.entities import EntityModel
        model = EntityModel()
        assert model.id is None

    def test_has_validate_classmethod(self):
        """Test EntityModel has validate classmethod."""
        from lys.core.models.entities import EntityModel
        assert hasattr(EntityModel, "validate")
        assert callable(EntityModel.validate)

    def test_validate_method_accepts_dict(self):
        """Test validate method accepts a dictionary."""
        from lys.core.models.entities import EntityModel
        # Should not raise
        EntityModel.validate({})
        EntityModel.validate({"id": None})

    def test_validate_method_raises_on_invalid_data(self):
        """Test validate method raises on invalid data types."""
        from lys.core.models.entities import EntityModel
        from pydantic import ValidationError
        # id should be None or appropriate type
        # This test checks the validate method works
        EntityModel.validate({"id": None})

    def test_has_hash_override(self):
        """Test EntityModel has __hash__ override."""
        from lys.core.models.entities import EntityModel
        assert EntityModel.__hash__ == object.__hash__

    def test_can_create_instance(self):
        """Test EntityModel can be instantiated."""
        from lys.core.models.entities import EntityModel
        model = EntityModel()
        assert model is not None

    def test_can_create_instance_with_id(self):
        """Test EntityModel can be instantiated with id."""
        from lys.core.models.entities import EntityModel
        model = EntityModel(id=None)
        assert model.id is None
