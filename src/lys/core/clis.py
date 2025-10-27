import uvicorn
from pathlib import Path

from fastapi_cli.discover import get_import_data
from fastapi_cli.exceptions import FastAPICLIException


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
