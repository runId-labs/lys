"""
Integration test building the GraphQL schema with the licensing app loaded.

A malformed resolver signature only fails when Strawberry resolves the schema
fields, which happens at application startup. Without this test the whole suite
passes while the application cannot boot.
"""

import pytest

from lys.core.configs import LysAppSettings
from lys.core.consts.component_types import AppComponentTypeEnum
from lys.core.managers.app import AppManager


@pytest.fixture(scope="module")
def licensing_schema():
    """Build the schema the way the application does at startup."""
    settings = LysAppSettings()
    settings.database.configure(type="sqlite", database=":memory:", echo=False)
    settings.apps = [
        "lys.apps.base",
        "lys.apps.user_auth",
        "lys.apps.user_role",
        "lys.apps.organization",
        "lys.apps.licensing",
    ]

    app_manager = AppManager(settings=settings)
    app_manager.configure_component_types([
        AppComponentTypeEnum.ENTITIES,
        AppComponentTypeEnum.SERVICES,
        AppComponentTypeEnum.NODES,
        AppComponentTypeEnum.WEBSERVICES,
    ])
    app_manager.load_all_components()

    return app_manager._load_schema()


class TestLicensingGraphQLSchema:
    """The licensing webservices must produce a resolvable schema."""

    def test_schema_resolves(self, licensing_schema):
        """
        Resolving the fields is what raises on a malformed signature, so the
        schema is rendered rather than merely built.
        """
        assert str(licensing_schema)

    @pytest.mark.parametrize("query", [
        "allLicensePlans",
        "allLicensePlanVersions",
    ])
    def test_listing_query_is_exposed(self, licensing_schema, query):
        assert query in str(licensing_schema)

    @pytest.mark.parametrize("mutation", [
        "createLicensePlanVersion",
        "setLicensePlanVersionRule",
        "setLicensePlanVersionEnabled",
    ])
    def test_catalogue_mutation_is_exposed(self, licensing_schema, mutation):
        assert mutation in str(licensing_schema)

    @pytest.mark.parametrize("mutation", [
        "subscribeClientManually",
        "setSubscriptionBillingMode",
    ])
    def test_manual_billing_mutation_is_exposed(self, licensing_schema, mutation):
        assert mutation in str(licensing_schema)

    def test_plan_version_entity_is_not_exposed_as_an_argument(self, licensing_schema):
        """
        lys_edition injects the edited entity, it is never an input. Leaking it
        into the signature is what makes Strawberry fail on an unexpected type.
        """
        assert "LicensePlanVersionEntity" not in str(licensing_schema)
