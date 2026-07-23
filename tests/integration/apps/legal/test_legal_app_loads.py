"""
App-load smoke test: the legal app loads all component types, the GraphQL schema builds
with the legal fields, and the public REST router mounts.
"""
import pytest

from lys.core.configs import LysAppSettings
from lys.core.consts.component_types import AppComponentTypeEnum
from lys.core.managers.app import AppManager


@pytest.fixture(scope="module")
def loaded_manager():
    settings = LysAppSettings()
    settings.database.configure(type="sqlite", database=":memory:", echo=False)
    settings.apps = ["lys.apps.base", "lys.apps.legal"]
    manager = AppManager(settings=settings)
    manager.configure_component_types([
        AppComponentTypeEnum.ENTITIES,
        AppComponentTypeEnum.SERVICES,
        AppComponentTypeEnum.NODES,
        AppComponentTypeEnum.WEBSERVICES,
    ])
    manager.load_all_components()
    return manager


def test_entities_and_services_registered(loaded_manager):
    for name in ("legal_document_type", "legal_document_version", "legal_document_acceptance"):
        assert loaded_manager.get_entity(name) is not None
        assert loaded_manager.get_service(name) is not None


def test_graphql_schema_builds_with_legal_fields(loaded_manager):
    schema = loaded_manager._load_schema()
    assert schema is not None
    sdl = str(schema)
    assert "currentLegalDocument" in sdl
    assert "outstandingLegalAcceptances" in sdl
    assert "acceptLegalDocument" in sdl


def test_public_rest_router_mounted(loaded_manager):
    prefixes = [router.prefix for router in loaded_manager.registry.routers]
    assert "/legal" in prefixes
