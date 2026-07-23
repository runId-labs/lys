"""
Fixtures for the legal_document module.

Seeds the default, generic document type codes. `LegalDocumentType` is a `ParametricEntity`,
so this fixture loads in all environments including prod (unlike non-parametric fixtures,
which are skipped in prod). Document *versions* are published at startup via the service's
`on_initialize` hook, not through a fixture.
"""

from lys.apps.legal.modules.legal_document.consts import (
    PRIVACY_POLICY,
    SALES_TERMS,
    TERMS_OF_USE,
)
from lys.apps.legal.modules.legal_document.services import LegalDocumentTypeService
from lys.core.fixtures import EntityFixtures
from lys.core.models.fixtures import ParametricEntityFixturesModel
from lys.core.registries import register_fixture


@register_fixture()
class LegalDocumentTypeFixtures(EntityFixtures[LegalDocumentTypeService]):
    """Default legal document type codes. Applications may add their own."""

    model = ParametricEntityFixturesModel

    data_list = [
        {
            "id": TERMS_OF_USE,
            "attributes": {
                "enabled": True,
                "requires_acceptance": True,
                "description": "Terms of use governing access to and use of the service.",
            },
        },
        {
            "id": SALES_TERMS,
            "attributes": {
                "enabled": True,
                "requires_acceptance": True,
                "description": "Sales terms governing paid subscriptions and purchases.",
            },
        },
        {
            "id": PRIVACY_POLICY,
            "attributes": {
                "enabled": True,
                "requires_acceptance": False,
                "description": "Privacy policy describing personal data processing.",
            },
        },
    ]
