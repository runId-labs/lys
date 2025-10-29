import importlib
import inspect
import logging
import traceback
from contextlib import asynccontextmanager
from typing import List

import strawberry
from fastapi import FastAPI
from graphql import NoSchemaIntrospectionCustomRule
from strawberry.extensions import QueryDepthLimiter, MaxAliasesLimiter, AddValidationRules
from strawberry.fastapi import GraphQLRouter

from lys.core.configs import LysAppSettings, AppSettings
from lys.core.consts.component_types import AppComponentTypeEnum
from lys.core.consts.environments import EnvironmentEnum
from lys.core.contexts import get_context
from lys.core.graphql.registers import GraphqlRegister, LysGraphqlRegister
from lys.core.graphql.types import DefaultQuery
from lys.core.interfaces.middlewares import MiddlewareInterface
from lys.core.interfaces.permissions import PermissionInterface
from lys.core.managers.database import DatabaseManager
from lys.core.registers import AppRegister, LysAppRegister
from lys.core.utils.decorators import singleton


class AppManager:
    def __init__(
            self,
            settings: AppSettings = None,
            register: AppRegister = None,
            graphql_register: GraphqlRegister = None
    ):
        if settings is None:
            settings = LysAppSettings()
        self.settings = settings

        if register is None:
            register = LysAppRegister()
        self.register = register

        self.database = DatabaseManager(settings.database)

        if graphql_register is None:
            graphql_register = LysGraphqlRegister()
        self.graphql_register = graphql_register

        self.component_types: List[AppComponentTypeEnum] = []

        self._loaded_modules: List[str] = []

        self.permissions: List[PermissionInterface] = []

    ####################################################################################################################
    #                                                    PUBLIC
    ####################################################################################################################

    def get_entity(self, name: str):
        """
        Retrieve a registered entity by name.

        This is the standard way to access entities in the lys framework.

        Args:
            name: Entity name to lookup (typically __tablename__)

        Returns:
            Entity class

        Raises:
            KeyError: If entity is not found

        Example:
            user_entity = app_manager.get_entity("users")
        """
        return self.register.get_entity(name)

    def get_service(self, name: str):
        """
        Retrieve a registered service by name.

        This is the standard way to access services in the lys framework.

        Args:
            name: Service name to lookup (typically entity's __tablename__)

        Returns:
            Service class

        Raises:
            KeyError: If service is not found

        Example:
            user_service = app_manager.get_service("users")
        """
        return self.register.get_service(name)

    ####################################################################################################################
    #                                                    PROTECTED
    ####################################################################################################################

    def _load_component_type(self, component_type: AppComponentTypeEnum) -> bool:
        """
        Load a specific component type from all installed apps.

        Args:
            component_type: The type of component to load (e.g., 'services', 'models')

        Returns:
            bool: True if at least one component was loaded successfully
        """
        loaded_count = 0

        for app_string in self.settings.apps:
            try:
                if self._load_app_component(app_string, component_type.value):
                    loaded_count += 1
            except Exception as e:
                logging.warning(f"Failed to load {component_type} from {app_string}: {e}")

        logging.info(f"Loaded {loaded_count} {component_type} components")

        # locked the component type registry because is load now
        self.register.lock(component_type)

        # call extra logique to apply after the registration of a component type
        method_name = "finalize_" + component_type.value

        method = getattr(self.register, method_name, None)
        if callable(method):
            method()

        return loaded_count > 0

    def _load_app_component(self, app_string: str, component_type: str) -> bool:
        """
        Load a specific component type from a single app.

        Supports multiple app structures:
        1. Apps with __submodules__ attribute (current structure)
        2. Direct component modules (e.g., app.services, app.models)
        3. Flat structure (components directly in app module)

        Args:
            app_string: The app module string (e.g., 'lys.modules.auth')
            component_type: The component type to load

        Returns:
            bool: True if component was loaded successfully
        """
        app_modules_string = f"{app_string}.modules"

        try:
            # Load the main app module
            app_module = importlib.import_module(app_modules_string)
        except ModuleNotFoundError as e:
            logging.warning(f"App module not found: {app_modules_string}")
            # installed app loading error must stop the application
            raise e

        loaded = self._load_from_submodules(app_module, component_type)

        return loaded

    def _load_from_submodules(self, app_module, component_type: str) -> bool:
        """Load components using __submodules__ attribute"""
        loaded = False
        for submodule in app_module.__submodules__:
            try:
                component_module_name = f"{submodule.__name__}.{component_type}"
                importlib.import_module(component_module_name)
                self._track_loaded_module(component_module_name)
                logging.info(f"Successfully loaded {component_type} from {submodule.__name__}")
                loaded = True
            except ModuleNotFoundError:
                logging.debug(f"No {component_type} module in {submodule.__name__}")
            except Exception as e:
                logging.error(f"Error loading {component_type} from {submodule.__name__}: {e}")
                traceback.print_exc()
        return loaded

    def _track_loaded_module(self, module_name: str):
        """Track loaded module to avoid duplicates"""
        if module_name not in self._loaded_modules:
            self._loaded_modules.append(module_name)

    async def _load_fixtures_in_order(self) -> bool:
        """
        Load all registered fixtures in dependency order.

        Returns:
            bool: True if all fixtures loaded successfully, False otherwise
        """
        try:
            fixtures_in_order = self.register.get_fixtures_in_dependency_order()

            if not fixtures_in_order:
                logging.info("No fixtures to load")
                return True

            logging.info("=" * 50)
            logging.info("Starting fixture loading process...")
            fixture_names = [f.__name__ for f in fixtures_in_order]
            logging.info(f"Fixtures to load in order: {fixture_names}")

            success_count = 0
            total_count = len(fixtures_in_order)

            for fixture_class in fixtures_in_order:
                try:
                    if fixture_class.is_viable(fixture_class):
                        logging.info(f"Loading fixture: {fixture_class.__name__}")
                        await fixture_class.load()
                        success_count += 1
                        logging.info(f"✓ Successfully loaded fixture: {fixture_class.__name__}")
                    else:
                        logging.info(
                            f"⚠ Skipping fixture {fixture_class.__name__} (not viable for current environment)")
                        success_count += 1  # Count as success since it's intentionally skipped
                except Exception as e:
                    logging.error(f"✗ Failed to load fixture {fixture_class.__name__}: {e}", exc_info=True)
                    # Continue loading other fixtures even if one fails

            success = success_count == total_count
            logging.info("=" * 50)
            logging.info(f"Fixture loading completed - Success: {success}")
            logging.info(f"Successfully loaded: {success_count}/{total_count} fixtures")
            logging.info("=" * 50)

            return success

        except Exception as e:
            logging.error(f"Error in fixture loading process: {e}")
            return False

    def _load_permissions(self):
        """Load permission classes from configured permission modules."""
        if not len(self.settings.permissions):
            logging.info("No permissions configured")
            return

        logging.info("=" * 50)
        logging.info("Starting permission loading process...")
        logging.info(f"Permission modules to load: {self.settings.permissions}")

        loaded_count = 0
        total_modules = len(self.settings.permissions)

        for permission_import in self.settings.permissions:
            try:
                logging.info(f"Loading permission module: {permission_import}")
                permission_module = importlib.import_module(permission_import)

                module_permissions = [
                    cls for name, cls in inspect.getmembers(permission_module, inspect.isclass)
                    if issubclass(cls, PermissionInterface) and cls is not PermissionInterface
                ]

                self.permissions += module_permissions
                loaded_count += 1

                permission_names = [cls.__name__ for cls in module_permissions]
                logging.info(f"✓ Loaded {len(module_permissions)} permissions from {permission_import}: {permission_names}")

            except Exception as e:
                logging.error(f"✗ Failed to load permission module {permission_import}: {e}")

        logging.info("=" * 50)
        logging.info(f"Permission loading completed - Success: {loaded_count}/{total_modules} modules")
        total_permissions = len(self.permissions)
        permission_names = [cls.__name__ for cls in self.permissions]
        logging.info(f"Total permissions loaded: {total_permissions} ({permission_names})")
        logging.info("=" * 50)

    def _load_middlewares(self, app: FastAPI):
        """Load middleware classes from configured middleware modules."""
        if not self.settings.permissions:
            logging.info("No middlewares configured")
            return

        logging.info("=" * 50)
        logging.info("Starting middleware loading process...")
        logging.info(f"Middleware modules to load: {self.settings.middlewares}")

        loaded_count = 0
        total_modules = len(self.settings.middlewares)

        middlewares = []

        for middleware_import in self.settings.middlewares:
            try:
                logging.info(f"Loading middleware module: {middleware_import}")
                middleware_module = importlib.import_module(middleware_import)

                module_middlewares = [
                    cls for name, cls in inspect.getmembers(middleware_module, inspect.isclass)
                    if issubclass(cls, MiddlewareInterface) and cls is not MiddlewareInterface
                ]

                for middleware in module_middlewares:
                    app.add_middleware(middleware)

                middlewares += module_middlewares
                loaded_count += 1

                middleware_import_names = [cls.__name__ for cls in module_middlewares]
                logging.info(f"✓ Loaded {len(module_middlewares)} middlewares from {middleware_import}: {middleware_import_names}")

            except Exception as e:
                logging.error(f"✗ Failed to load middleware module {middleware_import}: {e}")

        logging.info("=" * 50)
        logging.info(f"Middleware loading completed - Success: {loaded_count}/{total_modules} modules")
        total_middlewares = len(middlewares)
        middleware_names = [cls.__name__ for cls in middlewares]
        logging.info(f"Total middlewares loaded: {total_middlewares} ({middleware_names})")
        logging.info("=" * 50)

    def _load_schema_mapping(self):
        schema_mapping =  None
        if not self.graphql_register.is_empty:
            extensions = [
                # security: limit query depth to avoid high query complexity
                QueryDepthLimiter(self.settings.query_depth_limit),
                # security: limit number of alias in a same query to avoid malicious batch requests
                MaxAliasesLimiter(self.settings.query_alias_limit)
            ]

            # secure graphql schema on non-dev environment
            if not self.settings.env == EnvironmentEnum.DEV:
                extensions.append(AddValidationRules([NoSchemaIntrospectionCustomRule]))

            schema_mapping = {}
            register_mapping = {
                "Query": self.graphql_register.queries,
                "Mutation": self.graphql_register.mutations,
                "Subscription": self.graphql_register.subscriptions,
            }
            for type_name, schema_type in register_mapping.items():
                for schema_name in schema_type.keys():
                    if schema_mapping.get(schema_name) is None:
                        schema_mapping[schema_name] = {}

                    l = schema_type[schema_name]
                    if len(l) > 0:
                        l.reverse()
                        schema_mapping[schema_name][type_name] = strawberry.type(type(type_name, tuple(l), {}))

            for schema_name, value in schema_mapping.items():
                schema_mapping[schema_name] = strawberry.Schema(
                    value.get("Query", DefaultQuery),
                    value.get("Mutation"),
                    value.get("Subscription"),
                    extensions=extensions,
                )
        return schema_mapping

    @asynccontextmanager
    async def _app_lifespan(self, app: FastAPI):
        """
        FastAPI application lifespan context manager.
        """

        # Phase 1: Initialize database if configured
        if self.database.has_database_configured():
            await self.database.initialize_database()

        # Phase 2: Load fixtures in dependency order (after database is ready)
        if AppComponentTypeEnum.FIXTURES in self.component_types:
            await self._load_fixtures_in_order()

        yield
        # shutdown

    ####################################################################################################################
    #                                                    PUBLIC
    ####################################################################################################################

    def configure_component_types(self, component_types: List[AppComponentTypeEnum]):
        self.component_types = component_types

    def load_all_components(self) -> bool:
        """
        Load all component types from installed apps.

        Returns:
            bool: True if all components loaded successfully, False otherwise
        """
        logging.info("=" * 50)
        logging.info("Starting component loading process...")
        logging.info(f"Apps to process: {self.settings.apps}")
        logging.info(f"Component types: {self.component_types}")

        success = True
        for component_type in self.component_types:
            if not self._load_component_type(component_type):
                success = False

        # Summary logging
        logging.info("=" * 50)
        logging.info(f"Component loading completed - Success: {success}")
        logging.info(f"Total modules loaded: {len(self._loaded_modules)}")
        logging.info(f"Loaded modules: {self._loaded_modules}")
        logging.info(f"Registry summary:")
        logging.info(f"  - Services: {len(self.register.services)} ({list(self.register.services.keys())})")
        logging.info(f"  - Entities: {len(self.register.entities)} ({list(self.register.entities.keys())})")
        fixture_names = [f.__name__ for f in self.register.fixtures]
        logging.info(f"  - Fixtures: {len(self.register.fixtures)} ({fixture_names})")
        logging.info("=" * 50)

        return success

    def initialize_app(self, title: str, description: str, version:str ):
        # Phase 1: Load all components (services, entities, fixtures)
        self.load_all_components()

        # Phase 2: load permissions
        self._load_permissions()

        # Phase 3: create fastapi application
        app = FastAPI(
            title=title,
            description=description,
            version=version,
            debug=self.settings.debug,
            lifespan=self._app_lifespan
        )

        # Phase 4: load middlewares
        self._load_middlewares(app)

        # Phase 5: load graphql api
        schema_mapping = self._load_schema_mapping()

        if schema_mapping is not None:
            for key, schema in schema_mapping.items():
                graphql_app = GraphQLRouter(
                    schema,
                    context_getter=get_context,
                    # security enabled graphql ide only on dev environment
                    graphql_ide="graphiql" if self.settings.env == EnvironmentEnum.DEV else None
                )

                app.include_router(graphql_app, prefix=f"/{key}")

        return app


@singleton
class LysAppManager(AppManager):
    pass
