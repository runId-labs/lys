"""
Unit tests for core consts environments module.

Tests EnvironmentEnum enumeration.
"""

import pytest
from enum import Enum


class TestEnvironmentEnum:
    """Tests for EnvironmentEnum."""

    def test_enum_exists(self):
        """Test EnvironmentEnum class exists."""
        from lys.core.consts.environments import EnvironmentEnum
        assert EnvironmentEnum is not None

    def test_enum_inherits_from_str_enum(self):
        """Test EnvironmentEnum inherits from str and Enum."""
        from lys.core.consts.environments import EnvironmentEnum
        assert issubclass(EnvironmentEnum, str)
        assert issubclass(EnvironmentEnum, Enum)

    def test_dev_value(self):
        """Test DEV enum value."""
        from lys.core.consts.environments import EnvironmentEnum
        assert EnvironmentEnum.DEV.value == "dev"

    def test_preprod_value(self):
        """Test PREPROD enum value."""
        from lys.core.consts.environments import EnvironmentEnum
        assert EnvironmentEnum.PREPROD.value == "preprod"

    def test_prod_value(self):
        """Test PROD enum value."""
        from lys.core.consts.environments import EnvironmentEnum
        assert EnvironmentEnum.PROD.value == "prod"

    def test_demo_value(self):
        """Test DEMO enum value."""
        from lys.core.consts.environments import EnvironmentEnum
        assert EnvironmentEnum.DEMO.value == "demo"

    def test_all_values_are_lowercase(self):
        """Test all enum values are lowercase."""
        from lys.core.consts.environments import EnvironmentEnum
        for member in EnvironmentEnum:
            assert member.value == member.value.lower()

    def test_enum_has_four_members(self):
        """Test enum has exactly 4 members."""
        from lys.core.consts.environments import EnvironmentEnum
        assert len(EnvironmentEnum) == 4

    def test_enum_values_are_unique(self):
        """Test all enum values are unique."""
        from lys.core.consts.environments import EnvironmentEnum
        values = [member.value for member in EnvironmentEnum]
        assert len(values) == len(set(values))

    def test_can_compare_with_string(self):
        """Test enum can be compared with string."""
        from lys.core.consts.environments import EnvironmentEnum
        assert EnvironmentEnum.DEV == "dev"
        assert EnvironmentEnum.PROD == "prod"

    def test_enum_has_docstring(self):
        """Test enum has a docstring."""
        from lys.core.consts.environments import EnvironmentEnum
        assert EnvironmentEnum.__doc__ is not None
