"""
Alembic migration helper for lys-based projects.

Provides configure_alembic_env() to be called from a project's migrations/env.py.
Handles loading entities into Base.metadata and running migrations.
"""

import importlib
import logging

from alembic import context

from lys.core.consts.component_types import AppComponentTypeEnum
from lys.core.managers.app import LysAppManager
from lys.core.managers.database import Base

logger = logging.getLogger("alembic.env")


def configure_alembic_env(settings_module: str = "settings"):
    """
    Configure Alembic env.py for a lys-based project.

    This function:
    1. Imports the settings module and calls configure_core() + configure_database()
    2. Creates a LysAppManager and loads ENTITIES to populate Base.metadata
    3. Builds a sync database URL via DatabaseManager
    4. Runs Alembic migrations (online or offline mode)

    Args:
        settings_module: Python module path for the project settings (default: "settings")
    """
    # 1. Load and configure settings
    try:
        settings = importlib.import_module(settings_module)
    except ImportError as e:
        raise RuntimeError(f"Failed to import settings module '{settings_module}': {e}")

    if hasattr(settings, "configure_core"):
        settings.configure_core()
    else:
        raise RuntimeError(f"Function 'configure_core' not found in '{settings_module}'")

    if hasattr(settings, "configure_database"):
        settings.configure_database()
    else:
        raise RuntimeError(f"Function 'configure_database' not found in '{settings_module}'")

    # 2. Load entities to populate Base.metadata
    app_manager = LysAppManager()
    app_manager.configure_component_types([AppComponentTypeEnum.ENTITIES])
    app_manager.load_all_components()

    target_metadata = Base.metadata

    # 3. Build sync database URL
    from lys.core.managers.database import DatabaseManager
    db_manager = DatabaseManager(app_manager.settings.database)
    database_url = db_manager._build_url(async_mode=False)

    # 4. Run migrations
    if context.is_offline_mode():
        _run_migrations_offline(database_url, target_metadata)
    else:
        _run_migrations_online(database_url, target_metadata)


def _run_migrations_offline(url, target_metadata):
    """Run migrations in offline mode (SQL script generation)."""
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def _run_migrations_online(url, target_metadata):
    """Run migrations in online mode (direct database connection)."""
    from sqlalchemy import engine_from_config, pool

    alembic_config = context.config
    alembic_config.set_main_option("sqlalchemy.url", url)

    connectable = engine_from_config(
        alembic_config.get_section(alembic_config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()
