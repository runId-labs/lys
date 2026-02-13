"""
Unit tests for core AppManager and LysAppManager.

Tests class structure, method signatures, singleton behavior,
and key method behaviors with mocked dependencies.
"""

import inspect
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

from lys.core.consts.component_types import AppComponentTypeEnum
from lys.core.managers.app import AppManager, LysAppManager


def _create_app_manager():
    """Create an AppManager with all dependencies mocked."""
    with patch("lys.core.managers.app.LysAppSettings") as mock_settings, \
         patch("lys.core.managers.app.DatabaseManager") as mock_db, \
         patch("lys.core.managers.app.LysAppRegistry") as mock_registry, \
         patch("lys.core.managers.app.LysGraphqlRegistry") as mock_gql_registry:
        mock_settings.return_value = MagicMock()
        mock_settings.return_value.apps = []
        mock_settings.return_value.permissions = []
        mock_settings.return_value.middlewares = []
        mock_settings.return_value.database = MagicMock()
        mock_db.return_value = MagicMock()
        mock_registry.return_value = MagicMock()
        mock_registry.return_value.services = {}
        mock_registry.return_value.entities = {}
        mock_registry.return_value.fixtures = []
        mock_registry.return_value.routers = []
        mock_registry.return_value.webservices = {}
        mock_gql_registry.return_value = MagicMock()
        manager = AppManager()
    return manager


class TestAppManagerClassStructure:
    """Tests for AppManager class existence and attributes."""

    def test_class_exists(self):
        assert AppManager is not None

    def test_has_get_entity_method(self):
        assert hasattr(AppManager, "get_entity")

    def test_has_get_service_method(self):
        assert hasattr(AppManager, "get_service")

    def test_has_configure_component_types_method(self):
        assert hasattr(AppManager, "configure_component_types")

    def test_has_load_all_components_method(self):
        assert hasattr(AppManager, "load_all_components")

    def test_has_initialize_app_method(self):
        assert hasattr(AppManager, "initialize_app")

    def test_has_load_component_type_method(self):
        assert hasattr(AppManager, "_load_component_type")

    def test_has_load_app_component_method(self):
        assert hasattr(AppManager, "_load_app_component")

    def test_has_load_from_submodules_method(self):
        assert hasattr(AppManager, "_load_from_submodules")

    def test_has_track_loaded_module_method(self):
        assert hasattr(AppManager, "_track_loaded_module")

    def test_has_load_custom_component_files_method(self):
        assert hasattr(AppManager, "_load_custom_component_files")

    def test_has_load_fixtures_in_order_method(self):
        assert hasattr(AppManager, "_load_fixtures_in_order")

    def test_has_register_webservices_to_auth_server_method(self):
        assert hasattr(AppManager, "_register_webservices_to_auth_server")

    def test_has_load_custom_registries_method(self):
        assert hasattr(AppManager, "_load_custom_registries")

    def test_has_load_permissions_method(self):
        assert hasattr(AppManager, "_load_permissions")

    def test_has_load_middlewares_method(self):
        assert hasattr(AppManager, "_load_middlewares")

    def test_has_load_schema_method(self):
        assert hasattr(AppManager, "_load_schema")

    def test_has_app_lifespan_method(self):
        assert hasattr(AppManager, "_app_lifespan")


class TestAppManagerAsyncMethods:
    """Tests for async method signatures."""

    def test_load_fixtures_in_order_is_async(self):
        assert inspect.iscoroutinefunction(AppManager._load_fixtures_in_order)

    def test_register_webservices_to_auth_server_is_async(self):
        assert inspect.iscoroutinefunction(AppManager._register_webservices_to_auth_server)

    def test_app_lifespan_is_callable(self):
        assert callable(AppManager._app_lifespan)


class TestAppManagerInit:
    """Tests for AppManager initialization."""

    def test_has_settings_attribute(self):
        manager = _create_app_manager()
        assert hasattr(manager, "settings")

    def test_has_database_attribute(self):
        manager = _create_app_manager()
        assert hasattr(manager, "database")

    def test_has_registry_attribute(self):
        manager = _create_app_manager()
        assert hasattr(manager, "registry")

    def test_has_graphql_registry_attribute(self):
        manager = _create_app_manager()
        assert hasattr(manager, "graphql_registry")

    def test_has_permissions_attribute(self):
        manager = _create_app_manager()
        assert hasattr(manager, "permissions")
        assert isinstance(manager.permissions, list)

    def test_has_pubsub_attribute(self):
        manager = _create_app_manager()
        assert hasattr(manager, "pubsub")
        assert manager.pubsub is None

    def test_has_component_types_attribute(self):
        manager = _create_app_manager()
        assert hasattr(manager, "component_types")
        assert isinstance(manager.component_types, list)

    def test_has_loaded_modules_attribute(self):
        manager = _create_app_manager()
        assert hasattr(manager, "_loaded_modules")
        assert isinstance(manager._loaded_modules, list)

    def test_on_startup_is_none_initially(self):
        manager = _create_app_manager()
        assert manager._on_startup is None

    def test_on_shutdown_is_none_initially(self):
        manager = _create_app_manager()
        assert manager._on_shutdown is None


class TestLysAppManagerStructure:
    """Tests for LysAppManager singleton."""

    def test_class_exists(self):
        assert LysAppManager is not None

    def test_is_subclass_of_app_manager(self):
        assert issubclass(LysAppManager, AppManager)

    def test_singleton_returns_same_instance(self):
        instance1 = LysAppManager()
        instance2 = LysAppManager()
        assert instance1 is instance2


class TestConfigureComponentTypes:
    """Tests for configure_component_types method."""

    def test_sets_component_types(self):
        manager = _create_app_manager()
        types = [AppComponentTypeEnum.ENTITIES, AppComponentTypeEnum.SERVICES]
        manager.configure_component_types(types)
        assert manager.component_types == types

    def test_empty_list(self):
        manager = _create_app_manager()
        manager.configure_component_types([])
        assert manager.component_types == []


class TestTrackLoadedModule:
    """Tests for _track_loaded_module method."""

    def test_adds_module(self):
        manager = _create_app_manager()
        manager._track_loaded_module("myapp.services")
        assert "myapp.services" in manager._loaded_modules

    def test_avoids_duplicates(self):
        manager = _create_app_manager()
        manager._track_loaded_module("myapp.services")
        manager._track_loaded_module("myapp.services")
        assert manager._loaded_modules.count("myapp.services") == 1

    def test_adds_multiple_modules(self):
        manager = _create_app_manager()
        manager._track_loaded_module("mod1")
        manager._track_loaded_module("mod2")
        assert len(manager._loaded_modules) == 2


class TestGetEntityAndService:
    """Tests for get_entity and get_service delegation."""

    def test_get_entity_delegates_to_registry(self):
        manager = _create_app_manager()
        sentinel = object()
        manager.registry.get_entity.return_value = sentinel
        result = manager.get_entity("users")
        manager.registry.get_entity.assert_called_once_with("users", nullable=False)
        assert result is sentinel

    def test_get_entity_nullable(self):
        manager = _create_app_manager()
        manager.registry.get_entity.return_value = None
        result = manager.get_entity("optional", nullable=True)
        manager.registry.get_entity.assert_called_once_with("optional", nullable=True)
        assert result is None

    def test_get_service_delegates_to_registry(self):
        manager = _create_app_manager()
        sentinel = object()
        manager.registry.get_service.return_value = sentinel
        result = manager.get_service("users")
        manager.registry.get_service.assert_called_once_with("users", nullable=False)
        assert result is sentinel

    def test_get_service_nullable(self):
        manager = _create_app_manager()
        manager.registry.get_service.return_value = None
        result = manager.get_service("optional", nullable=True)
        manager.registry.get_service.assert_called_once_with("optional", nullable=True)
        assert result is None


class TestLoadComponentType:
    """Tests for _load_component_type method."""

    def test_iterates_over_apps(self):
        manager = _create_app_manager()
        manager.settings.apps = ["app1", "app2"]
        with patch.object(manager, "_load_app_component", return_value=True) as mock:
            manager._load_component_type(AppComponentTypeEnum.SERVICES)
        assert mock.call_count == 2

    def test_locks_registry_after_loading(self):
        manager = _create_app_manager()
        manager.settings.apps = []
        manager._load_component_type(AppComponentTypeEnum.ENTITIES)
        manager.registry.lock.assert_called_once_with(AppComponentTypeEnum.ENTITIES)

    def test_reraises_value_error(self):
        manager = _create_app_manager()
        manager.settings.apps = ["bad_app"]
        with patch.object(manager, "_load_app_component", side_effect=ValueError("bad")):
            with pytest.raises(ValueError):
                manager._load_component_type(AppComponentTypeEnum.ENTITIES)

    def test_returns_true_when_loaded(self):
        manager = _create_app_manager()
        manager.settings.apps = ["app1"]
        with patch.object(manager, "_load_app_component", return_value=True):
            result = manager._load_component_type(AppComponentTypeEnum.ENTITIES)
        assert result is True

    def test_returns_false_when_nothing_loaded(self):
        manager = _create_app_manager()
        manager.settings.apps = []
        result = manager._load_component_type(AppComponentTypeEnum.ENTITIES)
        assert result is False


class TestLoadAllComponents:
    """Tests for load_all_components method."""

    def test_returns_bool(self):
        manager = _create_app_manager()
        manager.component_types = []
        with patch.object(manager, "_load_custom_registries"), \
             patch.object(manager, "_load_custom_component_files"):
            result = manager.load_all_components()
        assert isinstance(result, bool)

    def test_calls_load_custom_registries(self):
        manager = _create_app_manager()
        manager.component_types = []
        with patch.object(manager, "_load_custom_registries") as mock, \
             patch.object(manager, "_load_custom_component_files"):
            manager.load_all_components()
        mock.assert_called_once()

    def test_calls_load_custom_component_files(self):
        manager = _create_app_manager()
        manager.component_types = []
        with patch.object(manager, "_load_custom_registries"), \
             patch.object(manager, "_load_custom_component_files") as mock:
            manager.load_all_components()
        mock.assert_called_once()

    def test_returns_false_when_component_fails(self):
        manager = _create_app_manager()
        manager.component_types = [AppComponentTypeEnum.ENTITIES]
        with patch.object(manager, "_load_custom_registries"), \
             patch.object(manager, "_load_component_type", return_value=False), \
             patch.object(manager, "_load_custom_component_files"):
            result = manager.load_all_components()
        assert result is False


class TestLoadFixturesInOrder:
    """Tests for _load_fixtures_in_order async method."""

    @pytest.mark.asyncio
    async def test_returns_true_when_no_fixtures(self):
        manager = _create_app_manager()
        manager.registry.get_fixtures_in_dependency_order.return_value = []
        result = await manager._load_fixtures_in_order()
        assert result is True

    @pytest.mark.asyncio
    async def test_returns_true_when_all_fixtures_load(self):
        manager = _create_app_manager()
        mock_fixture = MagicMock()
        mock_fixture.__name__ = "TestFixture"
        mock_fixture.is_viable.return_value = True
        mock_fixture.load = AsyncMock()
        manager.registry.get_fixtures_in_dependency_order.return_value = [mock_fixture]
        result = await manager._load_fixtures_in_order()
        assert result is True
        mock_fixture.load.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_skips_non_viable_fixtures(self):
        manager = _create_app_manager()
        mock_fixture = MagicMock()
        mock_fixture.__name__ = "SkippedFixture"
        mock_fixture.is_viable.return_value = False
        mock_fixture.load = AsyncMock()
        manager.registry.get_fixtures_in_dependency_order.return_value = [mock_fixture]
        result = await manager._load_fixtures_in_order()
        assert result is True
        mock_fixture.load.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_returns_false_on_exception(self):
        manager = _create_app_manager()
        manager.registry.get_fixtures_in_dependency_order.side_effect = Exception("boom")
        result = await manager._load_fixtures_in_order()
        assert result is False


class TestRegisterWebservicesToAuthServer:
    """Tests for _register_webservices_to_auth_server async method."""

    @pytest.mark.asyncio
    async def test_skips_if_auth_server(self):
        manager = _create_app_manager()
        manager.registry.entities = {"webservice": MagicMock()}
        result = await manager._register_webservices_to_auth_server()
        assert result is True

    @pytest.mark.asyncio
    async def test_skips_if_no_gateway_url(self):
        manager = _create_app_manager()
        manager.registry.entities = {}
        manager.settings.gateway_server_url = None
        manager.settings.service_name = "my_service"
        result = await manager._register_webservices_to_auth_server()
        assert result is True

    @pytest.mark.asyncio
    async def test_skips_if_no_service_name(self):
        manager = _create_app_manager()
        manager.registry.entities = {}
        manager.settings.gateway_server_url = "http://gateway"
        manager.settings.service_name = None
        result = await manager._register_webservices_to_auth_server()
        assert result is True

    @pytest.mark.asyncio
    async def test_skips_if_no_webservices(self):
        manager = _create_app_manager()
        manager.registry.entities = {}
        manager.settings.gateway_server_url = "http://gateway"
        manager.settings.service_name = "svc"
        manager.registry.webservices = {}
        result = await manager._register_webservices_to_auth_server()
        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_on_exception(self):
        manager = _create_app_manager()
        manager.registry.entities = {}
        manager.settings.gateway_server_url = "http://gateway"
        manager.settings.service_name = "svc"
        manager.settings.graphql_schema_name = "graphql"
        manager.settings.secret_key = "secret"
        manager.registry.webservices = {"ws1": {"attributes": {}}}
        with patch("lys.core.managers.app.GraphQLClient") as mock_cls:
            mock_cls.return_value.execute = AsyncMock(side_effect=Exception("network error"))
            result = await manager._register_webservices_to_auth_server()
        assert result is False


class TestLoadPermissions:
    """Tests for _load_permissions method."""

    def test_no_permissions(self):
        manager = _create_app_manager()
        manager.settings.permissions = []
        manager._load_permissions()
        assert manager.permissions == []

    @patch("lys.core.managers.app.import_string")
    def test_loads_permission_class(self, mock_import):
        from lys.core.interfaces.permissions import PermissionInterface

        class FakePermission(PermissionInterface):
            pass

        mock_import.return_value = FakePermission
        manager = _create_app_manager()
        manager.settings.permissions = ["myapp.FakePermission"]
        manager._load_permissions()
        assert len(manager.permissions) == 1
        assert manager.permissions[0] is FakePermission

    @patch("lys.core.managers.app.import_string")
    def test_raises_on_invalid_permission(self, mock_import):
        class NotAPermission:
            pass

        mock_import.return_value = NotAPermission
        manager = _create_app_manager()
        manager.settings.permissions = ["myapp.Bad"]
        with pytest.raises(TypeError, match="must be a subclass of PermissionInterface"):
            manager._load_permissions()


class TestLoadMiddlewares:
    """Tests for _load_middlewares method."""

    def test_no_middlewares(self):
        manager = _create_app_manager()
        manager.settings.middlewares = []
        mock_app = MagicMock()
        manager._load_middlewares(mock_app)
        mock_app.add_middleware.assert_not_called()

    @patch("lys.core.managers.app.import_string")
    def test_adds_middleware(self, mock_import):
        mock_cls = MagicMock()
        mock_cls.__name__ = "CorsMiddleware"
        mock_import.return_value = mock_cls
        manager = _create_app_manager()
        manager.settings.middlewares = ["myapp.Cors"]
        mock_app = MagicMock()
        manager._load_middlewares(mock_app)
        mock_app.add_middleware.assert_called_once_with(mock_cls)


class TestLoadSchema:
    """Tests for _load_schema method."""

    def test_returns_none_when_empty(self):
        manager = _create_app_manager()
        manager.graphql_registry.is_empty = True
        assert manager._load_schema() is None

    def test_returns_schema_when_not_empty(self):
        manager = _create_app_manager()
        manager.graphql_registry.is_empty = False
        manager.graphql_registry.queries = {}
        manager.graphql_registry.mutations = {}
        manager.graphql_registry.subscriptions = {}
        manager.settings.query_depth_limit = 10
        manager.settings.query_alias_limit = 10
        manager.settings.relay_max_results = 100
        manager.settings.graphql_schema_name = "graphql"
        manager.settings.env = MagicMock()
        manager.settings.env.__eq__ = MagicMock(return_value=True)
        with patch("lys.core.managers.app.FederationSchema") as mock_schema, \
             patch("lys.core.managers.app.DatabaseSessionExtension"), \
             patch("lys.core.managers.app.QueryDepthLimiter"), \
             patch("lys.core.managers.app.MaxAliasesLimiter"):
            mock_schema.return_value = MagicMock()
            result = manager._load_schema()
        assert result is not None

    def test_passes_relay_max_results_to_strawberry_config(self):
        """Verify StrawberryConfig(relay_max_results=...) is passed to FederationSchema."""
        from strawberry.schema.config import StrawberryConfig
        manager = _create_app_manager()
        manager.graphql_registry.is_empty = False
        manager.graphql_registry.queries = {}
        manager.graphql_registry.mutations = {}
        manager.graphql_registry.subscriptions = {}
        manager.settings.query_depth_limit = 10
        manager.settings.query_alias_limit = 10
        manager.settings.relay_max_results = 200
        manager.settings.graphql_schema_name = "graphql"
        manager.settings.env = MagicMock()
        manager.settings.env.__eq__ = MagicMock(return_value=True)
        with patch("lys.core.managers.app.FederationSchema") as mock_schema, \
             patch("lys.core.managers.app.DatabaseSessionExtension"), \
             patch("lys.core.managers.app.QueryDepthLimiter"), \
             patch("lys.core.managers.app.MaxAliasesLimiter"):
            mock_schema.return_value = MagicMock()
            manager._load_schema()
            call_kwargs = mock_schema.call_args[1]
            assert "config" in call_kwargs
            assert isinstance(call_kwargs["config"], StrawberryConfig)
            assert call_kwargs["config"].relay_max_results == 200


class TestAppLifespan:
    """Tests for _app_lifespan async context manager."""

    @pytest.mark.asyncio
    async def test_lifespan_yields(self):
        manager = _create_app_manager()
        mock_app = MagicMock()
        manager.database.has_database_configured.return_value = False
        manager.settings.get_plugin_config.return_value = {}
        manager.component_types = []
        manager.registry.initialize_services = AsyncMock()
        manager.registry.shutdown_services = AsyncMock()
        manager._on_startup = None
        manager._on_shutdown = None
        with patch.object(manager, "_register_webservices_to_auth_server", new_callable=AsyncMock):
            async with manager._app_lifespan(mock_app):
                pass
        manager.registry.initialize_services.assert_awaited_once()
        manager.registry.shutdown_services.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_lifespan_calls_startup_callback(self):
        manager = _create_app_manager()
        startup_cb = AsyncMock()
        manager.database.has_database_configured.return_value = False
        manager.settings.get_plugin_config.return_value = {}
        manager.component_types = []
        manager.registry.initialize_services = AsyncMock()
        manager.registry.shutdown_services = AsyncMock()
        manager._on_startup = startup_cb
        manager._on_shutdown = None
        with patch.object(manager, "_register_webservices_to_auth_server", new_callable=AsyncMock):
            async with manager._app_lifespan(MagicMock()):
                pass
        startup_cb.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_lifespan_calls_shutdown_callback(self):
        manager = _create_app_manager()
        shutdown_cb = AsyncMock()
        manager.database.has_database_configured.return_value = False
        manager.settings.get_plugin_config.return_value = {}
        manager.component_types = []
        manager.registry.initialize_services = AsyncMock()
        manager.registry.shutdown_services = AsyncMock()
        manager._on_startup = None
        manager._on_shutdown = shutdown_cb
        with patch.object(manager, "_register_webservices_to_auth_server", new_callable=AsyncMock):
            async with manager._app_lifespan(MagicMock()):
                pass
        shutdown_cb.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_lifespan_does_not_call_initialize_database(self):
        """Verify lifespan no longer calls initialize_database (removed, Alembic handles migrations)."""
        manager = _create_app_manager()
        manager.database.initialize_database = AsyncMock()
        manager.settings.get_plugin_config.return_value = {}
        manager.component_types = []
        manager.registry.initialize_services = AsyncMock()
        manager.registry.shutdown_services = AsyncMock()
        manager._on_startup = None
        manager._on_shutdown = None
        with patch.object(manager, "_register_webservices_to_auth_server", new_callable=AsyncMock):
            async with manager._app_lifespan(MagicMock()):
                pass
        manager.database.initialize_database.assert_not_awaited()


class TestInitializeApp:
    """Tests for initialize_app method."""

    def test_stores_lifecycle_callbacks(self):
        manager = _create_app_manager()
        on_start = AsyncMock()
        on_stop = AsyncMock()
        with patch.object(manager, "load_all_components"), \
             patch.object(manager, "_load_permissions"), \
             patch.object(manager, "_load_middlewares"), \
             patch.object(manager, "_load_schema", return_value=None), \
             patch("lys.core.managers.app.FastAPI") as mock_fa:
            mock_fa.return_value = MagicMock()
            manager.registry.routers = []
            manager.initialize_app("T", "D", "V", on_startup=on_start, on_shutdown=on_stop)
        assert manager._on_startup is on_start
        assert manager._on_shutdown is on_stop

    def test_returns_fastapi_instance(self):
        manager = _create_app_manager()
        with patch.object(manager, "load_all_components"), \
             patch.object(manager, "_load_permissions"), \
             patch.object(manager, "_load_middlewares"), \
             patch.object(manager, "_load_schema", return_value=None), \
             patch("lys.core.managers.app.FastAPI") as mock_fa:
            sentinel = MagicMock()
            mock_fa.return_value = sentinel
            manager.registry.routers = []
            result = manager.initialize_app("T", "D", "V")
        assert result is sentinel
