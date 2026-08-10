import logging
from typing import Type, Optional

from sqlalchemy.ext.asyncio import AsyncSession, async_object_session

from lys.core.consts.errors import PERMISSION_DENIED_ERROR, NOT_FOUND_ERROR
from lys.core.contexts import Context
from lys.core.errors import LysError
from lys.core.interfaces.entities import EntityInterface
from lys.core.interfaces.services import EntityServiceInterface

logger = logging.getLogger(__name__)


async def check_access_to_object(entity_obj: EntityInterface, context: Context) -> bool:

    connected_user_id = context.connected_user.get('sub') if context.connected_user else None
    access_type = context.access_type

    # check_permission and the accessing_users/accessing_organizations chain it calls may walk
    # unloaded ORM relationships. Under AsyncSession, an implicit lazy load outside of run_sync's
    # greenlet raises MissingGreenlet, so the check runs inside run_sync whenever the entity is
    # still attached to a session, regardless of which relations the access logic touches.
    session = async_object_session(entity_obj)
    if session is not None:
        has_permission = await session.run_sync(
            lambda _: entity_obj.check_permission(connected_user_id, access_type)
        )
    else:
        has_permission = entity_obj.check_permission(connected_user_id, access_type)

    if not has_permission:
        raise LysError(
            PERMISSION_DENIED_ERROR,
            "check_permission return False"
        )

    if getattr(entity_obj, "_sensitive", False):
        logger.info(
            "AUDIT: Access to %s (id=%s) by user=%s via webservice=%s with access_type=%s",
            entity_obj.__class__.__name__, getattr(entity_obj, "id", "?"),
            connected_user_id, getattr(context, "webservice_name", None), access_type
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