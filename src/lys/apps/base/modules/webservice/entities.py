from sqlalchemy import Table, Column, ForeignKey, DateTime, func
from sqlalchemy.orm import declared_attr, relationship, Mapped, mapped_column

from lys.core.abstracts.webservices import AbstractWebservice
from lys.core.consts.tablenames import WEBSERVICE_TABLENAME, ACCESS_LEVEL_TABLENAME
from lys.core.managers.database import Base
from lys.core.registers import register_entity

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