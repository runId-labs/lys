from typing import Any

from sqlalchemy import ForeignKey
from sqlalchemy.orm import declared_attr, Mapped, mapped_column, relationship

from lys.apps.organization.abstracts import AbstractOrganizationEntity
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
