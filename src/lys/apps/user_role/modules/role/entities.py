from sqlalchemy import ForeignKey, Table, Column, DateTime, func
from sqlalchemy.orm import relationship, declared_attr

from lys.core.entities import ParametricEntity
from lys.core.managers.database import Base
from lys.core.registers import register_entity


# many to many
role_webservice = Table(
    "role_webservice",
    Base.metadata,
    Column("role_id", ForeignKey("role.id", ondelete='CASCADE')),
    Column("webservice_id", ForeignKey("webservice.id", ondelete='CASCADE')),
    Column("created_at", DateTime, server_default=func.now())
)


@register_entity()
class Role(ParametricEntity):
    __tablename__ = "role"

    @declared_attr
    def webservices(self):
        return relationship(
            "webservice",
            backref="roles",
            secondary=role_webservice,
            lazy='selectin'
        )
