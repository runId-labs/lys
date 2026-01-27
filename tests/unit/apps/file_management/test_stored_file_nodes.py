"""
Unit tests for file_management stored_file module nodes.

Tests GraphQL node structure.
"""

import pytest

# Skip all tests if aioboto3 is not installed
pytest.importorskip("aioboto3", reason="aioboto3 not installed")


class TestPresignedUploadUrlNode:
    """Tests for PresignedUploadUrlNode."""

    def test_node_exists(self):
        """Test PresignedUploadUrlNode class exists."""
        from lys.apps.file_management.modules.stored_file.nodes import PresignedUploadUrlNode
        assert PresignedUploadUrlNode is not None

    def test_node_inherits_from_service_node(self):
        """Test PresignedUploadUrlNode inherits from ServiceNode."""
        from lys.apps.file_management.modules.stored_file.nodes import PresignedUploadUrlNode
        from lys.core.graphql.nodes import ServiceNode
        assert issubclass(PresignedUploadUrlNode, ServiceNode)

    def test_node_has_presigned_url_field(self):
        """Test PresignedUploadUrlNode has presigned_url field."""
        from lys.apps.file_management.modules.stored_file.nodes import PresignedUploadUrlNode
        assert "presigned_url" in PresignedUploadUrlNode.__annotations__

    def test_node_has_object_key_field(self):
        """Test PresignedUploadUrlNode has object_key field."""
        from lys.apps.file_management.modules.stored_file.nodes import PresignedUploadUrlNode
        assert "object_key" in PresignedUploadUrlNode.__annotations__
