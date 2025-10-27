from sqlalchemy import Select, select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from lys.core.entities import Entity


def check_is_needing_session(method):
    is_needing_session = False

    for key, type_ in method.__annotations__.items():
        if key == "session" and (type_ == AsyncSession or type_ == Session):
            is_needing_session = True
            break

    return is_needing_session


async def get_select_total_count(stmt: Select, entity: type[Entity], session:AsyncSession):
    count_stmt = select(func.count(entity.id.distinct())).select_from(*stmt.get_final_froms()).order_by(None)

    if stmt.whereclause is not None:
        count_stmt = count_stmt.where(stmt.whereclause)

    result = await session.execute(count_stmt)
    return result.scalar_one()