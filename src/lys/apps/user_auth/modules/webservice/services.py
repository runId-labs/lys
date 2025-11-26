from typing import Any, Optional

from sqlalchemy import Select, BinaryExpression, select

from lys.apps.base.modules.access_level.entities import AccessLevel
from lys.apps.base.modules.webservice.services import WebserviceService
from lys.apps.user_auth.modules.webservice.entities import WebservicePublicType
from lys.core.consts.webservices import CONNECTED_ACCESS_LEVEL, OWNER_ACCESS_LEVEL
from lys.core.registries import register_service
from lys.core.services import EntityService


@register_service()
class WebservicePublicTypeService(EntityService[WebservicePublicType]):
    pass

@register_service()
class AuthWebserviceService(WebserviceService):
    @classmethod
    async def _accessible_webservices_or_where(cls, stmt: Select, user: dict[str, Any] | None):
        where: Optional[BinaryExpression] = None

        if user is None or user.get("is_super_user", False) is False:
            # return public webservices ...
            where = cls.entity_class.public_type_id.is_not(None)

            if user is not None:
                access_level_entity: type[AccessLevel] = cls.app_manager.get_entity("access_level")
                # connected owner access level webservices ...
                where |= cls.entity_class.access_levels.any(
                    access_level_entity.id.in_([CONNECTED_ACCESS_LEVEL, OWNER_ACCESS_LEVEL]),
                    enabled=True
                )

        return stmt, where

    @classmethod
    async def accessible_webservices(
            cls,
            user: dict[str, Any] | None
    ) -> Select:
        stmt = select(cls.entity_class).distinct()

        stmt, where = await cls._accessible_webservices_or_where(stmt, user)

        if where is not None:
            stmt = stmt.where(where)

        return stmt.order_by(cls.entity_class.id.asc())