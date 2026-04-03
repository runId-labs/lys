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


class TestStoredFileNode:
    """Tests for StoredFileNode."""

    def test_node_exists(self):
        """Test StoredFileNode class exists."""
        from lys.apps.file_management.modules.stored_file.nodes import StoredFileNode
        assert StoredFileNode is not None

    def test_node_inherits_from_entity_node(self):
        """Test StoredFileNode inherits from EntityNode."""
        from lys.apps.file_management.modules.stored_file.nodes import StoredFileNode
        from lys.core.graphql.nodes import EntityNode
        assert issubclass(StoredFileNode, EntityNode)

    def test_node_has_original_name_field(self):
        """Test StoredFileNode has original_name field."""
        from lys.apps.file_management.modules.stored_file.nodes import StoredFileNode
        assert "original_name" in StoredFileNode.__annotations__

    def test_node_has_size_field(self):
        """Test StoredFileNode has size field."""
        from lys.apps.file_management.modules.stored_file.nodes import StoredFileNode
        assert "size" in StoredFileNode.__annotations__

    def test_node_has_mime_type_field(self):
        """Test StoredFileNode has mime_type field."""
        from lys.apps.file_management.modules.stored_file.nodes import StoredFileNode
        assert "mime_type" in StoredFileNode.__annotations__

    def test_node_has_type_id_field(self):
        """Test StoredFileNode has type_id field."""
        from lys.apps.file_management.modules.stored_file.nodes import StoredFileNode
        assert "type_id" in StoredFileNode.__annotations__

    def test_node_has_created_at_field(self):
        """Test StoredFileNode has created_at field."""
        from lys.apps.file_management.modules.stored_file.nodes import StoredFileNode
        assert "created_at" in StoredFileNode.__annotations__

    def test_node_has_updated_at_field(self):
        """Test StoredFileNode has updated_at field."""
        from lys.apps.file_management.modules.stored_file.nodes import StoredFileNode
        assert "updated_at" in StoredFileNode.__annotations__

    def test_node_has_entity_private_field(self):
        """Test StoredFileNode has _entity private field."""
        from lys.apps.file_management.modules.stored_file.nodes import StoredFileNode
        assert "_entity" in StoredFileNode.__annotations__
