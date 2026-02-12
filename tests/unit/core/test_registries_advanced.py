"""
Unit tests for AppRegistry advanced methods:
- validate_webservice_configuration
- finalize_webservices
- initialize_services / shutdown_services
- CustomRegistry register/get/all/keys
- override_webservice is_licenced/enabled
- fixture dependency unknown dep error
"""
import asyncio
import pytest

from lys.core.registries import AppRegistry, CustomRegistry


class TestCustomRegistryMethods:
    def test_register_and_get(self):
        class MyRegistry(CustomRegistry):
            name = "test"

        reg = MyRegistry()
        reg.register("key1", "value1")
        assert reg.get("key1") == "value1"

    def test_get_missing_returns_none(self):
        class MyRegistry(CustomRegistry):
            name = "test"

        reg = MyRegistry()
        assert reg.get("missing") is None

    def test_all_returns_copy(self):
        class MyRegistry(CustomRegistry):
            name = "test"

        reg = MyRegistry()
        reg.register("a", 1)
        reg.register("b", 2)
        result = reg.all()
        assert result == {"a": 1, "b": 2}
        result["c"] = 3
        assert reg.get("c") is None

    def test_keys(self):
        class MyRegistry(CustomRegistry):
            name = "test"

        reg = MyRegistry()
        reg.register("x", 10)
        reg.register("y", 20)
        assert set(reg.keys()) == {"x", "y"}


class TestValidateWebserviceConfiguration:
    def test_no_access_level_entity_skips(self):
        registry = AppRegistry()
        registry.webservices["ws1"] = {"attributes": {"access_levels": ["CONNECTED"]}}
        registry.validate_webservice_configuration()

    def test_valid_access_levels_passes(self):
        from lys.core.interfaces.entities import EntityInterface

        class FakeAccessLevel(EntityInterface):
            __tablename__ = "access_level"
            @classmethod
            def get_tablename(cls): return "access_level"

        registry = AppRegistry()
        registry.entities["access_level"] = FakeAccessLevel
        registry.webservices["ws1"] = {"attributes": {"access_levels": ["CONNECTED"]}}
        registry.validate_webservice_configuration()

    def test_empty_access_level_string_raises(self):
        from lys.core.interfaces.entities import EntityInterface

        class FakeAccessLevel(EntityInterface):
            __tablename__ = "access_level"
            @classmethod
            def get_tablename(cls): return "access_level"

        registry = AppRegistry()
        registry.entities["access_level"] = FakeAccessLevel
        registry.webservices["ws1"] = {"attributes": {"access_levels": [""]}}
        with pytest.raises(ValueError, match="validation failed"):
            registry.validate_webservice_configuration()

    def test_non_string_access_level_raises(self):
        from lys.core.interfaces.entities import EntityInterface

        class FakeAccessLevel(EntityInterface):
            __tablename__ = "access_level"
            @classmethod
            def get_tablename(cls): return "access_level"

        registry = AppRegistry()
        registry.entities["access_level"] = FakeAccessLevel
        registry.webservices["ws1"] = {"attributes": {"access_levels": [123]}}
        with pytest.raises(ValueError, match="validation failed"):
            registry.validate_webservice_configuration()


class TestFinalizeWebservices:
    def test_with_ai_tools(self):
        registry = AppRegistry()
        registry.webservices["ws1"] = {"_options": {"generate_tool": True}}
        registry.webservices["ws2"] = {"_options": None}
        registry.finalize_webservices()

    def test_no_ai_tools(self):
        registry = AppRegistry()
        registry.webservices["ws1"] = {"_options": None}
        registry.finalize_webservices()


class TestInitializeAndShutdownServices:
    def test_initialize_services(self):
        registry = AppRegistry()

        class FakeService:
            initialized = False
            @classmethod
            async def on_initialize(cls):
                cls.initialized = True

        registry.services["fake"] = FakeService
        asyncio.run(registry.initialize_services())
        assert FakeService.initialized is True

    def test_initialize_services_error_propagates(self):
        registry = AppRegistry()

        class BadService:
            @classmethod
            async def on_initialize(cls):
                raise RuntimeError("init failed")

        registry.services["bad"] = BadService
        with pytest.raises(RuntimeError, match="init failed"):
            asyncio.run(registry.initialize_services())

    def test_shutdown_services(self):
        registry = AppRegistry()

        class FakeService:
            shutdown_called = False
            @classmethod
            async def on_shutdown(cls):
                cls.shutdown_called = True

        registry.services["fake"] = FakeService
        asyncio.run(registry.shutdown_services())
        assert FakeService.shutdown_called is True

    def test_shutdown_continues_on_error(self):
        registry = AppRegistry()

        class BadService:
            @classmethod
            async def on_shutdown(cls):
                raise RuntimeError("shutdown failed")

        class GoodService:
            shutdown_called = False
            @classmethod
            async def on_shutdown(cls):
                cls.shutdown_called = True

        registry.services["bad"] = BadService
        registry.services["good"] = GoodService
        asyncio.run(registry.shutdown_services())
        assert GoodService.shutdown_called is True


class TestOverrideWebserviceAdditional:
    def test_override_is_licenced(self):
        from lys.core.registries import override_webservice
        registry = AppRegistry()
        registry.webservices["test_ws"] = {"attributes": {"is_licenced": True}}
        override_webservice("test_ws", is_licenced=False, register=registry)
        assert registry.webservices["test_ws"]["attributes"]["is_licenced"] is False

    def test_override_enabled(self):
        from lys.core.registries import override_webservice
        registry = AppRegistry()
        registry.webservices["test_ws"] = {"attributes": {"enabled": True}}
        override_webservice("test_ws", enabled=False, register=registry)
        assert registry.webservices["test_ws"]["attributes"]["enabled"] is False


class TestFixtureDependencyUnknownDep:
    def test_unknown_dependency_raises(self):
        registry = AppRegistry()
        A = type("A", (), {"__module__": "test"})
        registry.register_fixture(A, depends_on=["NonExistent"])
        with pytest.raises(ValueError, match="not registered"):
            registry.get_fixtures_in_dependency_order()
