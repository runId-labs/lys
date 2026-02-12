"""
Unit tests for core utils generic module.

Tests resolve_service_name_from_generic and replace_node_in_annotation.
"""
from typing import Optional, List, Union
from unittest.mock import MagicMock

from lys.core.utils.generic import resolve_service_name_from_generic, replace_node_in_annotation


class TestReplaceNodeInAnnotation:
    """Tests for replace_node_in_annotation function."""

    def test_string_annotation_in_registry(self):
        """Test that a string annotation matching a registry key is replaced."""
        registry = {"UserNode": "ReplacedUserNode"}
        result = replace_node_in_annotation("UserNode", registry)
        assert result == "ReplacedUserNode"

    def test_string_annotation_not_in_registry(self):
        """Test that a string annotation not in registry is returned as-is."""
        registry = {"UserNode": "ReplacedUserNode"}
        result = replace_node_in_annotation("OtherNode", registry)
        assert result == "OtherNode"

    def test_direct_class_reference_in_registry(self):
        """Test that a direct class reference in registry is replaced."""
        class UserNode:
            pass

        class ReplacedNode:
            pass

        registry = {"UserNode": ReplacedNode}
        result = replace_node_in_annotation(UserNode, registry)
        assert result is ReplacedNode

    def test_direct_class_reference_not_in_registry(self):
        """Test that a direct class reference not in registry is returned as-is."""
        class SomeNode:
            pass

        registry = {"UserNode": "ReplacedUserNode"}
        result = replace_node_in_annotation(SomeNode, registry)
        assert result is SomeNode

    def test_optional_type_with_replacement(self):
        """Test that Optional[NodeClass] replaces the inner type."""
        class UserNode:
            pass

        class ReplacedNode:
            pass

        registry = {"UserNode": ReplacedNode}
        annotation = Optional[UserNode]
        result = replace_node_in_annotation(annotation, registry)
        # The result should be Optional[ReplacedNode]
        assert ReplacedNode in getattr(result, "__args__", ())

    def test_list_type_with_replacement(self):
        """Test that List[NodeClass] replaces the inner type."""
        class UserNode:
            pass

        class ReplacedNode:
            pass

        registry = {"UserNode": ReplacedNode}
        annotation = List[UserNode]
        result = replace_node_in_annotation(annotation, registry)
        assert ReplacedNode in getattr(result, "__args__", ())

    def test_non_generic_non_class_returns_original(self):
        """Test that primitive types are returned as-is."""
        registry = {"UserNode": "ReplacedUserNode"}
        result = replace_node_in_annotation(int, registry)
        assert result is int

    def test_none_annotation_returns_original(self):
        """Test that None annotation is returned as-is."""
        registry = {"UserNode": "ReplacedUserNode"}
        result = replace_node_in_annotation(None, registry)
        assert result is None
