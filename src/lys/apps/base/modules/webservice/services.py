from typing import Any

from sqlalchemy import Select, select

from lys.apps.base.modules.webservice.entities import Webservice
from lys.core.registries import register_service
from lys.core.services import EntityService


@register_service()
class WebserviceService(EntityService[Webservice]):
    @classmethod
    async def accessible_webservices(
            cls,
            user: dict[str, Any] | None
    ) -> Select[tuple[Webservice]]:
        stmt = select(cls.entity_class).distinct()
        return stmt.order_by(cls.entity_class.id.asc())
