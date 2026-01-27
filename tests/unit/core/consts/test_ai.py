"""
Unit tests for core consts ai module.

Tests ToolRiskLevel enumeration.
"""

import pytest
from enum import Enum


class TestToolRiskLevelEnum:
    """Tests for ToolRiskLevel enum."""

    def test_enum_exists(self):
        """Test ToolRiskLevel class exists."""
        from lys.core.consts.ai import ToolRiskLevel
        assert ToolRiskLevel is not None

    def test_enum_inherits_from_enum(self):
        """Test ToolRiskLevel inherits from Enum."""
        from lys.core.consts.ai import ToolRiskLevel
        assert issubclass(ToolRiskLevel, Enum)

    def test_read_value(self):
        """Test READ enum value."""
        from lys.core.consts.ai import ToolRiskLevel
        assert ToolRiskLevel.READ.value == "read"

    def test_create_value(self):
        """Test CREATE enum value."""
        from lys.core.consts.ai import ToolRiskLevel
        assert ToolRiskLevel.CREATE.value == "create"

    def test_update_value(self):
        """Test UPDATE enum value."""
        from lys.core.consts.ai import ToolRiskLevel
        assert ToolRiskLevel.UPDATE.value == "update"

    def test_delete_value(self):
        """Test DELETE enum value."""
        from lys.core.consts.ai import ToolRiskLevel
        assert ToolRiskLevel.DELETE.value == "delete"

    def test_all_values_are_lowercase(self):
        """Test all enum values are lowercase."""
        from lys.core.consts.ai import ToolRiskLevel
        for member in ToolRiskLevel:
            assert member.value == member.value.lower()

    def test_enum_has_four_members(self):
        """Test enum has exactly 4 members."""
        from lys.core.consts.ai import ToolRiskLevel
        assert len(ToolRiskLevel) == 4

    def test_enum_values_are_unique(self):
        """Test all enum values are unique."""
        from lys.core.consts.ai import ToolRiskLevel
        values = [member.value for member in ToolRiskLevel]
        assert len(values) == len(set(values))

    def test_enum_has_docstring(self):
        """Test enum has a docstring."""
        from lys.core.consts.ai import ToolRiskLevel
        assert ToolRiskLevel.__doc__ is not None

    def test_read_is_safe_level(self):
        """Test READ is the safe level (no confirmation needed)."""
        from lys.core.consts.ai import ToolRiskLevel
        # READ is for safe operations
        assert ToolRiskLevel.READ.value == "read"

    def test_crud_operations_present(self):
        """Test all CRUD operations are present."""
        from lys.core.consts.ai import ToolRiskLevel
        operations = {member.value for member in ToolRiskLevel}
        assert "read" in operations
        assert "create" in operations
        assert "update" in operations
        assert "delete" in operations
