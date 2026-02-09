"""
Unit tests for AppRegistry logic (register/get, locking, fixtures ordering, overrides).

Isolation: Each test creates a fresh AppRegistry() instance — no singleton pollution.
"""
import pytest


class TestAppRegistryEntityRegistration:
    """Tests for entity register/get logic."""

    def test_register_and_get_entity(self):
        from lys.core.registries import AppRegistry
        from lys.core.interfaces.entities import EntityInterface

        class FakeEntity(EntityInterface):
            __tablename__ = "fake"
            @classmethod
            def get_tablename(cls): return "fake"

        registry = AppRegistry()
        registry.register_entity("fake", FakeEntity)
        assert registry.get_entity("fake") is FakeEntity

    def test_get_entity_not_found_raises(self):
        from lys.core.registries import AppRegistry
        registry = AppRegistry()
        with pytest.raises(KeyError, match="Entity 'missing' not found"):
            registry.get_entity("missing")

    def test_get_entity_nullable_returns_none(self):
        from lys.core.registries import AppRegistry
        registry = AppRegistry()
        assert registry.get_entity("missing", nullable=True) is None

    def test_register_entity_invalid_type_raises(self):
        from lys.core.registries import AppRegistry

        class NotAnEntity:
            pass

        registry = AppRegistry()
        with pytest.raises(TypeError, match="must be a subclass of EntityInterface"):
            registry.register_entity("bad", NotAnEntity)


class TestAppRegistryServiceRegistration:
    """Tests for service register/get logic."""

    def test_register_and_get_service(self):
        from lys.core.registries import AppRegistry
        from lys.core.interfaces.services import ServiceInterface

        class FakeService(ServiceInterface):
            service_name = "fake"

        registry = AppRegistry()
        registry.register_service("fake", FakeService)
        assert registry.get_service("fake") is FakeService

    def test_get_service_not_found_raises(self):
        from lys.core.registries import AppRegistry
        registry = AppRegistry()
        with pytest.raises(KeyError, match="Service 'missing' not found"):
            registry.get_service("missing")

    def test_get_service_nullable_returns_none(self):
        from lys.core.registries import AppRegistry
        registry = AppRegistry()
        assert registry.get_service("missing", nullable=True) is None

    def test_register_service_invalid_type_raises(self):
        from lys.core.registries import AppRegistry

        class NotAService:
            pass

        registry = AppRegistry()
        with pytest.raises(TypeError, match="must be a subclass of ServiceInterface"):
            registry.register_service("bad", NotAService)


class TestAppRegistryNodeRegistration:
    """Tests for node register/get logic."""

    def test_register_and_get_node(self):
        from lys.core.registries import AppRegistry
        from lys.core.graphql.interfaces import NodeInterface

        class FakeNode(NodeInterface):
            pass

        registry = AppRegistry()
        registry.register_node("fake", FakeNode)
        assert registry.get_node("fake") is FakeNode

    def test_get_node_not_found_raises(self):
        from lys.core.registries import AppRegistry
        registry = AppRegistry()
        with pytest.raises(KeyError, match="Node 'missing' not found"):
            registry.get_node("missing")

    def test_register_node_invalid_type_raises(self):
        from lys.core.registries import AppRegistry
        from lys.core.graphql.interfaces import NodeInterface

        class NotANode:
            pass

        registry = AppRegistry()
        with pytest.raises(TypeError, match="must be a subclass of NodeInterface"):
            registry.register_node("bad", NotANode)


class TestAppRegistryLocking:
    """Tests for is_locked/lock logic."""

    def test_not_locked_by_default(self):
        from lys.core.registries import AppRegistry
        from lys.core.consts.component_types import AppComponentTypeEnum
        registry = AppRegistry()
        assert registry.is_locked(AppComponentTypeEnum.ENTITIES) is False

    def test_lock_prevents_registration(self):
        from lys.core.registries import AppRegistry
        from lys.core.consts.component_types import AppComponentTypeEnum
        from lys.core.interfaces.entities import EntityInterface

        class FakeEntity(EntityInterface):
            __tablename__ = "fake"
            @classmethod
            def get_tablename(cls): return "fake"

        registry = AppRegistry()
        registry.lock(AppComponentTypeEnum.ENTITIES)
        assert registry.is_locked(AppComponentTypeEnum.ENTITIES) is True
        registry.register_entity("fake", FakeEntity)
        # Registration silently skipped when locked
        assert "fake" not in registry.entities

    def test_lock_services(self):
        from lys.core.registries import AppRegistry
        from lys.core.consts.component_types import AppComponentTypeEnum
        from lys.core.interfaces.services import ServiceInterface

        class FakeService(ServiceInterface):
            service_name = "fake"

        registry = AppRegistry()
        registry.lock(AppComponentTypeEnum.SERVICES)
        registry.register_service("fake", FakeService)
        assert "fake" not in registry.services


class TestAppRegistryFixturesDependencyOrder:
    """Tests for get_fixtures_in_dependency_order()."""

    def _make_fixture(self, name, module="test.module"):
        """Create a minimal fixture class with __name__ and __module__.

        We cannot directly subclass EntityFixtureInterface (ABC with classproperty)
        via type(), so we create a plain class that register_fixture accepts.
        The register_fixture method only checks is_locked() and stores the class;
        it does not introspect EntityFixtureInterface.
        """
        cls = type(name, (), {"__module__": module})
        return cls

    def test_empty_returns_empty(self):
        from lys.core.registries import AppRegistry
        registry = AppRegistry()
        assert registry.get_fixtures_in_dependency_order() == []

    def test_no_deps_returns_all(self):
        from lys.core.registries import AppRegistry
        registry = AppRegistry()
        A = self._make_fixture("A")
        B = self._make_fixture("B")
        registry.register_fixture(A)
        registry.register_fixture(B)
        result = registry.get_fixtures_in_dependency_order()
        assert set(result) == {A, B}

    def test_with_deps_correct_order(self):
        from lys.core.registries import AppRegistry
        registry = AppRegistry()
        A = self._make_fixture("A")
        B = self._make_fixture("B")
        registry.register_fixture(A)
        registry.register_fixture(B, depends_on=["A"])
        result = registry.get_fixtures_in_dependency_order()
        assert result.index(A) < result.index(B)

    def test_circular_dependency_raises(self):
        from lys.core.registries import AppRegistry
        registry = AppRegistry()
        A = self._make_fixture("A")
        B = self._make_fixture("B")
        registry.register_fixture(A, depends_on=["B"])
        registry.register_fixture(B, depends_on=["A"])
        with pytest.raises(ValueError, match="Circular dependency"):
            registry.get_fixtures_in_dependency_order()

    def test_duplicate_fixture_raises(self):
        from lys.core.registries import AppRegistry
        registry = AppRegistry()
        A = self._make_fixture("A")
        registry.register_fixture(A)
        with pytest.raises(ValueError, match="already registered"):
            registry.register_fixture(A)


class TestOverrideWebservice:
    """Tests for override_webservice() and disable_webservice()."""

    def test_override_not_found_raises(self):
        from lys.core.registries import AppRegistry, override_webservice
        registry = AppRegistry()
        with pytest.raises(ValueError, match="not found in registry"):
            override_webservice("nonexistent", access_levels=["ROLE"], register=registry)

    def test_override_access_levels(self):
        from lys.core.registries import AppRegistry, override_webservice
        registry = AppRegistry()
        registry.webservices["test_ws"] = {"attributes": {"access_levels": ["CONNECTED"]}}
        override_webservice("test_ws", access_levels=["ROLE", "OWNER"], register=registry)
        assert registry.webservices["test_ws"]["attributes"]["access_levels"] == ["ROLE", "OWNER"]

    def test_override_is_public(self):
        from lys.core.registries import AppRegistry, override_webservice
        registry = AppRegistry()
        registry.webservices["test_ws"] = {"attributes": {"is_public": False}}
        override_webservice("test_ws", is_public=True, register=registry)
        assert registry.webservices["test_ws"]["attributes"]["is_public"] is True

    def test_override_no_params_is_noop(self):
        from lys.core.registries import AppRegistry, override_webservice
        registry = AppRegistry()
        registry.webservices["test_ws"] = {"attributes": {"enabled": True}}
        # Should not raise — just logs a warning
        override_webservice("test_ws", register=registry)
        assert registry.webservices["test_ws"]["attributes"]["enabled"] is True

    def test_disable_webservice(self):
        from lys.core.registries import AppRegistry, disable_webservice
        registry = AppRegistry()
        registry.webservices["test_ws"] = {"attributes": {"enabled": True}}
        disable_webservice("test_ws", register=registry)
        assert registry.webservices["test_ws"]["attributes"]["enabled"] is False

    def test_disable_not_found_raises(self):
        from lys.core.registries import AppRegistry, disable_webservice
        registry = AppRegistry()
        with pytest.raises(ValueError, match="not found in registry"):
            disable_webservice("nonexistent", register=registry)


class TestCustomRegistryIntegration:
    """Tests for custom registry add/get on AppRegistry."""

    def test_add_and_get_custom_registry(self):
        from lys.core.registries import AppRegistry, CustomRegistry

        class ValidatorRegistry(CustomRegistry):
            name = "validators"

        registry = AppRegistry()
        validators = ValidatorRegistry()
        registry.add_custom_registry(validators)
        assert registry.get_registry("validators") is validators

    def test_get_missing_returns_none(self):
        from lys.core.registries import AppRegistry
        registry = AppRegistry()
        assert registry.get_registry("nonexistent") is None

    def test_get_custom_component_files(self):
        from lys.core.registries import AppRegistry, CustomRegistry

        class ValidatorRegistry(CustomRegistry):
            name = "validators"

        class DowngraderRegistry(CustomRegistry):
            name = "downgraders"

        registry = AppRegistry()
        registry.add_custom_registry(ValidatorRegistry())
        registry.add_custom_registry(DowngraderRegistry())
        files = registry.get_custom_component_files()
        assert "validators" in files
        assert "downgraders" in files
