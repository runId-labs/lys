"""
Unit tests for core interfaces services module.

Tests ServiceInterface and EntityServiceInterface abstract classes.
"""

import pytest
from abc import ABC


class TestServiceInterface:
    """Tests for ServiceInterface class."""

    def test_class_exists(self):
        """Test ServiceInterface class exists."""
        from lys.core.interfaces.services import ServiceInterface
        assert ServiceInterface is not None

    def test_inherits_from_abc(self):
        """Test ServiceInterface inherits from ABC."""
        from lys.core.interfaces.services import ServiceInterface
        assert issubclass(ServiceInterface, ABC)

    def test_has_execute_parallel_method(self):
        """Test ServiceInterface has execute_parallel abstract method."""
        from lys.core.interfaces.services import ServiceInterface
        assert hasattr(ServiceInterface, "execute_parallel")

    def test_execute_parallel_is_async(self):
        """Test execute_parallel is an async method."""
        from lys.core.interfaces.services import ServiceInterface
        import inspect
        assert inspect.iscoroutinefunction(ServiceInterface.execute_parallel)


class TestEntityServiceInterface:
    """Tests for EntityServiceInterface class."""

    def test_class_exists(self):
        """Test EntityServiceInterface class exists."""
        from lys.core.interfaces.services import EntityServiceInterface
        assert EntityServiceInterface is not None

    def test_inherits_from_service_interface(self):
        """Test EntityServiceInterface inherits from ServiceInterface."""
        from lys.core.interfaces.services import EntityServiceInterface, ServiceInterface
        assert issubclass(EntityServiceInterface, ServiceInterface)

    def test_has_entity_class_property(self):
        """Test EntityServiceInterface has entity_class classproperty."""
        from lys.core.interfaces.services import EntityServiceInterface
        # entity_class is a classproperty that raises NotImplementedError
        assert "entity_class" in dir(EntityServiceInterface)

    def test_has_get_by_id_method(self):
        """Test EntityServiceInterface has get_by_id method."""
        from lys.core.interfaces.services import EntityServiceInterface
        assert hasattr(EntityServiceInterface, "get_by_id")

    def test_get_by_id_is_async(self):
        """Test get_by_id is an async method."""
        from lys.core.interfaces.services import EntityServiceInterface
        import inspect
        assert inspect.iscoroutinefunction(EntityServiceInterface.get_by_id)

    def test_has_get_all_method(self):
        """Test EntityServiceInterface has get_all method."""
        from lys.core.interfaces.services import EntityServiceInterface
        assert hasattr(EntityServiceInterface, "get_all")

    def test_get_all_is_async(self):
        """Test get_all is an async method."""
        from lys.core.interfaces.services import EntityServiceInterface
        import inspect
        assert inspect.iscoroutinefunction(EntityServiceInterface.get_all)

    def test_has_create_method(self):
        """Test EntityServiceInterface has create method."""
        from lys.core.interfaces.services import EntityServiceInterface
        assert hasattr(EntityServiceInterface, "create")

    def test_create_is_async(self):
        """Test create is an async method."""
        from lys.core.interfaces.services import EntityServiceInterface
        import inspect
        assert inspect.iscoroutinefunction(EntityServiceInterface.create)

    def test_has_update_method(self):
        """Test EntityServiceInterface has update method."""
        from lys.core.interfaces.services import EntityServiceInterface
        assert hasattr(EntityServiceInterface, "update")

    def test_update_is_async(self):
        """Test update is an async method."""
        from lys.core.interfaces.services import EntityServiceInterface
        import inspect
        assert inspect.iscoroutinefunction(EntityServiceInterface.update)

    def test_has_delete_method(self):
        """Test EntityServiceInterface has delete method."""
        from lys.core.interfaces.services import EntityServiceInterface
        assert hasattr(EntityServiceInterface, "delete")

    def test_delete_is_async(self):
        """Test delete is an async method."""
        from lys.core.interfaces.services import EntityServiceInterface
        import inspect
        assert inspect.iscoroutinefunction(EntityServiceInterface.delete)

    def test_has_get_multiple_by_ids_method(self):
        """Test EntityServiceInterface has get_multiple_by_ids method."""
        from lys.core.interfaces.services import EntityServiceInterface
        assert hasattr(EntityServiceInterface, "get_multiple_by_ids")

    def test_get_multiple_by_ids_is_async(self):
        """Test get_multiple_by_ids is an async method."""
        from lys.core.interfaces.services import EntityServiceInterface
        import inspect
        assert inspect.iscoroutinefunction(EntityServiceInterface.get_multiple_by_ids)

    def test_has_check_and_update_method(self):
        """Test EntityServiceInterface has check_and_update method."""
        from lys.core.interfaces.services import EntityServiceInterface
        assert hasattr(EntityServiceInterface, "check_and_update")

    def test_check_and_update_is_async(self):
        """Test check_and_update is an async method."""
        from lys.core.interfaces.services import EntityServiceInterface
        import inspect
        assert inspect.iscoroutinefunction(EntityServiceInterface.check_and_update)


class TestEntityServiceInterfaceMethodSignatures:
    """Tests for EntityServiceInterface method signatures."""

    def test_get_by_id_signature(self):
        """Test get_by_id method signature."""
        from lys.core.interfaces.services import EntityServiceInterface
        import inspect

        sig = inspect.signature(EntityServiceInterface.get_by_id)
        params = list(sig.parameters.keys())
        assert "entity_id" in params
        assert "session" in params

    def test_get_all_signature(self):
        """Test get_all method signature."""
        from lys.core.interfaces.services import EntityServiceInterface
        import inspect

        sig = inspect.signature(EntityServiceInterface.get_all)
        params = list(sig.parameters.keys())
        assert "session" in params
        assert "limit" in params
        assert "offset" in params

    def test_create_signature(self):
        """Test create method signature."""
        from lys.core.interfaces.services import EntityServiceInterface
        import inspect

        sig = inspect.signature(EntityServiceInterface.create)
        params = list(sig.parameters.keys())
        assert "session" in params

    def test_update_signature(self):
        """Test update method signature."""
        from lys.core.interfaces.services import EntityServiceInterface
        import inspect

        sig = inspect.signature(EntityServiceInterface.update)
        params = list(sig.parameters.keys())
        assert "entity_id" in params
        assert "session" in params

    def test_delete_signature(self):
        """Test delete method signature."""
        from lys.core.interfaces.services import EntityServiceInterface
        import inspect

        sig = inspect.signature(EntityServiceInterface.delete)
        params = list(sig.parameters.keys())
        assert "entity_id" in params
        assert "session" in params

    def test_get_multiple_by_ids_signature(self):
        """Test get_multiple_by_ids method signature."""
        from lys.core.interfaces.services import EntityServiceInterface
        import inspect

        sig = inspect.signature(EntityServiceInterface.get_multiple_by_ids)
        params = list(sig.parameters.keys())
        assert "entity_ids" in params
        assert "session" in params
