"""
Fixtures for the client_request module.

Seeds the four lifecycle statuses. `ClientRequestStatus` is a `ParametricEntity`, so this
fixture loads in every environment including production.

No request *type* is seeded here on purpose: lys owns the record, not the catalogue. An
application declares the types it knows how to act on, in its own fixtures.
"""

from lys.apps.organization.modules.client_request.consts import (
    CLIENT_REQUEST_STATUS_CANCELLED,
    CLIENT_REQUEST_STATUS_ERROR,
    CLIENT_REQUEST_STATUS_PENDING,
    CLIENT_REQUEST_STATUS_PROCESSED,
)
from lys.apps.organization.modules.client_request.services import (
    ClientRequestStatusService,
)
from lys.core.fixtures import EntityFixtures
from lys.core.models.fixtures import ParametricEntityFixturesModel
from lys.core.registries import register_fixture


@register_fixture()
class ClientRequestStatusFixtures(EntityFixtures[ClientRequestStatusService]):
    """The four states a request can be in.

    PENDING and ERROR are open: someone still has to act. PROCESSED and CANCELLED are
    settled. Nothing here says *why* a request is in its state — that is `reason_code`,
    which each application fills with its own vocabulary.
    """

    model = ParametricEntityFixturesModel

    data_list = [
        {
            "id": CLIENT_REQUEST_STATUS_PENDING,
            "attributes": {
                "enabled": True,
                "description": "Waiting to be handled.",
            },
        },
        {
            "id": CLIENT_REQUEST_STATUS_PROCESSED,
            "attributes": {
                "enabled": True,
                "description": "Handled; nothing further is expected.",
            },
        },
        {
            "id": CLIENT_REQUEST_STATUS_CANCELLED,
            "attributes": {
                "enabled": True,
                "description": "Dropped without being handled; see the reason code.",
            },
        },
        {
            "id": CLIENT_REQUEST_STATUS_ERROR,
            "attributes": {
                "enabled": True,
                "description": "Handling failed; the request is stuck, not settled.",
            },
        },
    ]
