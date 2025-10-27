from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship, declared_attr

from lys.core.entities import Entity
from lys.core.registers import register_entity


@register_entity()
class ClientUser(Entity):
    __tablename__ = "client_user"

    user_id: Mapped[str] = mapped_column(ForeignKey("user.id", ondelete='CASCADE'), nullable=False)
    client_id: Mapped[str] = mapped_column(ForeignKey("client.id", ondelete='CASCADE'), nullable=False)

    @declared_attr
    def user(self):
        return relationship(
            "user",
            backref="client_users",
            lazy='selectin'
        )

    @declared_attr
    def client(self):
        return relationship(
            "client",
            backref="client_users",
            lazy='selectin'
        )

    def accessing_users(self):
        return [self.user]

    def accessing_organizations(self):
        if self.client:
            return self.client.accessing_organizations()
        return {}

    @classmethod
    def user_accessing_filters(cls, stmt, user_id):
        return stmt, [cls.user_id == user_id]

    @classmethod
    def organization_accessing_filters(cls, stmt, organization_id_dict):
        return stmt, [cls.client_id.in_(organization_id_dict.get(cls.client.__tablename__, []))]

