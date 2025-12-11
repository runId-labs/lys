from typing import Type, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from lys.core.consts.errors import PERMISSION_DENIED_ERROR, NOT_FOUND_ERROR
from lys.core.contexts import Context
from lys.core.errors import LysError
from lys.core.interfaces.entities import EntityInterface
from lys.core.interfaces.services import EntityServiceInterface


async def check_access_to_object(entity_obj: EntityInterface, context: Context) -> bool:

    connected_user_id = context.connected_user.get('sub') if context.connected_user else None
    access_type = context.access_type

    if not entity_obj.check_permission(connected_user_id, access_type):
        raise LysError(
            PERMISSION_DENIED_ERROR,
            "check_permission return False"
        )

    return True


async def get_db_object_and_check_access(
    object_id: str,
    service_class: Type[EntityServiceInterface],
    context: Context,
    session: AsyncSession,
    nullable: bool = False,

) -> Optional[EntityInterface]:

    entity_obj: Optional[EntityInterface] = await service_class.get_by_id(object_id, session)

    if not nullable and entity_obj is None:
        raise LysError(
            NOT_FOUND_ERROR,
            "Entity '%s' with id '%s' is not found" % (service_class.entity_class.__tablename__, object_id)
        )
    if entity_obj:
        await check_access_to_object(entity_obj, context)

    return entity_obj