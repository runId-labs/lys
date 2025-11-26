# many to many
from sqlalchemy import Table, Column, ForeignKey, DateTime, func
from sqlalchemy.orm import declared_attr, relationship

from lys.apps.user_auth.modules.user.entities import User as BasUser
from lys.core.managers.database import Base
from lys.core.registries import register_entity

user_role = Table(
    "user_role",
    Base.metadata,
    Column("user_id", ForeignKey("user.id", ondelete='CASCADE')),
    Column("role_id", ForeignKey("role.id", ondelete='CASCADE')),
    Column("created_at", DateTime(timezone=True), server_default=func.now())
)


@register_entity()
class User(BasUser):
    """
    User entity
    """

    @declared_attr
    def roles(self):
        return relationship(
            "role",
            secondary=user_role,
            lazy='selectin',
            backref="users"
        )
