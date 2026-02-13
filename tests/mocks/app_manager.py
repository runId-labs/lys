"""
Mock AppManager for unit testing.

Provides a lightweight mock of LysAppManager that can be injected
into components using configure_app_manager_for_testing().
"""

from typing import Dict, Type, Any
from unittest.mock import Mock, AsyncMock


class MockRegister:
    """Mock of LysAppRegister."""

    def __init__(self, entities: Dict, services: Dict):
        self.entities = entities
        self.services = services


class MockSettings:
    """Mock of LysAppSettings."""

    def __init__(self):
        self.env = "DEV"
        self.debug = True
        self.database = Mock()
        self.email = Mock()


class MockDatabaseManager:
    """Mock of DatabaseManager."""

    def __init__(self):
        self._session = None

    def get_session(self):
        """Return a mock async context manager for database session."""
        return AsyncMock()

    async def execute_parallel(self, *query_functions):
        """Mock parallel execution - just run sequentially."""
        results = []
        mock_session = AsyncMock()
        for query_func in query_functions:
            result = await query_func(mock_session)
            results.append(result)
        return results

    async def dispose(self):
        """Mock database disposal."""
        pass

    def has_database_configured(self):
        """Mock database configuration check."""
        return True


class MockAppManager:
    """
    Lightweight mock of AppManager for unit tests.

    This mock allows you to register entities and services manually
    and inject it into components using configure_app_manager_for_testing().

    Example:
        # Setup
        mock_app = MockAppManager()
        mock_app.register_entity("users", User)
        mock_app.register_service("users", UserService)

        # Inject into service
        UserService.configure_app_manager_for_testing(mock_app)

        # Now UserService will use the mock instead of singleton
        service = UserService()
        entity_class = service.entity_class  # Returns User
    """

    def __init__(self):
        self._entities: Dict[str, Type] = {}
        self._services: Dict[str, Type] = {}
        self.database = MockDatabaseManager()
        self.settings = MockSettings()
        self.register = MockRegister(self._entities, self._services)
        self.graphql_register = Mock()

    def get_entity(self, name: str):
        """
        Retrieve a registered entity by name.

        Args:
            name: Entity name (typically __tablename__)

        Returns:
            Entity class

        Raises:
            KeyError: If entity is not registered
        """
        if name not in self._entities:
            raise KeyError(
                f"Entity '{name}' not registered in MockAppManager. "
                f"Use mock_app.register_entity('{name}', YourEntity) first."
            )
        return self._entities[name]

    def get_service(self, name: str):
        """
        Retrieve a registered service by name.

        Args:
            name: Service name (typically entity's __tablename__)

        Returns:
            Service class

        Raises:
            KeyError: If service is not registered
        """
        if name not in self._services:
            raise KeyError(
                f"Service '{name}' not registered in MockAppManager. "
                f"Use mock_app.register_service('{name}', YourService) first."
            )
        return self._services[name]

    def register_entity(self, name: str, entity_class: Type):
        """
        Register an entity for testing.

        Args:
            name: Entity name (typically entity.__tablename__)
            entity_class: The entity class to register

        Returns:
            Self for chaining
        """
        self._entities[name] = entity_class
        return self

    def register_service(self, name: str, service_class: Type):
        """
        Register a service for testing.

        Args:
            name: Service name (typically matches entity tablename)
            service_class: The service class to register

        Returns:
            Self for chaining
        """
        self._services[name] = service_class
        return self

    def load_all_components(self):
        """Mock component loading - does nothing."""
        pass
