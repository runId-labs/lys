"""
Unit tests for file_management file_import module nodes.

Tests GraphQL node structure.
"""

import inspect

import pytest

# Skip all tests if aioboto3 is not installed
pytest.importorskip("aioboto3", reason="aioboto3 not installed")


class TestFileImportTypeNode:
    """Tests for FileImportTypeNode."""

    def test_node_exists(self):
        """Test FileImportTypeNode class exists."""
        from lys.apps.file_management.modules.file_import.nodes import FileImportTypeNode
        assert FileImportTypeNode is not None

    def test_node_inherits_from_entity_node(self):
        """Test FileImportTypeNode inherits from EntityNode."""
        from lys.apps.file_management.modules.file_import.nodes import FileImportTypeNode
        from lys.core.graphql.nodes import EntityNode
        assert issubclass(FileImportTypeNode, EntityNode)

    def test_node_has_id_field(self):
        """Test FileImportTypeNode has id field."""
        from lys.apps.file_management.modules.file_import.nodes import FileImportTypeNode
        assert "id" in FileImportTypeNode.__annotations__

    def test_node_has_enabled_field(self):
        """Test FileImportTypeNode has enabled field."""
        from lys.apps.file_management.modules.file_import.nodes import FileImportTypeNode
        assert "enabled" in FileImportTypeNode.__annotations__

    def test_node_has_description_field(self):
        """Test FileImportTypeNode has description field."""
        from lys.apps.file_management.modules.file_import.nodes import FileImportTypeNode
        assert "description" in FileImportTypeNode.__annotations__


class TestFileImportStatusNode:
    """Tests for FileImportStatusNode."""

    def test_node_exists(self):
        """Test FileImportStatusNode class exists."""
        from lys.apps.file_management.modules.file_import.nodes import FileImportStatusNode
        assert FileImportStatusNode is not None

    def test_node_inherits_from_entity_node(self):
        """Test FileImportStatusNode inherits from EntityNode."""
        from lys.apps.file_management.modules.file_import.nodes import FileImportStatusNode
        from lys.core.graphql.nodes import EntityNode
        assert issubclass(FileImportStatusNode, EntityNode)

    def test_node_has_id_field(self):
        """Test FileImportStatusNode has id field."""
        from lys.apps.file_management.modules.file_import.nodes import FileImportStatusNode
        assert "id" in FileImportStatusNode.__annotations__

    def test_node_has_enabled_field(self):
        """Test FileImportStatusNode has enabled field."""
        from lys.apps.file_management.modules.file_import.nodes import FileImportStatusNode
        assert "enabled" in FileImportStatusNode.__annotations__

    def test_node_has_description_field(self):
        """Test FileImportStatusNode has description field."""
        from lys.apps.file_management.modules.file_import.nodes import FileImportStatusNode
        assert "description" in FileImportStatusNode.__annotations__


class TestFileImportNode:
    """Tests for FileImportNode."""

    def test_node_exists(self):
        """Test FileImportNode class exists."""
        from lys.apps.file_management.modules.file_import.nodes import FileImportNode
        assert FileImportNode is not None

    def test_node_inherits_from_entity_node(self):
        """Test FileImportNode inherits from EntityNode."""
        from lys.apps.file_management.modules.file_import.nodes import FileImportNode
        from lys.core.graphql.nodes import EntityNode
        assert issubclass(FileImportNode, EntityNode)

    def test_node_has_client_id_field(self):
        """Test FileImportNode has client_id field."""
        from lys.apps.file_management.modules.file_import.nodes import FileImportNode
        assert "client_id" in FileImportNode.__annotations__

    def test_node_has_status_id_field(self):
        """Test FileImportNode has status_id field."""
        from lys.apps.file_management.modules.file_import.nodes import FileImportNode
        assert "status_id" in FileImportNode.__annotations__

    def test_node_has_type_id_field(self):
        """Test FileImportNode has type_id field."""
        from lys.apps.file_management.modules.file_import.nodes import FileImportNode
        assert "type_id" in FileImportNode.__annotations__

    def test_node_has_total_rows_field(self):
        """Test FileImportNode has total_rows field."""
        from lys.apps.file_management.modules.file_import.nodes import FileImportNode
        assert "total_rows" in FileImportNode.__annotations__

    def test_node_has_processed_rows_field(self):
        """Test FileImportNode has processed_rows field."""
        from lys.apps.file_management.modules.file_import.nodes import FileImportNode
        assert "processed_rows" in FileImportNode.__annotations__

    def test_node_has_success_rows_field(self):
        """Test FileImportNode has success_rows field."""
        from lys.apps.file_management.modules.file_import.nodes import FileImportNode
        assert "success_rows" in FileImportNode.__annotations__

    def test_node_has_error_rows_field(self):
        """Test FileImportNode has error_rows field."""
        from lys.apps.file_management.modules.file_import.nodes import FileImportNode
        assert "error_rows" in FileImportNode.__annotations__

    def test_node_has_extra_data_field(self):
        """Test FileImportNode has extra_data field."""
        from lys.apps.file_management.modules.file_import.nodes import FileImportNode
        assert "extra_data" in FileImportNode.__annotations__

    def test_node_has_started_at_field(self):
        """Test FileImportNode has started_at field."""
        from lys.apps.file_management.modules.file_import.nodes import FileImportNode
        assert "started_at" in FileImportNode.__annotations__

    def test_node_has_completed_at_field(self):
        """Test FileImportNode has completed_at field."""
        from lys.apps.file_management.modules.file_import.nodes import FileImportNode
        assert "completed_at" in FileImportNode.__annotations__

    def test_node_has_created_at_field(self):
        """Test FileImportNode has created_at field."""
        from lys.apps.file_management.modules.file_import.nodes import FileImportNode
        assert "created_at" in FileImportNode.__annotations__

    def test_node_has_entity_private_field(self):
        """Test FileImportNode has _entity private field."""
        from lys.apps.file_management.modules.file_import.nodes import FileImportNode
        assert "_entity" in FileImportNode.__annotations__

    def test_stored_file_resolver_exists(self):
        """Test FileImportNode has stored_file resolver method."""
        from lys.apps.file_management.modules.file_import.nodes import FileImportNode
        assert hasattr(FileImportNode, "stored_file")

    def test_type_resolver_exists(self):
        """Test FileImportNode has type resolver method."""
        from lys.apps.file_management.modules.file_import.nodes import FileImportNode
        assert hasattr(FileImportNode, "type")

    def test_status_resolver_exists(self):
        """Test FileImportNode has status resolver method."""
        from lys.apps.file_management.modules.file_import.nodes import FileImportNode
        assert hasattr(FileImportNode, "status")


class TestActiveFileImportsCountNode:
    """Tests for ActiveFileImportsCountNode."""

    def test_node_exists(self):
        """Test ActiveFileImportsCountNode class exists."""
        from lys.apps.file_management.modules.file_import.nodes import ActiveFileImportsCountNode
        assert ActiveFileImportsCountNode is not None

    def test_node_inherits_from_service_node(self):
        """Test ActiveFileImportsCountNode inherits from ServiceNode."""
        from lys.apps.file_management.modules.file_import.nodes import ActiveFileImportsCountNode
        from lys.core.graphql.nodes import ServiceNode
        assert issubclass(ActiveFileImportsCountNode, ServiceNode)

    def test_node_has_active_count_field(self):
        """Test ActiveFileImportsCountNode has active_count field."""
        from lys.apps.file_management.modules.file_import.nodes import ActiveFileImportsCountNode
        assert "active_count" in ActiveFileImportsCountNode.__annotations__

    def test_node_service_name_is_file_import(self):
        """Test ActiveFileImportsCountNode resolves service_name to file_import."""
        from lys.apps.file_management.modules.file_import.nodes import ActiveFileImportsCountNode
        assert ActiveFileImportsCountNode.service_name == "file_import"
