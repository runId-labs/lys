import importlib
import logging
import traceback
from contextlib import asynccontextmanager
from typing import List, Optional, Callable, Awaitable

import strawberry
from fastapi import FastAPI
from graphql import NoSchemaIntrospectionCustomRule
from strawberry.extensions import QueryDepthLimiter, MaxAliasesLimiter, AddValidationRules
from strawberry.fastapi import GraphQLRouter
from strawberry.federation import Schema as FederationSchema

from lys.core.configs import LysAppSettings, AppSettings
from lys.core.consts.component_types import AppComponentTypeEnum
from lys.core.consts.environments import EnvironmentEnum
from lys.core.contexts import get_context
from lys.core.graphql.extensions import DatabaseSessionExtension
from lys.core.graphql.registries import GraphqlRegistry, LysGraphqlRegistry
from lys.core.graphql.types import DefaultQuery
from lys.core.interfaces.permissions import PermissionInterface
from lys.core.managers.database import DatabaseManager
from lys.core.managers.pubsub import PubSubManager
from lys.core.models import PubSubConfig
from lys.core.registries import AppRegistry, LysAppRegistry, CustomRegistry
from lys.core.graphql.client import GraphQLClient
from lys.core.utils.decorators import singleton
from lys.core.utils.import_string import import_string


class AppManager:
    def __init__(
            self,
            settings: AppSettings = None,
            registry: AppRegistry = None,
            graphql_registry: GraphqlRegistry = None
    ):
        if settings is None:
            settings = LysAppSettings()
        self.settings = settings

        if registry is None:
            registry = LysAppRegistry()
        self.registry = registry

        self.database = DatabaseManager(settings.database)

        if graphql_registry is None:
            graphql_registry = LysGraphqlRegistry()
        self.graphql_registry = graphql_registry

        self.component_types: List[AppComponentTypeEnum] = []

        self._loaded_modules: List[str] = []

        self.permissions: List[PermissionInterface] = []

        self.pubsub: Optional[PubSubManager] = None

        # Lifecycle callbacks (set via initialize_app)
        self._on_startup: Optional[Callable[[], Awaitable[None]]] = None
        self._on_shutdown: Optional[Callable[[], Awaitable[None]]] = None

    ####################################################################################################################
    #                                                    PUBLIC
    ####################################################################################################################

    def get_entity(self, name: str, nullable: bool = False):
        """
        Retrieve a registered entity by name.

        This is the standard way to access entities in the lys framework.

        Args:
            name: Entity name to lookup (typically __tablename__)
            nullable: If True, return None instead of raising KeyError when not found

        Returns:
            Entity class, or None if nullable=True and entity not found

        Raises:
            KeyError: If entity is not found and nullable=False

        Example:
            user_entity = app_manager.get_entity("users")
            optional_entity = app_manager.get_entity("optional_table", nullable=True)
        """
        return self.registry.get_entity(name, nullable=nullable)

    def get_service(self, name: str, nullable: bool = False):
        """
        Retrieve a registered service by name.

        This is the standard way to access services in the lys framework.

        Args:
            name: Service name to lookup (typically entity's __tablename__)
            nullable: If True, return None instead of raising KeyError when not found

        Returns:
            Service class or None if nullable=True and not found

        Raises:
            KeyError: If service is not found and nullable=False

        Example:
            user_service = app_manager.get_service("users")
            optional_service = app_manager.get_service("optional_thing", nullable=True)
        """
        return self.registry.get_service(name, nullable=nullable)

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
            except (ValueError, TypeError, ModuleNotFoundError) as e:
                # ValueError/TypeError/ModuleNotFoundError indicate configuration errors - these are fatal
                logging.error(f"❌ FATAL: Configuration error in {app_string}: {e}")
                raise  # Re-raise to stop application startup
            except Exception as e:
                logging.warning(f"Failed to load {component_type} from {app_string}: {e}")

        logging.info(f"Loaded {loaded_count} {component_type} components")

        # locked the component type registry because is load now
        self.registry.lock(component_type)

        # call extra logique to apply after the registration of a component type
        method_name = "finalize_" + component_type.value

        method = getattr(self.registry, method_name, None)
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
                module = importlib.import_module(component_module_name)
                self._track_loaded_module(component_module_name)

                # Collect APIRouter from webservices modules
                if component_type == "webservices":
                    router = getattr(module, "router", None)
                    if router is not None:
                        self.registry.routers.append(router)
                        logging.info(f"✓ Collected REST router from {component_module_name}")

                logging.info(f"Successfully loaded {component_type} from {submodule.__name__}")
                loaded = True
            except ModuleNotFoundError as e:
                # Distinguish between:
                # 1. Module file doesn't exist (e.g., services.py not found) → skip silently
                # 2. Import error inside the module (e.g., import mollie fails) → FATAL
                if e.name == component_module_name or component_module_name.endswith(f".{e.name}"):
                    # Case 1: The module file itself doesn't exist - this is normal
                    logging.debug(f"No {component_type} module in {submodule.__name__}")
                else:
                    # Case 2: An import inside the module failed - this is a configuration error
                    logging.error(f"❌ FATAL: Import error in {component_module_name}: {e}")
                    traceback.print_exc()
                    raise
            except (ValueError, TypeError, ImportError) as e:
                # ValueError/TypeError/ImportError indicate configuration errors (duplicate webservices, invalid imports, etc)
                # These should be fatal as they indicate programmer errors
                logging.error(f"❌ FATAL: Configuration error in {submodule.__name__}: {e}")
                traceback.print_exc()
                raise  # Re-raise to stop application startup
            except Exception as e:
                logging.error(f"Error loading {component_type} from {submodule.__name__}: {e}")
                traceback.print_exc()
        return loaded

    def _track_loaded_module(self, module_name: str):
        """Track loaded module to avoid duplicates"""
        if module_name not in self._loaded_modules:
            self._loaded_modules.append(module_name)

    def _load_custom_component_files(self) -> None:
        """
        Load custom component files from all app modules.

        For each custom registry (e.g., "validators", "downgraders"), this method
        attempts to import the corresponding file from each app submodule.

        Example: If "validators" registry is registered, this will try to import:
        - lys.apps.licensing.modules.rule.validators
        - lys.apps.licensing.modules.subscription.validators
        - etc.
        """
        custom_files = self.registry.get_custom_component_files()
        if not custom_files:
            return

        logging.info("=" * 50)
        logging.info("Loading custom component files...")
        logging.info(f"Custom component types: {custom_files}")

        loaded_count = 0

        for app_string in self.settings.apps:
            app_modules_string = f"{app_string}.modules"

            try:
                app_module = importlib.import_module(app_modules_string)
            except ModuleNotFoundError:
                continue

            if not hasattr(app_module, '__submodules__'):
                continue

            for submodule in app_module.__submodules__:
                for custom_file in custom_files:
                    try:
                        component_module_name = f"{submodule.__name__}.{custom_file}"
                        importlib.import_module(component_module_name)
                        self._track_loaded_module(component_module_name)
                        logging.info(f"✓ Loaded {custom_file} from {submodule.__name__}")
                        loaded_count += 1
                    except ModuleNotFoundError:
                        # File doesn't exist in this module, that's OK
                        logging.debug(f"No {custom_file} module in {submodule.__name__}")
                    except Exception as e:
                        logging.error(f"✗ Error loading {custom_file} from {submodule.__name__}: {e}")
                        traceback.print_exc()

        logging.info(f"Loaded {loaded_count} custom component files")
        logging.info("=" * 50)

    async def _load_fixtures_in_order(self) -> bool:
        """
        Load all registered fixtures in dependency order.

        Returns:
            bool: True if all fixtures loaded successfully, False otherwise
        """
        try:
            fixtures_in_order = self.registry.get_fixtures_in_dependency_order()

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

    async def _register_webservices_to_auth_server(self) -> bool:
        """
        Register webservices with Auth Server at startup.

        This is called by business microservices to register their webservices
        with the Auth Server. The Auth Server stores these for JWT token generation.

        Skipped if:
        - gateway_server_url is not configured
        - service_name is not configured
        - This is the Auth Server itself (has webservice entity)

        Returns:
            bool: True if registration succeeded or was skipped, False on error
        """

        # Skip if this is Auth Server (has webservice entity)
        if "webservice" in self.registry.entities:
            logging.debug("Skipping webservice registration: this is Auth Server")
            return True

        # Skip if not configured
        if not self.settings.gateway_server_url or not self.settings.service_name:
            logging.debug("Skipping webservice registration: gateway_server_url or service_name not configured")
            return True

        # Get webservices from registry
        webservices = self.registry.webservices
        if not webservices:
            logging.debug("No webservices to register")
            return True

        logging.info("=" * 50)
        logging.info("Registering webservices with Gateway...")
        logging.info(f"Gateway URL: {self.settings.gateway_server_url}")
        logging.info(f"Service name: {self.settings.service_name}")
        logging.info(f"Webservices to register: {list(webservices.keys())}")

        try:
            # Build webservices payload for GraphQL mutation
            # Convert snake_case to camelCase for GraphQL
            webservices_input = []
            for ws_id, ws_config in webservices.items():
                attrs = ws_config.get("attributes", {})
                webservices_input.append({
                    "id": ws_id,
                    "attributes": {
                        "enabled": attrs.get("enabled", True),
                        "publicType": attrs.get("public_type"),
                        "isLicenced": attrs.get("is_licenced", False),
                        "accessLevels": attrs.get("access_levels", []),
                        "operationType": attrs.get("operation_type"),
                        "aiTool": attrs.get("ai_tool"),
                    }
                })

            # GraphQL mutation
            mutation = """
                mutation RegisterWebservices($webservices: [WebserviceFixturesInput!]!) {
                    registerWebservices(webservices: $webservices) {
                        success
                        registeredCount
                        message
                    }
                }
            """

            # Call GraphQL endpoint
            client = GraphQLClient(
                url=f"{self.settings.gateway_server_url}/{self.settings.graphql_schema_name}",
                secret_key=self.settings.secret_key,
                service_name=self.settings.service_name,
                verify_ssl=not self.settings.debug,
            )
            result = await client.execute(mutation, {"webservices": webservices_input})

            if "errors" in result:
                logging.error(f"GraphQL errors: {result['errors']}")
                return False

            data = result.get("data", {}).get("registerWebservices", {})
            if data.get("success"):
                logging.info(f"✓ Successfully registered {data.get('registeredCount', 0)} webservices")
            else:
                logging.error(f"Registration failed: {data.get('message', 'Unknown error')}")
                return False

            logging.info("=" * 50)
            return True

        except Exception as e:
            logging.error(f"Error registering webservices with Auth Server: {e}")
            return False

    def _load_custom_registries(self) -> None:
        """
        Load custom registries from apps and add them to AppRegistry.

        This is called during app initialization, before loading app modules.
        Custom registries are discovered from __registries__ attribute in each app's __init__.py.

        Example app __init__.py:
            from lys.apps.licensing.registries import ValidatorRegistry, DowngraderRegistry

            __registries__ = [
                ValidatorRegistry,
                DowngraderRegistry,
            ]
        """
        loaded_count = 0

        for app_string in self.settings.apps:
            try:
                app_module = importlib.import_module(app_string)
                registries = getattr(app_module, '__registries__', [])

                for registry_class in registries:
                    # Verify it's a CustomRegistry subclass
                    if not issubclass(registry_class, CustomRegistry):
                        raise TypeError(f"'{registry_class.__name__}' must be a subclass of CustomRegistry")

                    # Instantiate and add to AppRegistry
                    registry = registry_class()
                    self.registry.add_custom_registry(registry)
                    loaded_count += 1

            except ModuleNotFoundError:
                logging.debug(f"App module not found: {app_string}")
            except Exception as e:
                logging.error(f"✗ Failed to load custom registries from '{app_string}': {e}")
                raise

        if loaded_count > 0:
            logging.info(f"Loaded {loaded_count} custom registries")

    def _load_permissions(self):
        """
        Load permission classes from configured permission class paths.

        Permissions are specified as full dotted paths to permission classes.
        Example: "lys.apps.user_auth.permissions.UserAuthPermission"
        """
        if not len(self.settings.permissions):
            logging.info("No permissions configured")
            return

        logging.info("=" * 50)
        logging.info("Starting permission loading process...")
        logging.info(f"Permission classes to load: {self.settings.permissions}")

        loaded_count = 0

        for permission_path in self.settings.permissions:
            try:
                permission_class = import_string(permission_path)

                # Verify it implements PermissionInterface
                if not issubclass(permission_class, PermissionInterface):
                    raise TypeError(
                        f"'{permission_class.__name__}' must be a subclass of PermissionInterface"
                    )

                self.permissions.append(permission_class)
                loaded_count += 1
                logging.info(f"✓ Loaded permission: {permission_class.__name__}")

            except Exception as e:
                logging.error(f"✗ Failed to load permission '{permission_path}': {e}")
                raise

        logging.info("=" * 50)
        logging.info(f"Permission loading completed: {loaded_count} permissions")
        permission_names = [cls.__name__ for cls in self.permissions]
        logging.info(f"Permissions loaded: {permission_names}")
        logging.info("=" * 50)

    def _load_middlewares(self, app: FastAPI):
        """
        Load middleware classes from configured middleware class paths.

        Middlewares are specified as full dotted paths to middleware classes.
        Example: "lys.core.middlewares.cors.LysCorsMiddleware"
        """
        if not self.settings.middlewares:
            logging.info("No middlewares configured")
            return

        logging.info("=" * 50)
        logging.info("Starting middleware loading process...")
        logging.info(f"Middlewares to load: {self.settings.middlewares}")

        loaded_count = 0

        for middleware_path in self.settings.middlewares:
            try:
                middleware_class = import_string(middleware_path)
                app.add_middleware(middleware_class)
                loaded_count += 1
                logging.info(f"✓ Loaded middleware: {middleware_class.__name__}")

            except Exception as e:
                logging.error(f"✗ Failed to load middleware '{middleware_path}': {e}")
                raise

        logging.info("=" * 50)
        logging.info(f"Middleware loading completed: {loaded_count} middlewares")
        logging.info("=" * 50)

    def _load_schema(self):
        """
        Load the single GraphQL schema.

        The schema name is taken from settings.graphql_schema_name.
        All queries, mutations, and subscriptions are registered to this single schema.

        Returns:
            strawberry.Schema or None if no GraphQL components are registered
        """
        if self.graphql_registry.is_empty:
            return None

        # Configure extensions
        extensions = [
            # Database session management: opens session at start of GraphQL operation
            # and keeps it open for entire resolution (including nested fields)
            DatabaseSessionExtension(),
            # security: limit query depth to avoid high query complexity
            QueryDepthLimiter(self.settings.query_depth_limit),
            # security: limit number of alias in a same query to avoid malicious batch requests
            MaxAliasesLimiter(self.settings.query_alias_limit)
        ]

        # secure graphql schema on non-dev environment
        if not self.settings.env == EnvironmentEnum.DEV:
            extensions.append(AddValidationRules([NoSchemaIntrospectionCustomRule]))

        # Build schema types from registered components
        schema_name = self.settings.graphql_schema_name
        schema_types = {}

        registry_mapping = {
            "Query": self.graphql_registry.queries,
            "Mutation": self.graphql_registry.mutations,
            "Subscription": self.graphql_registry.subscriptions,
        }

        for type_name, schema_type in registry_mapping.items():
            component_list = schema_type.get(schema_name, [])
            if len(component_list) > 0:
                component_list.reverse()
                schema_types[type_name] = strawberry.type(type(type_name, tuple(component_list), {}))

        # Create and return the federation-compatible schema
        # FederationSchema exposes _service { sdl } for Apollo Gateway/Router
        # while remaining fully compatible with standalone usage
        return FederationSchema(
            schema_types.get("Query", DefaultQuery),
            schema_types.get("Mutation"),
            schema_types.get("Subscription"),
            extensions=extensions,
        )

    @asynccontextmanager
    async def _app_lifespan(self, app: FastAPI):
        """
        FastAPI application lifespan context manager.
        """

        # Phase 1: Initialize database if configured
        if self.database.has_database_configured():
            await self.database.initialize_database()

        # Phase 2: Initialize PubSub if configured
        pubsub_config = self.settings.get_plugin_config("pubsub")
        if pubsub_config:
            validated_config = PubSubConfig(**pubsub_config)
            self.pubsub = PubSubManager(
                redis_url=validated_config.redis_url,
                channel_prefix=validated_config.channel_prefix
            )
            await self.pubsub.initialize()

        # Phase 3: Load fixtures in dependency order (after database is ready)
        if AppComponentTypeEnum.FIXTURES in self.component_types:
            await self._load_fixtures_in_order()

        # Phase 4: Register webservices with Auth Server (for business microservices)
        await self._register_webservices_to_auth_server()

        # Phase 5: Initialize services (async lifecycle hooks)
        await self.registry.initialize_services()

        # Phase 6: Call custom startup callback if provided
        if self._on_startup:
            await self._on_startup()

        yield

        # Shutdown: call custom shutdown callback first
        if self._on_shutdown:
            await self._on_shutdown()

        # Shutdown: call shutdown methods for component types that support it
        await self.registry.shutdown_services()

        # Shutdown PubSub if initialized
        if self.pubsub:
            await self.pubsub.shutdown()

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
        # Phase 0: Load custom registries first (before app components)
        self._load_custom_registries()

        logging.info("=" * 50)
        logging.info("Starting component loading process...")
        logging.info(f"Apps to process: {self.settings.apps}")
        logging.info(f"Component types: {self.component_types}")

        success = True
        for component_type in self.component_types:
            if not self._load_component_type(component_type):
                success = False

        # Load custom component files (validators.py, downgraders.py, etc.)
        self._load_custom_component_files()

        # Summary logging
        logging.info("=" * 50)
        logging.info(f"Component loading completed - Success: {success}")
        logging.info(f"Total modules loaded: {len(self._loaded_modules)}")
        logging.info(f"Loaded modules: {self._loaded_modules}")
        logging.info(f"Registry summary:")
        logging.info(f"  - Services: {len(self.registry.services)} ({list(self.registry.services.keys())})")
        logging.info(f"  - Entities: {len(self.registry.entities)} ({list(self.registry.entities.keys())})")
        fixture_names = [f.__name__ for f in self.registry.fixtures]
        logging.info(f"  - Fixtures: {len(self.registry.fixtures)} ({fixture_names})")
        logging.info("=" * 50)

        return success

    def initialize_app(
        self,
        title: str,
        description: str,
        version: str,
        on_startup: Optional[Callable[[], Awaitable[None]]] = None,
        on_shutdown: Optional[Callable[[], Awaitable[None]]] = None,
    ):
        # Store lifecycle callbacks
        self._on_startup = on_startup
        self._on_shutdown = on_shutdown

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
        schema = self._load_schema()

        if schema is not None:
            # Create context getter that includes app_manager reference
            def context_getter_with_app_manager():
                context = get_context()
                context.app_manager = self
                return context

            graphql_app = GraphQLRouter(
                schema,
                context_getter=context_getter_with_app_manager,
                # security enabled graphql ide only on dev environment
                graphql_ide="graphiql" if self.settings.env == EnvironmentEnum.DEV else None
            )

            app.include_router(graphql_app, prefix=f"/{self.settings.graphql_schema_name}")

        # Phase 6: Mount REST routers
        for router in self.registry.routers:
            app.include_router(router)
            logging.info(f"✓ Mounted REST router: {router.prefix}")

        return app


@singleton
class LysAppManager(AppManager):
    pass
