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
        # Database connection components
        self.type: Optional[str] = None  # "postgresql", "sqlite", "mysql"
        self.host: Optional[str] = None
        self.port: Optional[int] = None
        self.username: Optional[str] = None
        self.password: Optional[str] = None
        self.database: Optional[str] = None

        # SQLAlchemy pool class to use (async pool, will be converted for sync)
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
        return self.type is not None

    def validate(self):
        """
        Validate that required settings are configured.

        Raises:
            ValueError: If required settings are missing or invalid
        """
        if self.type is None:
            raise ValueError(
                "Database must be configured. Use database_settings.configure("
                "type='postgresql', host='...', port=..., username='...', password='...', database='...')"
            )

        # Validate based on database type
        if self.type == "sqlite":
            if not self.database:
                raise ValueError("SQLite requires 'database' parameter (file path)")
        elif self.type in ["postgresql", "mysql"]:
            required = ["host", "port", "username", "password", "database"]
            missing = [field for field in required if getattr(self, field) is None]
            if missing:
                raise ValueError(
                    f"Database type '{self.type}' requires: {', '.join(missing)}"
                )
        else:
            raise ValueError(f"Unsupported database type: {self.type}. Supported: postgresql, sqlite, mysql")


class CelerySettings(BaseSettings):
    """Configuration for Celery task queue."""

    def __init__(self):
        # Broker configuration
        self.broker_url: str = "redis://localhost:6379/0"
        self.result_backend: Optional[str] = "redis://localhost:6379/0"
        self.broker_connection_retry_on_startup: bool = True

        # Task configuration
        self.task_serializer: str = "json"
        self.result_serializer: str = "json"
        self.accept_content: list[str] = ["json"]
        self.task_track_started: bool = True
        self.task_time_limit: int = 3600  # 1 hour
        self.task_soft_time_limit: int = 3000  # 50 minutes

        # Task modules to import
        self.tasks: list[str] = []

        # Beat schedule configuration
        self.beat_schedule: dict[str, dict[str, Any]] = {}

        # Timezone
        self.timezone: str = "UTC"
        self.enable_utc: bool = True

        # Worker configuration
        self.worker_prefetch_multiplier: int = 4
        self.worker_max_tasks_per_child: int = 1000

    def configured(self) -> bool:
        """Check if Celery is configured."""
        return self.broker_url is not None

    def validate(self):
        """
        Validate that required Celery settings are configured.

        Raises:
            ValueError: If broker_url is not configured
        """
        if not self.broker_url:
            raise ValueError(
                "Celery broker_url must be configured. "
                "Use settings.celery.configure(broker_url='redis://...')"
            )


class EmailSettings(BaseSettings):
    """Configuration for email sending."""

    def __init__(self):
        # SMTP server configuration
        self.server: str = "localhost"
        self.port: int = 587
        self.sender: Optional[str] = None
        self.login: Optional[str] = None
        self.password: Optional[str] = None
        self.starttls: bool = True

        # Template configuration
        self.template_path: str = "/templates/emails"

    def configured(self) -> bool:
        """Check if email is configured."""
        return self.sender is not None

    def validate(self):
        """
        Validate that required email settings are configured.

        Raises:
            ValueError: If sender is not configured
        """
        if not self.sender:
            raise ValueError(
                "Email sender must be configured. "
                "Use settings.email.configure(sender='noreply@example.com', ...)"
            )


class StripeSettings(BaseSettings):
    """Configuration for Stripe payment integration."""

    def __init__(self):
        # Master switch for Stripe features
        self.enabled: bool = False

        # API keys
        self.api_key: Optional[str] = None  # Secret key (sk_...)
        self.publishable_key: Optional[str] = None  # Publishable key (pk_...)

        # Webhook configuration
        self.webhook_secret: Optional[str] = None  # Webhook signing secret (whsec_...)

    def configured(self) -> bool:
        """Check if Stripe is properly configured."""
        return self.enabled and self.api_key is not None

    def validate(self):
        """
        Validate that required Stripe settings are configured.

        Raises:
            ValueError: If enabled but api_key is missing
        """
        if self.enabled and not self.api_key:
            raise ValueError(
                "Stripe is enabled but api_key is not configured. "
                "Use settings.stripe.configure(enabled=True, api_key='sk_...')"
            )


class AISettings(BaseSettings):
    """Configuration for AI/LLM integration and tool generation."""

    def __init__(self):
        # Master switch for AI features
        self.enabled: bool = False

        # LLM provider configuration
        self.provider: Optional[str] = None  # "mistral", "openai", "anthropic"
        self.api_key: Optional[str] = None
        self.base_url: Optional[str] = None  # Optional custom endpoint

        # Model configuration
        self.model: Optional[str] = None  # e.g., "mistral-large-latest"

        # Custom system prompt for the application
        self.system_prompt: Optional[str] = None  # Application-specific instructions

        # Routes manifest for frontend navigation
        self.routes_manifest_path: Optional[str] = None  # Path to routes-manifest.json
        self._routes_manifest_cache: Optional[Dict[str, Any]] = None

    def configured(self) -> bool:
        """Check if AI is properly configured for tool generation."""
        return self.enabled and self.api_key is not None

    def get_routes_manifest(self) -> Optional[Dict[str, Any]]:
        """
        Get the routes manifest, loading from file if not cached.

        Returns:
            Routes manifest dict or None if not configured/not found
        """
        if self._routes_manifest_cache is not None:
            return self._routes_manifest_cache

        if not self.routes_manifest_path:
            return None

        from lys.core.utils.routes import load_routes_manifest
        self._routes_manifest_cache = load_routes_manifest(self.routes_manifest_path)
        return self._routes_manifest_cache

    def clear_routes_cache(self):
        """Clear the routes manifest cache to force reload."""
        self._routes_manifest_cache = None

    def validate(self):
        """
        Validate that required AI settings are configured.

        Raises:
            ValueError: If enabled but api_key is missing
        """
        if self.enabled and not self.api_key:
            raise ValueError(
                "AI is enabled but api_key is not configured. "
                "Use settings.ai.configure(enabled=True, api_key='...', provider='mistral')"
            )


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
        self.front_url: Optional[str] = None    # Frontend URL for email links
        self.database: DatabaseSettings = DatabaseSettings()
        self.celery: Optional[CelerySettings] = None  # Celery task queue (optional)
        self.email: EmailSettings = EmailSettings()  # Email configuration
        self.ai: AISettings = AISettings()  # AI/LLM configuration for tool generation
        self.stripe: StripeSettings = StripeSettings()  # Stripe payment integration
        self.log_format:str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

        # graphql configurations
        self.graphql_schema_name: str = "graphql"
        self.query_depth_limit = 10
        self.query_alias_limit = 10

        # Inter-service communication
        self.service_name: Optional[str] = None  # Name of this microservice
        self.auth_server_url: Optional[str] = None  # URL of Auth Server for webservice registration

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
