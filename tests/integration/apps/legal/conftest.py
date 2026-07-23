"""
Pytest configuration for legal app integration tests.

Provides a session-scoped AppManager with the legal app loaded (plus base for Language),
tables created, and languages + document types seeded.
"""
import pytest_asyncio
from sqlalchemy.pool import StaticPool

from lys.apps.legal.modules.legal_document.consts import (
    PRIVACY_POLICY,
    SALES_TERMS,
    TERMS_OF_USE,
)
from lys.core.configs import LysAppSettings
from lys.core.consts.component_types import AppComponentTypeEnum
from lys.core.managers.app import LysAppManager
from lys.core.utils.manager import AppManagerCallerMixin
from tests.fixtures.database import create_all_tables


@pytest_asyncio.fixture(scope="session")
async def legal_app_manager():
    """Create AppManager with the legal app loaded and reference data seeded."""
    settings = LysAppSettings()
    # StaticPool → a single shared :memory: connection, so a service method that opens its
    # own session (on_initialize) sees the tables created here, not a fresh empty DB.
    settings.database.configure(
        type="sqlite", database=":memory:", echo=False, poolclass=StaticPool,
    )
    settings.apps = [
        "lys.apps.base",
        "lys.apps.legal",
    ]

    # Use the LysAppManager singleton so the mixin's `cls.app_manager` fallback resolves to
    # THIS manager (with tables), matching how service methods open their own session.
    app_manager = LysAppManager(settings=settings)
    app_manager.configure_component_types([
        AppComponentTypeEnum.ENTITIES,
        AppComponentTypeEnum.SERVICES,
    ])
    app_manager.load_all_components()
    await create_all_tables(app_manager.database)

    async with app_manager.database.get_session() as session:
        language_service = app_manager.get_service("language")
        await language_service.create(session=session, id="en", enabled=True)
        await language_service.create(session=session, id="fr", enabled=True)

        # Mirror the lys fixture defaults: TOU/SALES gate access, PRIVACY does not.
        type_service = app_manager.get_service("legal_document_type")
        await type_service.create(session=session, id=TERMS_OF_USE, enabled=True,
                                  requires_acceptance=True)
        await type_service.create(session=session, id=SALES_TERMS, enabled=True,
                                  requires_acceptance=True)
        await type_service.create(session=session, id=PRIVACY_POLICY, enabled=True,
                                  requires_acceptance=False)

    yield app_manager
    AppManagerCallerMixin._app_manager = None
    await app_manager.database.close()
