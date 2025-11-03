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
    )


def export_graphql_schema(
    output_path: Path,
    settings_module: str = "settings",
    split_schemas: bool = False
):
    """
    Export the GraphQL schema to a file.

    This function initializes the app_manager with the necessary components
    (entities, services, nodes, webservices) and exports the GraphQL schema
    to the specified output path.

    This function only calls configure_core() from the settings module, which
    configures apps, middlewares, permissions, and plugins without initializing
    database, Celery, or email services.

    By default, all schemas (graphql, auth, etc.) are merged into a single file
    for client consumption. Use split_schemas=True to export each schema separately.

    Args:
        output_path: Path where the schema file will be written (e.g., ./schema/schema.graphql)
        settings_module: Module path to import settings from (default: "settings")
        split_schemas: If True, export each schema to a separate file. If False (default),
                      merge all schemas into a single file.

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

    # Load schema mapping
    schema_mapping = app_manager._load_schema_mapping()

    if not schema_mapping:
        raise Exception("No GraphQL schema found. Make sure you have registered queries/mutations.")

    # Create output directory if it doesn't exist
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if split_schemas:
        # Export each schema to a separate file
        for schema_name, schema in schema_mapping.items():
            # Generate the schema SDL (Schema Definition Language)
            schema_str = str(schema)

            # Write to file with schema name suffix
            schema_file = output_path.parent / f"{output_path.stem}_{schema_name}{output_path.suffix}"
            with open(schema_file, "w", encoding="utf-8") as f:
                f.write(schema_str)

            print(f"GraphQL schema exported to: {schema_file}")
    else:
        # Merge all schemas into a single file (default behavior for client consumption)
        merged_schema = []
        for schema_name, schema in schema_mapping.items():
            # Generate the schema SDL
            schema_str = str(schema)
            # Add header comment to identify schema sections
            merged_schema.append(f"# Schema: {schema_name}\n")
            merged_schema.append(schema_str)
            merged_schema.append("\n")

        # Write merged schema to single file
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(merged_schema))

        print(f"GraphQL schema (merged) exported to: {output_path}")

    print(f"Schema export completed successfully!")
