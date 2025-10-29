from datetime import datetime
from typing import Optional

import strawberry
from sqlalchemy import select, Select

from lys.apps.base.modules.log.nodes import LogNode
from lys.core.contexts import Info
from lys.core.graphql.connection import lys_connection
from lys.core.graphql.registers import register_query
from lys.core.graphql.types import Query


@register_query("graphql")
@strawberry.type
class LogQuery(Query):
    @lys_connection(
        ensure_type=LogNode,
        is_licenced=False,
        description="Return logs filtered by date range and optional filters."
    )
    async def all_logs(
        self,
        info: Info,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        file_name: Optional[str] = None,
    ) -> Select:
        entity_type = info.context.service_class.entity_class

        stmt = select(entity_type).order_by(entity_type.created_at.desc())

        if start_date is not None:
            stmt = stmt.where(entity_type.created_at >= start_date)

        if end_date is not None:
            stmt = stmt.where(entity_type.created_at <= end_date)

        if file_name is not None:
            stmt = stmt.where(entity_type.file_name.ilike(f"%{file_name}%"))

        return stmt