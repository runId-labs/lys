from typing import Any, Optional, Dict

from sqlalchemy import Pool

from lys.core.utils.decorators import singleton
from lys.core.consts.environments import EnvironmentEnum


class BaseSettings:
    def configure(self, **kwargs):
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
            else:
                raise ValueError(f"Unknown {self.__class__.__name__} setting: {key}")


class DatabaseSettings(BaseSettings):
    def __init__(self):
        # Default values

        # Database URL connection string
        self.url: Optional[str] = None
        # SQLAlchemy pool class to use
        self.poolclass: Optional[type[Pool]] = None
        # Additional arguments for database connection
        self.connect_args: dict[str, Any] = {}
        # Enable connection health check
        self.pool_pre_ping: bool = True
        # Connection recycles time in seconds
        self.pool_recycle: int = 3600
        #  Enable SQL query logging
        self.echo: bool = False
        # Enable pool logging
        self.echo_pool: bool = False
        # Number of connections to maintain in pool
        self.pool_size: Optional[int] = None
        # Maximum overflow connections
        self.max_overflow: Optional[int] = None

    def configured(self):
        return not self.url

    def validate(self):
        """
        Validate that required settings are configured.

        Raises:
            ValueError: If required settings are missing or invalid
        """
        if not self.url:
            raise ValueError("Database URL must be configured. Use database_settings.configure(url='...')")

        # Additional validation can be added here

    def get_engine_kwargs(self) -> Dict[str, Any]:
        """
        Get keyword arguments for create_async_engine.

        Returns:
            Dict with engine configuration parameters
        """
        self.validate()

        kwargs: Dict[str, Any] = {
            "pool_pre_ping": self.pool_pre_ping,
            "pool_recycle": self.pool_recycle,
            "echo": self.echo,
            "echo_pool": self.echo_pool,
        }

        # Add optional parameters only if they are set
        if self.poolclass is not None:
            kwargs["poolclass"] = self.poolclass

        if self.connect_args:
            kwargs["connect_args"] = self.connect_args

        if self.pool_size is not None:
            kwargs["pool_size"] = self.pool_size

        if self.max_overflow is not None:
            kwargs["max_overflow"] = self.max_overflow

        return kwargs


class AppSettings(BaseSettings):
    def __init__(self):
        # Environment configuration - drives other settings
        self.env: EnvironmentEnum = EnvironmentEnum.DEV

        # Django-like module system for extensibility
        self.apps: list[str] = []   # Modules to load and register
        self.middlewares: list[str] = []    # Middleware classes to apply
        self.permissions: list[str] = []
        self.plugins: dict[str, dict[str, Any]] = {}    # Plugin configurations

        # General application configuration
        self.secret_key: Optional[str] = None    # For cryptographic operations
        self.database: DatabaseSettings = DatabaseSettings()
        self.log_format:str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

        # graphql configurations
        self.query_depth_limit = 5
        self.query_alias_limit = 10

    @property
    def debug(self) -> bool:
        """
        Debug mode automatically determined by environment.

        When enabled, provides:
        - Detailed error messages and stack traces
        - Auto-reload on code changes
        - Verbose logging and validation
        - Development-friendly features

        Environments with debug enabled: DEV, DEMO
        Environments with debug disabled: PREPROD, PROD

        Returns:
            bool: True for development/demo environments, False for production
        """
        return self.env in (EnvironmentEnum.DEV, EnvironmentEnum.DEMO)

    @property
    def testing(self) -> bool:
        """
        Testing mode for unit/integration tests.

        When enabled:
        - Uses in-memory databases by default
        - Disables external service calls
        - Enables test-specific configurations

        Only enabled in DEV environment for local testing.

        Returns:
            bool: True only in DEV environment
        """
        return self.env == EnvironmentEnum.DEV

    @property
    def log_level(self) -> str:
        """
        Logging level automatically set based on environment.

        Log levels by environment:
        - DEV: DEBUG (verbose, all messages)
        - DEMO: INFO (informational messages)
        - PREPROD: WARNING (warnings and errors only)
        - PROD: ERROR (errors only for security/performance)

        Returns:
            str: Python logging level string (DEBUG/INFO/WARNING/ERROR)
        """
        return {
            EnvironmentEnum.DEV: "DEBUG",
            EnvironmentEnum.DEMO: "INFO",
            EnvironmentEnum.PREPROD: "WARNING",
            EnvironmentEnum.PROD: "ERROR"
        }.get(self.env, "INFO")

    def configure(self, **kwargs):
        """
        Configure application settings.

        Args:
            kwargs: Keyword arguments for application configuration, including:
                env: application environment (dev, demo, preprod, prod)
                installed_apps: List of module names to load
                middleware: List of middleware classes to apply
                plugins: Dict of plugin configurations
                secret_key: Secret key for cryptographic operations
                timezone: Default timezone
                language_code: Default language code

        Example:
            app_settings.configure(
                debug=True,
                installed_apps=[
                    "lys.auth",
                    "lys.api.graphql",
                    "myproject.users",
                ],
                middlewares=[
                    "lys.middleware.cors",
                    "lys.middleware.auth",
                ],
                plugins={
                    "redis": {"url": "redis://localhost:6379"},
                    "celery": {"broker": "redis://localhost:6379"},
                }
            )
        """
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
            else:
                raise ValueError(f"Unknown app setting: {key}")

    def add_app(self, app_name: str):
        """
        Add an application to apps.

        Args:
            app_name: Name of the application module
        """
        if app_name not in self.apps:
            self.apps.append(app_name)

    def remove_app(self, app_name: str):
        """
        Remove an application from apps.

        Args:
            app_name: Name of the application module to remove
        """
        if app_name in self.apps:
            self.apps.remove(app_name)

    def add_middleware(self, middleware_class: str):
        """
        Add middleware to the middleware stack.

        Args:
            middleware_class: Full path to middleware class
        """
        if middleware_class not in self.middlewares:
            self.middlewares.append(middleware_class)

    def add_permission(self, permission_class: str):
        """
        Add permission to the permission stack.

        Args:
            permission_class: Full path to permission class
        """
        if permission_class not in self.permissions:
            self.permissions.append(permission_class)

    def configure_plugin(self, plugin_name: str, **config):
        """
        Configure a plugin with specific settings.

        Args:
            plugin_name: Name of the plugin
            **config: Plugin configuration parameters
        """
        self.plugins[plugin_name] = config

    def get_plugin_config(self, plugin_name: str) -> Dict[str, Any]:
        """
        Get configuration for a specific plugin.

        Args:
            plugin_name: Name of the plugin

        Returns:
            Plugin configuration dict
        """
        return self.plugins.get(plugin_name, {})

@singleton
class LysAppSettings(AppSettings):
    pass


settings = LysAppSettings()
