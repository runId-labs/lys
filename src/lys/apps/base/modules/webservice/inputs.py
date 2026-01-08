"""
Input types for webservice operations.
"""
from typing import Optional

import strawberry
from strawberry.scalars import JSON

from lys.core.models.webservices import WebserviceFixturesModel


@strawberry.experimental.pydantic.input(model=WebserviceFixturesModel.AttributesModel)
class WebserviceAttributesInput:
    """Input for webservice attributes configuration."""
    public_type: strawberry.auto
    is_licenced: strawberry.auto
    enabled: strawberry.auto
    access_levels: strawberry.auto
    operation_type: strawberry.auto
    ai_tool: Optional[JSON] = None


@strawberry.experimental.pydantic.input(model=WebserviceFixturesModel)
class WebserviceFixturesInput:
    """Input for webservice fixtures configuration."""
    id: strawberry.auto
    attributes: strawberry.auto