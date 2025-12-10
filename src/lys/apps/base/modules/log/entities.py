from sqlalchemy import Text, String, Integer, JSON
from sqlalchemy.orm import mapped_column, Mapped

from lys.core.consts.tablenames import LOG_TABLENAME
from lys.core.entities import Entity
from lys.core.registries import register_entity


@register_entity()
class Log(Entity):
    __tablename__ = LOG_TABLENAME
    message = mapped_column(Text, nullable=False)
    file_name: Mapped[str] = mapped_column(String, nullable=False)
    line: Mapped[int] = mapped_column(Integer, nullable=False)
    traceback = mapped_column(Text, nullable=False)
    context = mapped_column(JSON, nullable=True)

    def accessing_users(self) -> list[str]:
        return []

    def accessing_organizations(self) -> dict[str, list[str]]:
        return {}