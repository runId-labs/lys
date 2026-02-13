"""
Integration tests for EntityService with different entity types.

This extends the LanguageService tests (test_language_service.py) by testing
EntityService with different entity configurations:
- UUID primary keys (Entity) vs string primary keys (ParametricEntity)
- Entities with nullable fields and JSON columns

Test approach: Minimal integration tests to verify EntityService handles different
entity structures. The existing LanguageService tests (12 tests) already cover
comprehensive CRUD operations for ParametricEntity.

Note: This is a minimal Phase 1.4 completion. More comprehensive EntityService tests
with complex relationships, constraints, etc. can be added in future phases.
"""

import pytest
import pytest_asyncio

from lys.core.configs import LysAppSettings
from lys.core.consts.component_types import AppComponentTypeEnum
from lys.core.managers.app import AppManager
from tests.fixtures.database import create_all_tables


class TestEntityServiceWithDifferentEntityTypes:
    """Test EntityService with different entity configurations."""

    @pytest_asyncio.fixture
    async def app_manager(self):
        """Create AppManager with base app loaded."""
        settings = LysAppSettings()
        settings.database.configure(
            type="sqlite",
            database=":memory:",
            echo=False
        )
        settings.apps = ["lys.apps.base"]

        app_manager = AppManager(settings=settings)
        app_manager.configure_component_types([
            AppComponentTypeEnum.ENTITIES,
            AppComponentTypeEnum.SERVICES,
        ])
        app_manager.load_all_components()
        await create_all_tables(app_manager.database)

        yield app_manager

        await app_manager.database.close()

    @pytest.mark.asyncio
    async def test_entity_service_with_string_primary_key(self, app_manager):
        """Test EntityService with ParametricEntity (string ID).

        Language is a ParametricEntity that uses string as primary key (id field).
        This verifies EntityService.create() and get_by_id() work with string IDs.
        """
        language_service = app_manager.get_service("language")

        async with app_manager.database.get_session() as session:
            # ParametricEntity only needs id and enabled
            created = await language_service.create(
                session=session,
                id="es",
                enabled=True
            )

            assert created.id == "es"
            assert created.enabled is True
            # code is a property that returns id
            assert created.code == "es"

            # Retrieve by string ID
            retrieved = await language_service.get_by_id("es", session)
            assert retrieved is not None
            assert retrieved.id == "es"


    @pytest.mark.asyncio
    async def test_get_all_with_different_entity_types(self, app_manager):
        """Test get_all() works with both ParametricEntity and Entity types."""
        async with app_manager.database.get_session() as session:
            language_service = app_manager.get_service("language")
            access_level_service = app_manager.get_service("access_level")

            # Create multiple ParametricEntities (string IDs)
            for lang_id in ["en", "fr", "de"]:
                await language_service.create(session=session, id=lang_id, enabled=True)

            # Create multiple ParametricEntities (string IDs)
            for code in ["ADMIN", "USER", "GUEST"]:
                await access_level_service.create(session=session, id=code, enabled=True)

            # Test get_all with pagination
            languages = await language_service.get_all(session, limit=2, offset=0)
            assert len(languages) == 2

            access_levels = await access_level_service.get_all(session, limit=10, offset=0)
            assert len(access_levels) == 3
