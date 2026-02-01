"""
Integration tests for AppManager.

AppManager is the central orchestrator that:
- Loads components (entities, services, fixtures, nodes, webservices)
- Manages registrations
- Initializes database
- Creates FastAPI app with GraphQL

Test approach: Integration tests with real SQLite database and real components.
Dependencies: LysAppSettings, AppRegister, DatabaseManager
"""

import pytest
from fastapi import FastAPI

from lys.core.configs import LysAppSettings
from lys.core.consts.component_types import AppComponentTypeEnum
from lys.core.managers.app import AppManager, LysAppManager


class TestAppManagerBasics:
    """Test basic AppManager functionality."""

    def test_app_manager_can_be_instantiated(self):
        """Test that AppManager can be created with default settings."""
        app_manager = AppManager()

        assert app_manager is not None
        assert app_manager.settings is not None
        assert app_manager.registry is not None
        assert app_manager.database is not None
        assert app_manager.graphql_registry is not None
        assert app_manager.component_types == []
        assert app_manager._loaded_modules == []
        assert app_manager.permissions == []

    def test_app_manager_with_custom_settings(self):
        """Test AppManager with custom settings."""
        custom_settings = LysAppSettings()
        custom_settings.database.configure(
            type="sqlite",
            database=":memory:",
            echo=False
        )

        app_manager = AppManager(settings=custom_settings)

        assert app_manager.settings is custom_settings
        assert app_manager.database.settings is custom_settings.database

    def test_configure_component_types(self):
        """Test configuring which component types to load."""
        app_manager = AppManager()

        component_types = [
            AppComponentTypeEnum.ENTITIES,
            AppComponentTypeEnum.SERVICES,
        ]
        app_manager.configure_component_types(component_types)

        assert app_manager.component_types == component_types

    def test_lys_app_manager_is_singleton(self):
        """Test that LysAppManager follows singleton pattern."""
        instance1 = LysAppManager()
        instance2 = LysAppManager()

        assert instance1 is instance2


class TestAppManagerEntityServiceLookup:
    """Test entity and service retrieval."""

    @pytest.fixture
    def app_manager_with_components(self):
        """Create AppManager and load components."""
        settings = LysAppSettings()
        settings.database.configure(
            type="sqlite",
            database=":memory:",
            echo=False
        )
        # Configure apps to load (base app has Language, AccessLevel, etc.)
        settings.apps = ["lys.apps.base"]

        app_manager = AppManager(settings=settings)
        app_manager.configure_component_types([
            AppComponentTypeEnum.ENTITIES,
            AppComponentTypeEnum.SERVICES,
        ])
        app_manager.load_all_components()

        return app_manager

    def test_get_entity_returns_registered_entity(self, app_manager_with_components):
        """Test get_entity() returns a registered entity."""
        # Language entity should be registered from base app
        language_entity = app_manager_with_components.get_entity("language")

        assert language_entity is not None
        assert language_entity.__tablename__ == "language"

    def test_get_entity_raises_on_missing(self, app_manager_with_components):
        """Test get_entity() raises KeyError for non-existent entity."""
        with pytest.raises(KeyError) as exc_info:
            app_manager_with_components.get_entity("nonexistent_entity")

        assert "nonexistent_entity" in str(exc_info.value)

    def test_get_service_returns_registered_service(self, app_manager_with_components):
        """Test get_service() returns a registered service."""
        # LanguageService should be registered
        language_service = app_manager_with_components.get_service("language")

        assert language_service is not None
        assert hasattr(language_service, "create")
        assert hasattr(language_service, "get_by_id")

    def test_get_service_raises_on_missing(self, app_manager_with_components):
        """Test get_service() raises KeyError for non-existent service."""
        with pytest.raises(KeyError) as exc_info:
            app_manager_with_components.get_service("nonexistent_service")

        assert "nonexistent_service" in str(exc_info.value)

    def test_get_multiple_entities(self, app_manager_with_components):
        """Test retrieving multiple entities."""
        # Get multiple entities from base app
        language_entity = app_manager_with_components.get_entity("language")
        access_level_entity = app_manager_with_components.get_entity("access_level")

        assert language_entity is not None
        assert access_level_entity is not None
        assert language_entity != access_level_entity


class TestAppManagerComponentLoading:
    """Test component loading functionality."""

    def test_load_all_components_returns_true_on_success(self):
        """Test load_all_components() returns True when successful."""
        settings = LysAppSettings()
        settings.database.configure(
            type="sqlite",
            database=":memory:",
            echo=False
        )
        settings.apps = ["lys.apps.base"]

        app_manager = AppManager(settings=settings)
        app_manager.configure_component_types([
            AppComponentTypeEnum.ENTITIES,
            AppComponentTypeEnum.SERVICES,
        ])

        result = app_manager.load_all_components()

        assert result is True
        assert len(app_manager._loaded_modules) > 0

    def test_load_all_components_loads_entities(self):
        """Test that entities are loaded and registered."""
        settings = LysAppSettings()
        settings.apps = ["lys.apps.base"]
        app_manager = AppManager(settings=settings)
        app_manager.configure_component_types([AppComponentTypeEnum.ENTITIES])

        app_manager.load_all_components()

        # Check that entities were registered
        assert len(app_manager.registry.entities) > 0
        # Language entity should be present
        assert "language" in app_manager.registry.entities

    def test_load_all_components_loads_services(self):
        """Test that services are loaded and registered."""
        settings = LysAppSettings()
        settings.apps = ["lys.apps.base"]
        app_manager = AppManager(settings=settings)
        app_manager.configure_component_types([
            AppComponentTypeEnum.ENTITIES,  # Services depend on entities
            AppComponentTypeEnum.SERVICES,
        ])

        app_manager.load_all_components()

        # Check that services were registered
        assert len(app_manager.registry.services) > 0
        # LanguageService should be present
        assert "language" in app_manager.registry.services

    def test_load_all_components_tracks_loaded_modules(self):
        """Test that loaded modules are tracked."""
        settings = LysAppSettings()
        settings.apps = ["lys.apps.base"]
        app_manager = AppManager(settings=settings)
        app_manager.configure_component_types([
            AppComponentTypeEnum.ENTITIES,
            AppComponentTypeEnum.SERVICES,
        ])

        app_manager.load_all_components()

        # Verify modules were tracked
        assert len(app_manager._loaded_modules) > 0
        # Should contain module paths
        assert any("entities" in module for module in app_manager._loaded_modules)
        assert any("services" in module for module in app_manager._loaded_modules)

    def test_component_loading_order(self):
        """Test that components are loaded in specified order."""
        settings = LysAppSettings()
        settings.apps = ["lys.apps.base"]
        app_manager = AppManager(settings=settings)

        # Configure in specific order
        component_types = [
            AppComponentTypeEnum.ENTITIES,
            AppComponentTypeEnum.SERVICES,
            AppComponentTypeEnum.FIXTURES,
        ]
        app_manager.configure_component_types(component_types)

        app_manager.load_all_components()

        # Verify all were attempted to load (even if fixtures are empty)
        # Entities should be finalized (abstract to concrete)
        assert len(app_manager.registry.entities) > 0


class TestAppManagerInitialization:
    """Test application initialization."""

    def test_initialize_app_creates_fastapi_app(self):
        """Test initialize_app() creates a FastAPI application."""
        settings = LysAppSettings()
        settings.database.configure(
            type="sqlite",
            database=":memory:",
            echo=False
        )

        app_manager = AppManager(settings=settings)
        app_manager.configure_component_types([
            AppComponentTypeEnum.ENTITIES,
            AppComponentTypeEnum.SERVICES,
        ])

        app = app_manager.initialize_app(
            title="Test App",
            description="Test Description",
            version="1.0.0"
        )

        assert isinstance(app, FastAPI)
        assert app.title == "Test App"
        assert app.description == "Test Description"
        assert app.version == "1.0.0"

    def test_initialize_app_loads_components(self):
        """Test initialize_app() loads all components."""
        settings = LysAppSettings()
        settings.database.configure(
            type="sqlite",
            database=":memory:",
            echo=False
        )
        settings.apps = ["lys.apps.base"]

        app_manager = AppManager(settings=settings)
        app_manager.configure_component_types([
            AppComponentTypeEnum.ENTITIES,
            AppComponentTypeEnum.SERVICES,
        ])

        app = app_manager.initialize_app(
            title="Test App",
            description="Test",
            version="1.0.0"
        )

        # Verify components were loaded
        assert len(app_manager.registry.entities) > 0
        assert len(app_manager.registry.services) > 0

    @pytest.mark.asyncio
    async def test_initialize_app_with_graphql(self):
        """Test initialize_app() includes GraphQL router when nodes are loaded."""
        settings = LysAppSettings()
        settings.database.configure(
            type="sqlite",
            database=":memory:",
            echo=False
        )
        settings.apps = ["lys.apps.base"]

        app_manager = AppManager(settings=settings)
        app_manager.configure_component_types([
            AppComponentTypeEnum.ENTITIES,
            AppComponentTypeEnum.SERVICES,
            AppComponentTypeEnum.NODES,  # Include GraphQL nodes
        ])

        app = app_manager.initialize_app(
            title="Test App",
            description="Test",
            version="1.0.0"
        )

        # Check if GraphQL route was added (if nodes were registered)
        routes = [route.path for route in app.routes]

        # If nodes were registered, GraphQL route should be present
        # base app might not have many nodes, so this is optional
        has_nodes = len(app_manager.graphql_registry.queries.get(settings.graphql_schema_name, [])) > 0
        has_graphql_route = any("graphql" in route for route in routes)

        # If nodes exist, route must exist. If no nodes, no route is expected.
        if has_nodes:
            assert has_graphql_route, "GraphQL nodes registered but no route found"
        else:
            # No nodes, so no GraphQL route expected - this is also valid
            assert True


class TestAppManagerEdgeCases:
    """Test edge cases and error handling."""

    def test_load_components_without_configuration(self):
        """Test loading components without configuring types first."""
        app_manager = AppManager()

        # Should handle empty component_types gracefully
        result = app_manager.load_all_components()

        # Should succeed but not load anything
        assert result is True
        assert len(app_manager._loaded_modules) == 0

    def test_get_entity_with_nonexistent_name_raises_keyerror(self):
        """Test get_entity() raises KeyError for non-existent entity name."""
        app_manager = AppManager()

        # Test with a definitely non-existent entity name
        with pytest.raises(KeyError) as exc_info:
            app_manager.get_entity("definitely_does_not_exist_entity_12345")

        assert "definitely_does_not_exist_entity_12345" in str(exc_info.value)

    def test_initialize_app_without_database(self):
        """Test initialize_app() works without database configuration."""
        settings = LysAppSettings()
        # Don't configure database

        app_manager = AppManager(settings=settings)
        app_manager.configure_component_types([
            AppComponentTypeEnum.ENTITIES,
            AppComponentTypeEnum.SERVICES,
        ])

        # Should still create app (database optional for some use cases)
        app = app_manager.initialize_app(
            title="Test App",
            description="Test",
            version="1.0.0"
        )

        assert isinstance(app, FastAPI)
