import abc
from typing import Self, Any

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from lys.core.entities import Entity


class AbstractOrganizationEntity(Entity):
    __abstract__ = True

    name: Mapped[str] = mapped_column(nullable=False)

    @property
    @abc.abstractmethod
    def parent_organization(self) -> Self | None:
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def owner(self) -> Any:
        raise NotImplementedError


    def accessing_users(self) -> list[str]:
        return []

    def accessing_organizations(self) -> dict[str, list[str]]:
        new_accessing_organizations = {
            self.__tablename__: [self.id]
        }

        # parent organization has access to the child organization
        if isinstance(self.parent_organization, AbstractOrganizationEntity):
            new_accessing_organizations = {
                **self.parent_organization.accessing_organizations(),
                **new_accessing_organizations
            }

        return new_accessing_organizations


class AbstractUserOrganizationRoleEntity(Entity):
    """
    Abstract base class for user-organization role assignments.

    Supports hierarchical organization structures where roles can be assigned
    at different levels (e.g., client, company, establishment).

    The `level` property indicates which organization level this role assignment applies to:
    - "client": Role applies to the entire client (base level, no additional scoping columns)
    - "company": Role applies to a specific company (requires company_id column in subclass)
    - "establishment": Role applies to a specific establishment (requires establishment_id column)

    Subclasses can extend the base table by adding optional organization columns:
    - Base: (user_id, role_id) with level="client"
    - Extended: (user_id, role_id, company_id[opt], establishment_id[opt])
      where level is determined by which columns are populated

    Permission inheritance:
    - A role at "client" level grants access to all companies/establishments under that client
    - A role at "company" level grants access to all establishments under that company
    - A role at "establishment" level grants access only to that specific establishment
    """
    __abstract__ = True

    user_id: Mapped[str] = mapped_column(ForeignKey("user.id", ondelete='CASCADE'), nullable=False)
    role_id: Mapped[str] = mapped_column(ForeignKey("role.id", ondelete='CASCADE'), nullable=False)

    @property
    @abc.abstractmethod
    def level(self) -> str:
        """
        Return the organization level this role assignment applies to.

        Returns:
            str: Organization level identifier (e.g., "client", "company", "establishment")
        """
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def organization(self) -> AbstractOrganizationEntity:
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def user(self) -> Any:
        raise NotImplementedError

    def accessing_users(self) -> list[str]:
        return []

    def accessing_organizations(self) -> dict[str, list[str]]:
        table_name = self.organization.__tablename__
        new_accessing_organizations = {
            table_name: [self.organization.id]
        }

        # parent organization has access to the child organization
        if isinstance(self.organization.parent_organization, AbstractOrganizationEntity):
            new_accessing_organizations = {
                **self.organization.parent_organization.accessing_organizations(),
                **new_accessing_organizations
            }

        return new_accessing_organizations
