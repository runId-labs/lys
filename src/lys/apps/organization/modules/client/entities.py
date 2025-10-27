from typing import Any

from sqlalchemy import ForeignKey
from sqlalchemy.orm import declared_attr, Mapped, mapped_column, relationship

from lys.apps.organization.abstracts import AbstractOrganizationEntity, AbstractUserOrganizationRoleEntity
from lys.core.registers import register_entity


@register_entity()
class Client(AbstractOrganizationEntity):
    __tablename__ = "client"

    owner_id: Mapped[str] = mapped_column(ForeignKey("user.id", ondelete='CASCADE'), nullable=False)

    @declared_attr
    def owner(self):
        return relationship(
            "user",
            backref="clients",
            lazy='selectin'
        )

    @property
    def parent_organization(self) -> Any:
        return None

    @classmethod
    def organization_accessing_filters(cls, stmt, organization_id_dict):
        return stmt, [cls.id.in_(organization_id_dict.get(cls.__tablename__, []))]


@register_entity()
class ClientUserRole(AbstractUserOrganizationRoleEntity):
    __tablename__ = "client_user_role"

    @declared_attr
    def client_user(self):
        return relationship(
            "client_user",
            backref="client_user_roles",
            lazy='selectin'
        )

    @declared_attr
    def role(self):
        return relationship(
            "role",
            backref="client_user_roles",
            lazy='selectin'
        )

    @property
    def organization(self) -> AbstractOrganizationEntity:
        return self.client_user.client

    @classmethod
    def organization_accessing_filters(cls, stmt, organization_id_dict):
        tablename = cls.client_user.client.__tablename__
        return stmt, [cls.client_user.client_id.in_(organization_id_dict.get(tablename, []))]
