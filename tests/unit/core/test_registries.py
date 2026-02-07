import inspect

import pytest


class TestCustomRegistryExists:
    """Verify that CustomRegistry class exists and has the expected interface."""

    def test_class_exists(self):
        from lys.core.registries import CustomRegistry

        assert inspect.isclass(CustomRegistry)

    def test_has_init_method(self):
        from lys.core.registries import CustomRegistry

        assert hasattr(CustomRegistry, "__init__")
        assert callable(CustomRegistry.__init__)

    def test_has_register_method(self):
        from lys.core.registries import CustomRegistry

        assert hasattr(CustomRegistry, "register")
        assert callable(CustomRegistry.register)

    def test_register_method_signature(self):
        from lys.core.registries import CustomRegistry

        sig = inspect.signature(CustomRegistry.register)
        param_names = list(sig.parameters.keys())
        assert "self" in param_names
        assert "key" in param_names
        assert "item" in param_names

    def test_has_get_method(self):
        from lys.core.registries import CustomRegistry

        assert hasattr(CustomRegistry, "get")
        assert callable(CustomRegistry.get)

    def test_get_method_signature(self):
        from lys.core.registries import CustomRegistry

        sig = inspect.signature(CustomRegistry.get)
        param_names = list(sig.parameters.keys())
        assert "self" in param_names
        assert "key" in param_names

    def test_has_all_method(self):
        from lys.core.registries import CustomRegistry

        assert hasattr(CustomRegistry, "all")
        assert callable(CustomRegistry.all)

    def test_all_method_returns_dict(self):
        from lys.core.registries import CustomRegistry

        registry = CustomRegistry()
        result = registry.all()
        assert isinstance(result, dict)

    def test_has_keys_method(self):
        from lys.core.registries import CustomRegistry

        assert hasattr(CustomRegistry, "keys")
        assert callable(CustomRegistry.keys)

    def test_keys_method_returns_list(self):
        from lys.core.registries import CustomRegistry

        registry = CustomRegistry()
        result = registry.keys()
        assert isinstance(result, list)

    def test_has_name_annotation(self):
        from lys.core.registries import CustomRegistry

        assert "name" in CustomRegistry.__annotations__
        assert CustomRegistry.__annotations__["name"] is str


class TestCustomRegistryFunctional:
    """Verify CustomRegistry functional behavior with register, get, all, and keys."""

    def _make_registry(self, name="test_registry"):
        """Create a CustomRegistry subclass with a name attribute for testing."""
        from lys.core.registries import CustomRegistry

        class TestRegistry(CustomRegistry):
            pass

        TestRegistry.name = name
        return TestRegistry()

    def test_register_and_get(self):
        registry = self._make_registry()
        registry.register("test_key", "test_value")
        assert registry.get("test_key") == "test_value"

    def test_register_multiple_items(self):
        registry = self._make_registry()
        registry.register("key1", "value1")
        registry.register("key2", "value2")
        assert registry.get("key1") == "value1"
        assert registry.get("key2") == "value2"

    def test_all_returns_registered_items(self):
        registry = self._make_registry()
        registry.register("alpha", 1)
        registry.register("beta", 2)
        result = registry.all()
        assert result == {"alpha": 1, "beta": 2}

    def test_keys_returns_registered_keys(self):
        registry = self._make_registry()
        registry.register("first", "a")
        registry.register("second", "b")
        keys = registry.keys()
        assert "first" in keys
        assert "second" in keys
        assert len(keys) == 2

    def test_empty_registry_all(self):
        registry = self._make_registry()
        assert registry.all() == {}

    def test_empty_registry_keys(self):
        registry = self._make_registry()
        assert registry.keys() == []

    def test_register_overwrites_existing_key(self):
        registry = self._make_registry()
        registry.register("key", "old_value")
        registry.register("key", "new_value")
        assert registry.get("key") == "new_value"

    def test_register_various_item_types(self):
        registry = self._make_registry()
        registry.register("string", "hello")
        registry.register("number", 42)
        registry.register("cls", dict)
        assert registry.get("string") == "hello"
        assert registry.get("number") == 42
        assert registry.get("cls") is dict


class TestAppRegistryExists:
    """Verify that AppRegistry class exists and has the expected attributes and methods."""

    def test_class_exists(self):
        from lys.core.registries import AppRegistry

        assert inspect.isclass(AppRegistry)

    def test_has_entities_attribute(self):
        from lys.core.registries import AppRegistry

        instance = AppRegistry()
        assert hasattr(instance, "entities")
        assert isinstance(instance.entities, dict)

    def test_has_services_attribute(self):
        from lys.core.registries import AppRegistry

        instance = AppRegistry()
        assert hasattr(instance, "services")
        assert isinstance(instance.services, dict)

    def test_has_fixtures_attribute(self):
        from lys.core.registries import AppRegistry

        instance = AppRegistry()
        assert hasattr(instance, "fixtures")
        assert isinstance(instance.fixtures, list)

    def test_has_webservices_attribute(self):
        from lys.core.registries import AppRegistry

        instance = AppRegistry()
        assert hasattr(instance, "webservices")
        assert isinstance(instance.webservices, dict)

    def test_has_nodes_attribute(self):
        from lys.core.registries import AppRegistry

        instance = AppRegistry()
        assert hasattr(instance, "nodes")
        assert isinstance(instance.nodes, dict)

    def test_has_routers_attribute(self):
        from lys.core.registries import AppRegistry

        instance = AppRegistry()
        assert hasattr(instance, "routers")
        assert isinstance(instance.routers, list)


class TestAppRegistryMethods:
    """Verify that AppRegistry has all expected methods with correct signatures."""

    def test_has_add_custom_registry(self):
        from lys.core.registries import AppRegistry

        assert hasattr(AppRegistry, "add_custom_registry")
        assert callable(AppRegistry.add_custom_registry)

    def test_add_custom_registry_signature(self):
        from lys.core.registries import AppRegistry

        sig = inspect.signature(AppRegistry.add_custom_registry)
        param_names = list(sig.parameters.keys())
        assert "self" in param_names
        assert "registry" in param_names

    def test_has_get_registry(self):
        from lys.core.registries import AppRegistry

        assert hasattr(AppRegistry, "get_registry")
        assert callable(AppRegistry.get_registry)

    def test_get_registry_signature(self):
        from lys.core.registries import AppRegistry

        sig = inspect.signature(AppRegistry.get_registry)
        param_names = list(sig.parameters.keys())
        assert "self" in param_names
        assert "name" in param_names

    def test_has_register_entity(self):
        from lys.core.registries import AppRegistry

        assert hasattr(AppRegistry, "register_entity")
        assert callable(AppRegistry.register_entity)

    def test_register_entity_signature(self):
        from lys.core.registries import AppRegistry

        sig = inspect.signature(AppRegistry.register_entity)
        param_names = list(sig.parameters.keys())
        assert "self" in param_names
        assert "name" in param_names
        assert "entity_class" in param_names

    def test_has_get_entity(self):
        from lys.core.registries import AppRegistry

        assert hasattr(AppRegistry, "get_entity")
        assert callable(AppRegistry.get_entity)

    def test_get_entity_signature(self):
        from lys.core.registries import AppRegistry

        sig = inspect.signature(AppRegistry.get_entity)
        param_names = list(sig.parameters.keys())
        assert "self" in param_names
        assert "name" in param_names
        assert "nullable" in param_names

    def test_has_finalize_entities(self):
        from lys.core.registries import AppRegistry

        assert hasattr(AppRegistry, "finalize_entities")
        assert callable(AppRegistry.finalize_entities)

    def test_has_register_service(self):
        from lys.core.registries import AppRegistry

        assert hasattr(AppRegistry, "register_service")
        assert callable(AppRegistry.register_service)

    def test_register_service_signature(self):
        from lys.core.registries import AppRegistry

        sig = inspect.signature(AppRegistry.register_service)
        param_names = list(sig.parameters.keys())
        assert "self" in param_names
        assert "name" in param_names
        assert "service_class" in param_names

    def test_has_get_service(self):
        from lys.core.registries import AppRegistry

        assert hasattr(AppRegistry, "get_service")
        assert callable(AppRegistry.get_service)

    def test_get_service_signature(self):
        from lys.core.registries import AppRegistry

        sig = inspect.signature(AppRegistry.get_service)
        param_names = list(sig.parameters.keys())
        assert "self" in param_names
        assert "name" in param_names
        assert "nullable" in param_names

    def test_has_initialize_services(self):
        from lys.core.registries import AppRegistry

        assert hasattr(AppRegistry, "initialize_services")
        assert inspect.iscoroutinefunction(AppRegistry.initialize_services)

    def test_has_shutdown_services(self):
        from lys.core.registries import AppRegistry

        assert hasattr(AppRegistry, "shutdown_services")
        assert inspect.iscoroutinefunction(AppRegistry.shutdown_services)

    def test_has_register_fixture(self):
        from lys.core.registries import AppRegistry

        assert hasattr(AppRegistry, "register_fixture")
        assert callable(AppRegistry.register_fixture)

    def test_register_fixture_signature(self):
        from lys.core.registries import AppRegistry

        sig = inspect.signature(AppRegistry.register_fixture)
        param_names = list(sig.parameters.keys())
        assert "self" in param_names
        assert "fixture_class" in param_names
        assert "depends_on" in param_names

    def test_has_get_fixtures_in_dependency_order(self):
        from lys.core.registries import AppRegistry

        assert hasattr(AppRegistry, "get_fixtures_in_dependency_order")
        assert callable(AppRegistry.get_fixtures_in_dependency_order)

    def test_has_register_webservice(self):
        from lys.core.registries import AppRegistry

        assert hasattr(AppRegistry, "register_webservice")
        assert callable(AppRegistry.register_webservice)

    def test_register_webservice_signature(self):
        from lys.core.registries import AppRegistry

        sig = inspect.signature(AppRegistry.register_webservice)
        param_names = list(sig.parameters.keys())
        assert "self" in param_names
        assert "field_or_fct" in param_names
        assert "is_public" in param_names
        assert "enabled" in param_names
        assert "access_levels" in param_names

    def test_has_register_node(self):
        from lys.core.registries import AppRegistry

        assert hasattr(AppRegistry, "register_node")
        assert callable(AppRegistry.register_node)

    def test_register_node_signature(self):
        from lys.core.registries import AppRegistry

        sig = inspect.signature(AppRegistry.register_node)
        param_names = list(sig.parameters.keys())
        assert "self" in param_names
        assert "name" in param_names
        assert "node_class" in param_names

    def test_has_get_node(self):
        from lys.core.registries import AppRegistry

        assert hasattr(AppRegistry, "get_node")
        assert callable(AppRegistry.get_node)

    def test_get_node_signature(self):
        from lys.core.registries import AppRegistry

        sig = inspect.signature(AppRegistry.get_node)
        param_names = list(sig.parameters.keys())
        assert "self" in param_names
        assert "name" in param_names

    def test_has_finalize_nodes(self):
        from lys.core.registries import AppRegistry

        assert hasattr(AppRegistry, "finalize_nodes")
        assert callable(AppRegistry.finalize_nodes)

    def test_has_is_locked(self):
        from lys.core.registries import AppRegistry

        assert hasattr(AppRegistry, "is_locked")
        assert callable(AppRegistry.is_locked)

    def test_is_locked_signature(self):
        from lys.core.registries import AppRegistry

        sig = inspect.signature(AppRegistry.is_locked)
        param_names = list(sig.parameters.keys())
        assert "self" in param_names
        assert "component_type" in param_names

    def test_has_lock(self):
        from lys.core.registries import AppRegistry

        assert hasattr(AppRegistry, "lock")
        assert callable(AppRegistry.lock)

    def test_lock_signature(self):
        from lys.core.registries import AppRegistry

        sig = inspect.signature(AppRegistry.lock)
        param_names = list(sig.parameters.keys())
        assert "self" in param_names
        assert "component_type" in param_names

    def test_initialize_services_is_async(self):
        from lys.core.registries import AppRegistry

        assert inspect.iscoroutinefunction(AppRegistry.initialize_services)

    def test_shutdown_services_is_async(self):
        from lys.core.registries import AppRegistry

        assert inspect.iscoroutinefunction(AppRegistry.shutdown_services)

    def test_register_entity_is_sync(self):
        from lys.core.registries import AppRegistry

        assert not inspect.iscoroutinefunction(AppRegistry.register_entity)

    def test_get_entity_is_sync(self):
        from lys.core.registries import AppRegistry

        assert not inspect.iscoroutinefunction(AppRegistry.get_entity)


class TestLysAppRegistryExists:
    """Verify that LysAppRegistry exists and inherits from AppRegistry."""

    def test_class_exists(self):
        from lys.core.registries import LysAppRegistry

        assert inspect.isclass(LysAppRegistry)

    def test_inherits_from_app_registry(self):
        from lys.core.registries import AppRegistry, LysAppRegistry

        assert issubclass(LysAppRegistry, AppRegistry)

    def test_is_distinct_from_app_registry(self):
        from lys.core.registries import AppRegistry, LysAppRegistry

        assert LysAppRegistry is not AppRegistry


class TestModuleLevelDecorators:
    """Verify that module-level decorator functions exist and are callable."""

    def test_register_entity_exists(self):
        from lys.core.registries import register_entity

        assert callable(register_entity)

    def test_register_service_exists(self):
        from lys.core.registries import register_service

        assert callable(register_service)

    def test_register_fixture_exists(self):
        from lys.core.registries import register_fixture

        assert callable(register_fixture)

    def test_register_webservice_exists(self):
        from lys.core.registries import register_webservice

        assert callable(register_webservice)

    def test_register_node_exists(self):
        from lys.core.registries import register_node

        assert callable(register_node)

    def test_override_webservice_exists(self):
        from lys.core.registries import override_webservice

        assert callable(override_webservice)

    def test_disable_webservice_exists(self):
        from lys.core.registries import disable_webservice

        assert callable(disable_webservice)

    def test_register_entity_is_function(self):
        from lys.core.registries import register_entity

        assert inspect.isfunction(register_entity)

    def test_register_service_is_function(self):
        from lys.core.registries import register_service

        assert inspect.isfunction(register_service)

    def test_register_fixture_is_function(self):
        from lys.core.registries import register_fixture

        assert inspect.isfunction(register_fixture)

    def test_register_webservice_is_function(self):
        from lys.core.registries import register_webservice

        assert inspect.isfunction(register_webservice)

    def test_register_node_is_function(self):
        from lys.core.registries import register_node

        assert inspect.isfunction(register_node)

    def test_override_webservice_is_function(self):
        from lys.core.registries import override_webservice

        assert inspect.isfunction(override_webservice)

    def test_disable_webservice_is_function(self):
        from lys.core.registries import disable_webservice

        assert inspect.isfunction(disable_webservice)
