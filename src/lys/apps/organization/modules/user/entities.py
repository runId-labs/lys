from typing import Optional

from sqlalchemy import ForeignKey, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship, declared_attr, backref

from lys.apps.organization.abstracts import AbstractOrganizationEntity, AbstractUserOrganizationRoleEntity
from lys.apps.user_role.modules.user.entities import User as BaseUser
from lys.core.registries import register_entity


@register_entity()
class User(BaseUser):
    """
    Extended User entity with client organization support.

    Adds client_id to associate a user with a client organization.
    - client_id = None: User is a supervisor (internal team)
    - client_id = <uuid>: User is a client user (belongs to that organization)
    """

    client_id: Mapped[Optional[str]] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey("client.id", ondelete='SET NULL', use_alter=True),
        nullable=True,
        comment="Client organization (null for supervisors)"
    )

    @declared_attr
    def client(cls):
        return relationship(
            "client",
            backref="users",
            foreign_keys=[cls.client_id],
            lazy='selectin'
        )

    @property
    def is_supervisor(self) -> bool:
        """Returns True if user is a supervisor (not associated with any client)."""
        return self.client_id is None

    @property
    def is_client_user(self) -> bool:
        """Returns True if user is associated with a client organization."""
        return self.client_id is not None

    def accessing_organizations(self) -> dict[str, list[str]]:
        """Returns the client organization this user belongs to."""
        if self.client_id:
            return {"client": [self.client_id]}
        return {}

    @classmethod
    def organization_accessing_filters(cls, stmt, organization_id_dict):
        """
        Filter users by their client_id to only show users from the same organization.

        A user can see other users if:
        - The user's client_id is in the list of client IDs the connected user has access to

        Args:
            stmt: SQLAlchemy SELECT statement
            organization_id_dict: Dict with "client" key containing list of accessible client IDs

        Returns:
            Tuple of (stmt, conditions) where conditions filter by client_id
        """
        client_ids = organization_id_dict.get("client", [])
        if client_ids:
            return stmt, [cls.client_id.in_(client_ids)]
        return stmt, []


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
    def user(self):
        return relationship(
            "user",
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
        recipient resolution. Since client_id is accessed via user.client_id,
        this property allows consistent attribute access pattern across all
        organization levels (client_id, company_id, establishment_id).

        Returns:
            str: The client ID from the associated user
        """
        return self.user.client_id

    @property
    def organization(self) -> AbstractOrganizationEntity:
        return self.user.client

    @classmethod
    def organization_accessing_filters(cls, stmt, organization_id_dict):
        return stmt, [cls.user_id.in_(organization_id_dict.get("client", []))]

