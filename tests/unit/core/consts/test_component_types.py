"""
Unit tests for core consts component_types module.

Tests AppComponentTypeEnum enumeration.
"""

import pytest
from enum import Enum


class TestAppComponentTypeEnum:
    """Tests for AppComponentTypeEnum."""

    def test_enum_exists(self):
        """Test AppComponentTypeEnum class exists."""
        from lys.core.consts.component_types import AppComponentTypeEnum
        assert AppComponentTypeEnum is not None

    def test_enum_inherits_from_str_enum(self):
        """Test AppComponentTypeEnum inherits from str and Enum."""
        from lys.core.consts.component_types import AppComponentTypeEnum
        assert issubclass(AppComponentTypeEnum, str)
        assert issubclass(AppComponentTypeEnum, Enum)

    def test_entities_value(self):
        """Test ENTITIES enum value."""
        from lys.core.consts.component_types import AppComponentTypeEnum
        assert AppComponentTypeEnum.ENTITIES.value == "entities"

    def test_services_value(self):
        """Test SERVICES enum value."""
        from lys.core.consts.component_types import AppComponentTypeEnum
        assert AppComponentTypeEnum.SERVICES.value == "services"

    def test_fixtures_value(self):
        """Test FIXTURES enum value."""
        from lys.core.consts.component_types import AppComponentTypeEnum
        assert AppComponentTypeEnum.FIXTURES.value == "fixtures"

    def test_nodes_value(self):
        """Test NODES enum value."""
        from lys.core.consts.component_types import AppComponentTypeEnum
        assert AppComponentTypeEnum.NODES.value == "nodes"

    def test_webservices_value(self):
        """Test WEBSERVICES enum value."""
        from lys.core.consts.component_types import AppComponentTypeEnum
        assert AppComponentTypeEnum.WEBSERVICES.value == "webservices"

    def test_all_values_are_lowercase(self):
        """Test all enum values are lowercase."""
        from lys.core.consts.component_types import AppComponentTypeEnum
        for member in AppComponentTypeEnum:
            assert member.value == member.value.lower()

    def test_enum_has_five_members(self):
        """Test enum has exactly 5 members."""
        from lys.core.consts.component_types import AppComponentTypeEnum
        assert len(AppComponentTypeEnum) == 5

    def test_enum_values_are_unique(self):
        """Test all enum values are unique."""
        from lys.core.consts.component_types import AppComponentTypeEnum
        values = [member.value for member in AppComponentTypeEnum]
        assert len(values) == len(set(values))

    def test_can_compare_with_string(self):
        """Test enum can be compared with string."""
        from lys.core.consts.component_types import AppComponentTypeEnum
        assert AppComponentTypeEnum.ENTITIES == "entities"
        assert AppComponentTypeEnum.SERVICES == "services"
