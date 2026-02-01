"""
Unit tests for core services module.

Tests Service and EntityService base classes.
"""

import pytest
import inspect


class TestServiceClass:
    """Tests for Service base class."""

    def test_class_exists(self):
        """Test Service class exists."""
        from lys.core.services import Service
        assert Service is not None

    def test_implements_service_interface(self):
        """Test Service implements ServiceInterface."""
        from lys.core.services import Service
        from lys.core.interfaces.services import ServiceInterface
        assert issubclass(Service, ServiceInterface)

    def test_has_execute_parallel_method(self):
        """Test Service has execute_parallel method."""
        from lys.core.services import Service
        assert hasattr(Service, "execute_parallel")

    def test_execute_parallel_is_async(self):
        """Test execute_parallel is an async method."""
        from lys.core.services import Service
        assert inspect.iscoroutinefunction(Service.execute_parallel)


class TestEntityServiceClass:
    """Tests for EntityService base class."""

    def test_class_exists(self):
        """Test EntityService class exists."""
        from lys.core.services import EntityService
        assert EntityService is not None

    def test_inherits_from_service(self):
        """Test EntityService inherits from Service."""
        from lys.core.services import EntityService, Service
        assert issubclass(EntityService, Service)

    def test_implements_entity_service_interface(self):
        """Test EntityService implements EntityServiceInterface."""
        from lys.core.services import EntityService
        from lys.core.interfaces.services import EntityServiceInterface
        assert issubclass(EntityService, EntityServiceInterface)

    def test_has_entity_class_property(self):
        """Test EntityService has entity_class classproperty."""
        from lys.core.services import EntityService
        # entity_class is a classproperty
        assert "entity_class" in dir(EntityService)

    def test_has_get_by_id_method(self):
        """Test EntityService has get_by_id method."""
        from lys.core.services import EntityService
        assert hasattr(EntityService, "get_by_id")

    def test_get_by_id_is_async(self):
        """Test get_by_id is an async method."""
        from lys.core.services import EntityService
        assert inspect.iscoroutinefunction(EntityService.get_by_id)

    def test_has_get_all_method(self):
        """Test EntityService has get_all method."""
        from lys.core.services import EntityService
        assert hasattr(EntityService, "get_all")

    def test_get_all_is_async(self):
        """Test get_all is an async method."""
        from lys.core.services import EntityService
        assert inspect.iscoroutinefunction(EntityService.get_all)

    def test_has_create_method(self):
        """Test EntityService has create method."""
        from lys.core.services import EntityService
        assert hasattr(EntityService, "create")

    def test_create_is_async(self):
        """Test create is an async method."""
        from lys.core.services import EntityService
        assert inspect.iscoroutinefunction(EntityService.create)

    def test_has_update_method(self):
        """Test EntityService has update method."""
        from lys.core.services import EntityService
        assert hasattr(EntityService, "update")

    def test_update_is_async(self):
        """Test update is an async method."""
        from lys.core.services import EntityService
        assert inspect.iscoroutinefunction(EntityService.update)

    def test_has_delete_method(self):
        """Test EntityService has delete method."""
        from lys.core.services import EntityService
        assert hasattr(EntityService, "delete")

    def test_delete_is_async(self):
        """Test delete is an async method."""
        from lys.core.services import EntityService
        assert inspect.iscoroutinefunction(EntityService.delete)

    def test_has_get_multiple_by_ids_method(self):
        """Test EntityService has get_multiple_by_ids method."""
        from lys.core.services import EntityService
        assert hasattr(EntityService, "get_multiple_by_ids")

    def test_get_multiple_by_ids_is_async(self):
        """Test get_multiple_by_ids is an async method."""
        from lys.core.services import EntityService
        assert inspect.iscoroutinefunction(EntityService.get_multiple_by_ids)

    def test_has_check_and_update_method(self):
        """Test EntityService has check_and_update method."""
        from lys.core.services import EntityService
        assert hasattr(EntityService, "check_and_update")

    def test_check_and_update_is_async(self):
        """Test check_and_update is an async method."""
        from lys.core.services import EntityService
        assert inspect.iscoroutinefunction(EntityService.check_and_update)

    def test_has_values_differ_method(self):
        """Test EntityService has _values_differ method."""
        from lys.core.services import EntityService
        assert hasattr(EntityService, "_values_differ")

    def test_has_list_values_differ_method(self):
        """Test EntityService has _list_values_differ method."""
        from lys.core.services import EntityService
        assert hasattr(EntityService, "_list_values_differ")


class TestEntityServiceMethodSignatures:
    """Tests for EntityService method signatures."""

    def test_get_by_id_signature(self):
        """Test get_by_id method signature."""
        from lys.core.services import EntityService

        sig = inspect.signature(EntityService.get_by_id)
        params = list(sig.parameters.keys())
        assert "entity_id" in params
        assert "session" in params

    def test_get_all_signature(self):
        """Test get_all method signature."""
        from lys.core.services import EntityService

        sig = inspect.signature(EntityService.get_all)
        params = list(sig.parameters.keys())
        assert "session" in params
        assert "limit" in params
        assert "offset" in params

    def test_get_all_has_default_limit(self):
        """Test get_all has default limit of 100."""
        from lys.core.services import EntityService

        sig = inspect.signature(EntityService.get_all)
        assert sig.parameters["limit"].default == 100

    def test_get_all_has_default_offset(self):
        """Test get_all has default offset of 0."""
        from lys.core.services import EntityService

        sig = inspect.signature(EntityService.get_all)
        assert sig.parameters["offset"].default == 0

    def test_create_signature(self):
        """Test create method signature."""
        from lys.core.services import EntityService

        sig = inspect.signature(EntityService.create)
        params = list(sig.parameters.keys())
        assert "session" in params

    def test_update_signature(self):
        """Test update method signature."""
        from lys.core.services import EntityService

        sig = inspect.signature(EntityService.update)
        params = list(sig.parameters.keys())
        assert "entity_id" in params
        assert "session" in params

    def test_delete_signature(self):
        """Test delete method signature."""
        from lys.core.services import EntityService

        sig = inspect.signature(EntityService.delete)
        params = list(sig.parameters.keys())
        assert "entity_id" in params
        assert "session" in params

    def test_get_multiple_by_ids_signature(self):
        """Test get_multiple_by_ids method signature."""
        from lys.core.services import EntityService

        sig = inspect.signature(EntityService.get_multiple_by_ids)
        params = list(sig.parameters.keys())
        assert "entity_ids" in params
        assert "session" in params


class TestEntityServiceValuesDiffer:
    """Tests for EntityService _values_differ method."""

    def test_values_differ_with_equal_primitives(self):
        """Test _values_differ returns False for equal primitives."""
        from lys.core.services import EntityService
        result = EntityService._values_differ("old", "old")
        assert result is False

    def test_values_differ_with_different_primitives(self):
        """Test _values_differ returns True for different primitives."""
        from lys.core.services import EntityService
        result = EntityService._values_differ("old", "new")
        assert result is True

    def test_values_differ_with_equal_numbers(self):
        """Test _values_differ returns False for equal numbers."""
        from lys.core.services import EntityService
        result = EntityService._values_differ(42, 42)
        assert result is False

    def test_values_differ_with_different_numbers(self):
        """Test _values_differ returns True for different numbers."""
        from lys.core.services import EntityService
        result = EntityService._values_differ(42, 43)
        assert result is True


class TestEntityServiceListValuesDiffer:
    """Tests for EntityService _list_values_differ method."""

    def test_list_values_differ_with_non_list_old_value(self):
        """Test _list_values_differ returns True when old value is not a list."""
        from lys.core.services import EntityService
        result = EntityService._list_values_differ("not a list", [1, 2, 3])
        assert result is True

    def test_list_values_differ_with_different_lengths(self):
        """Test _list_values_differ returns True for different length lists."""
        from lys.core.services import EntityService
        result = EntityService._list_values_differ([1, 2], [1, 2, 3])
        assert result is True

    def test_list_values_differ_with_equal_primitive_lists(self):
        """Test _list_values_differ returns False for equal primitive lists."""
        from lys.core.services import EntityService
        result = EntityService._list_values_differ([1, 2, 3], [1, 2, 3])
        assert result is False

    def test_list_values_differ_with_different_primitive_lists(self):
        """Test _list_values_differ returns True for different primitive lists."""
        from lys.core.services import EntityService
        result = EntityService._list_values_differ([1, 2, 3], [1, 2, 4])
        assert result is True

    def test_list_values_differ_with_same_elements_different_order(self):
        """Test _list_values_differ returns False for same elements in different order."""
        from lys.core.services import EntityService
        result = EntityService._list_values_differ([1, 2, 3], [3, 2, 1])
        assert result is False
