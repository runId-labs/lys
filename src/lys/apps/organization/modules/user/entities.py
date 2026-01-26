from typing import Any

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship, declared_attr, backref

from lys.apps.organization.abstracts import AbstractOrganizationEntity, AbstractUserOrganizationRoleEntity
from lys.core.entities import Entity
from lys.core.registries import register_entity


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

    def accessing_users(self) -> list[str]:
        return [self.user_id] if self.user_id else []

    def accessing_organizations(self) -> dict[str, list[str]]:
        if self.client:
            return self.client.accessing_organizations()
        return {}

    @classmethod
    def user_accessing_filters(cls, stmt, user_id):
        return stmt, [cls.user_id == user_id]

    @classmethod
    def organization_accessing_filters(cls, stmt, organization_id_dict):
        return stmt, [cls.client_id.in_(organization_id_dict.get("client", []))]


@register_entity()
class ClientUserRole(AbstractUserOrganizationRoleEntity):
    """
    Role assignment for a user at the client organization level.

    This is the base implementation of user-organization role assignments.
    A role assigned here applies to the entire client organization.

    For hierarchical organization support (company, establishment levels),
    subclass this entity and add optional columns:
    - company_id: Mapped[str | None] - to scope role to a specific company
    - establishment_id: Mapped[str | None] - to scope role to a specific establishment

    The `level` property determines the effective scope:
    - If company_id and establishment_id are both None: level="client" (full client access)
    - If company_id is set but establishment_id is None: level="company"
    - If both company_id and establishment_id are set: level="establishment"

    Permission inheritance flows downward:
    - "client" level grants access to all companies and establishments
    - "company" level grants access to all establishments under that company
    - "establishment" level grants access only to that establishment
    """
    __tablename__ = "client_user_role"

    @declared_attr
    def client_user(self):
        return relationship(
            "client_user",
            backref=backref("client_user_roles", lazy='selectin'),
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
    def level(self) -> str:
        """
        Return the organization level for this role assignment.

        Base implementation always returns "client" since there are no
        company_id or establishment_id columns. Subclasses with these
        columns should override to check which level is populated.

        Returns:
            str: "client" - role applies to entire client organization
        """
        return "client"

    @property
    def client_id(self) -> str:
        """
        Return the client_id for this role assignment.

        This property provides unified access to client_id for notification
        recipient resolution. Since client_id is accessed via client_user.client_id,
        this property allows consistent attribute access pattern across all
        organization levels (client_id, company_id, establishment_id).

        Returns:
            str: The client ID from the associated client_user
        """
        return self.client_user.client_id

    @property
    def organization(self) -> AbstractOrganizationEntity:
        return self.client_user.client

    @classmethod
    def organization_accessing_filters(cls, stmt, organization_id_dict):
        return stmt, [cls.client_user_id.in_(organization_id_dict.get("client", []))]

