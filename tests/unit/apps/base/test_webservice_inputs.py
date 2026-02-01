"""
Unit tests for base webservice module inputs.

Tests Strawberry input types.
"""

import pytest


class TestWebserviceAttributesInput:
    """Tests for WebserviceAttributesInput."""

    def test_input_exists(self):
        """Test WebserviceAttributesInput class exists."""
        from lys.apps.base.modules.webservice.inputs import WebserviceAttributesInput
        assert WebserviceAttributesInput is not None

    def test_input_has_strawberry_definition(self):
        """Test WebserviceAttributesInput is a Strawberry input type."""
        from lys.apps.base.modules.webservice.inputs import WebserviceAttributesInput
        assert hasattr(WebserviceAttributesInput, "__strawberry_definition__")

    def test_input_is_input_type(self):
        """Test WebserviceAttributesInput is a Strawberry input type."""
        from lys.apps.base.modules.webservice.inputs import WebserviceAttributesInput
        definition = WebserviceAttributesInput.__strawberry_definition__
        assert definition.is_input is True

    def test_input_has_fields_in_definition(self):
        """Test WebserviceAttributesInput has fields in strawberry definition."""
        from lys.apps.base.modules.webservice.inputs import WebserviceAttributesInput
        definition = WebserviceAttributesInput.__strawberry_definition__
        field_names = [f.name for f in definition.fields]
        # Check that expected fields exist
        assert "public_type" in field_names or "publicType" in field_names
        assert "is_licenced" in field_names or "isLicenced" in field_names
        assert "enabled" in field_names
        assert "access_levels" in field_names or "accessLevels" in field_names
        assert "operation_type" in field_names or "operationType" in field_names

    def test_input_is_pydantic_based(self):
        """Test WebserviceAttributesInput is based on a Pydantic model."""
        from lys.apps.base.modules.webservice.inputs import WebserviceAttributesInput
        # Strawberry pydantic inputs have to_pydantic method
        assert hasattr(WebserviceAttributesInput, "to_pydantic")


class TestWebserviceFixturesInput:
    """Tests for WebserviceFixturesInput."""

    def test_input_exists(self):
        """Test WebserviceFixturesInput class exists."""
        from lys.apps.base.modules.webservice.inputs import WebserviceFixturesInput
        assert WebserviceFixturesInput is not None

    def test_input_has_strawberry_definition(self):
        """Test WebserviceFixturesInput is a Strawberry input type."""
        from lys.apps.base.modules.webservice.inputs import WebserviceFixturesInput
        assert hasattr(WebserviceFixturesInput, "__strawberry_definition__")

    def test_input_is_input_type(self):
        """Test WebserviceFixturesInput is a Strawberry input type."""
        from lys.apps.base.modules.webservice.inputs import WebserviceFixturesInput
        definition = WebserviceFixturesInput.__strawberry_definition__
        assert definition.is_input is True

    def test_input_has_id_field_in_definition(self):
        """Test WebserviceFixturesInput has id field in definition."""
        from lys.apps.base.modules.webservice.inputs import WebserviceFixturesInput
        definition = WebserviceFixturesInput.__strawberry_definition__
        field_names = [f.name for f in definition.fields]
        assert "id" in field_names

    def test_input_has_attributes_field_in_definition(self):
        """Test WebserviceFixturesInput has attributes field in definition."""
        from lys.apps.base.modules.webservice.inputs import WebserviceFixturesInput
        definition = WebserviceFixturesInput.__strawberry_definition__
        field_names = [f.name for f in definition.fields]
        assert "attributes" in field_names

    def test_input_has_to_pydantic_method(self):
        """Test WebserviceFixturesInput can convert to Pydantic model."""
        from lys.apps.base.modules.webservice.inputs import WebserviceFixturesInput
        # Strawberry pydantic inputs have this method
        assert hasattr(WebserviceFixturesInput, "to_pydantic")
