import os
import uvicorn
from pathlib import Path

from fastapi_cli.discover import get_import_data
from fastapi_cli.exceptions import FastAPICLIException

from lys.core.consts.component_types import AppComponentTypeEnum


def run_fast_app(
        host: str,
        port: int,
        reload: bool,
        workers: int,
        app_path: Path,
        ssl_certfile: str | None,
        ssl_keyfile: str | None,
        timeout_graceful_shutdown: int | None = None,
):
    """
    Launch the FastAPI application with configured settings.

    Args:
        host: Host to bind the server to
        port: Port to bind the server to
        reload: Enable auto-reload on code changes
        workers: Number of worker processes
        app_path: Path to FastAPI application file
        ssl_certfile: Path to the SSL certificate file
        ssl_keyfile: Path to the SSL key file
        timeout_graceful_shutdown: Seconds to wait for connections to close on shutdown (None = wait forever)

    Raises:
        typer.Exit: If the settings file, the app file is not found, or FastAPI app discovery fails
    """

    if not app_path.exists():
        raise Exception(f"App file not found: {app_path}")

    try:
        import_data = get_import_data(path=app_path)
        import_string = import_data.import_string
    except FastAPICLIException as e:
        raise Exception(f"Failed to discover FastAPI app: {e}")

    uvicorn.run(
        app=import_string,
        host=host,
        port=port,
        reload=reload,
        workers=workers,
        ssl_certfile=ssl_certfile,
        ssl_keyfile=ssl_keyfile,
        timeout_graceful_shutdown=timeout_graceful_shutdown,
    )


def export_graphql_schema(
    output_path: Path,
    settings_module: str = "settings"
):
    """
    Export the GraphQL schema to a file.

    This function initializes the app_manager with the necessary components
    (entities, services, nodes, webservices) and exports the GraphQL schema
    to the specified output path.

    This function only calls configure_core() from the settings module, which
    configures apps, middlewares, permissions, and plugins without initializing
    database, Celery, or email services.

    Args:
        output_path: Path where the schema file will be written (e.g., ./schema/schema.graphql)
        settings_module: Module path to import settings from (default: "settings")

    Raises:
        Exception: If settings module cannot be imported or schema generation fails
    """
    import importlib
    from lys.core.managers.app import LysAppManager

    # Import settings module and call configure_core for minimal configuration
    try:
        settings = importlib.import_module(settings_module)
        # Call configure_core if it exists (for schema export, we don't need database/celery/email)
        if hasattr(settings, "configure_core"):
            settings.configure_core()
        else:
            raise Exception(f"Function 'configure_core' not found in '{settings_module}'")
    except ImportError as e:
        raise Exception(f"Failed to import settings module '{settings_module}': {e}")

    # Initialize app_manager with required components
    app_manager = LysAppManager()
    app_manager.configure_component_types([
        AppComponentTypeEnum.ENTITIES,
        AppComponentTypeEnum.SERVICES,
        AppComponentTypeEnum.NODES,
        AppComponentTypeEnum.WEBSERVICES,
    ])

    # Load all components
    app_manager.load_all_components()

    # Load the GraphQL schema
    schema = app_manager._load_schema()

    if not schema:
        raise Exception("No GraphQL schema found. Make sure you have registered queries/mutations.")

    # Create output directory if it doesn't exist
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Generate the schema SDL (Schema Definition Language)
    schema_str = str(schema)

    # Write schema to file
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(schema_str)

    print(f"GraphQL schema exported to: {output_path}")
    print(f"Schema export completed successfully!")


def _find_alembic_ini() -> str:
    """
    Find alembic.ini in the current working directory.

    Returns:
        Absolute path to alembic.ini

    Raises:
        FileNotFoundError: If alembic.ini is not found
    """
    ini_path = os.path.join(os.getcwd(), "alembic.ini")
    if not os.path.exists(ini_path):
        raise FileNotFoundError(
            f"alembic.ini not found in {os.getcwd()}. "
            "Run this command from the project directory containing alembic.ini."
        )
    return ini_path


def run_migrate(revision: str = "head"):
    """
    Apply database migrations up to the given revision.

    Args:
        revision: Target revision (default: "head" for latest)
    """
    from alembic.config import Config
    from alembic import command

    alembic_cfg = Config(_find_alembic_ini())
    command.upgrade(alembic_cfg, revision)
    print(f"Migration applied to: {revision}")


def run_makemigrations(message: str):
    """
    Auto-generate a new migration by comparing models to the current database schema.

    Args:
        message: Description for the migration revision
    """
    from alembic.config import Config
    from alembic import command

    alembic_cfg = Config(_find_alembic_ini())
    command.revision(alembic_cfg, message=message, autogenerate=True)
    print(f"Migration created: {message}")


def run_db_status():
    """Show the current migration revision applied to the database."""
    from alembic.config import Config
    from alembic import command

    alembic_cfg = Config(_find_alembic_ini())
    command.current(alembic_cfg, verbose=True)


def run_db_stamp(revision: str = "head"):
    """
    Stamp the database with a revision without running migrations.

    Useful for marking an existing database as up-to-date.

    Args:
        revision: Revision to stamp (default: "head")
    """
    from alembic.config import Config
    from alembic import command

    alembic_cfg = Config(_find_alembic_ini())
    command.stamp(alembic_cfg, revision)
    print(f"Database stamped with: {revision}")
