from typing import Optional

from sqlalchemy import Table, Column, ForeignKey, DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import declared_attr, relationship, Mapped, mapped_column

from lys.core.abstracts.webservices import AbstractWebservice
from lys.core.consts.tablenames import WEBSERVICE_TABLENAME, ACCESS_LEVEL_TABLENAME
from lys.core.managers.database import Base
from lys.core.registries import register_entity

# Many-to-many association table for webservice access levels
# This table links webservices to their allowed access levels (CONNECTED, OWNER, etc.)
webservice_access_level = Table(
    "webservice_access_level",
    Base.metadata,
    Column("webservice_id", ForeignKey(WEBSERVICE_TABLENAME + ".id", ondelete='CASCADE')),
    Column("access_level_id", ForeignKey(ACCESS_LEVEL_TABLENAME + ".id", ondelete='CASCADE')),
    Column("created_at", DateTime(timezone=True), server_default=func.now())  # Audit trail
)


@register_entity()
class Webservice(AbstractWebservice):
    is_licenced: Mapped[bool] = mapped_column(
        nullable=False,
        comment="Defined if an active licence is mandatory to call the webservice"
    )
    app_name: Mapped[str] = mapped_column(
        nullable=True,
        comment="Name of the application/microservice that provides this webservice"
    )
    operation_type: Mapped[str] = mapped_column(
        String(20),
        nullable=True,
        comment="GraphQL operation type (query or mutation)"
    )
    ai_tool: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="AI tool definition for LLM function calling"
    )

    @property
    def is_public(self):
        return True

    @declared_attr
    def access_levels(self):
        """
        Many-to-many relationship with access levels.

        This defines which types of authenticated access are allowed
        """
        return relationship(
            ACCESS_LEVEL_TABLENAME,
            secondary=webservice_access_level,
            lazy='selectin'
        )