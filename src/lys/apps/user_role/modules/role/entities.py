from typing import List

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from lys.core.entities import Entity, ParametricEntity
from lys.core.registries import register_entity


@register_entity()
class RoleWebservice(Entity):
    """
    Junction entity for role-webservice many-to-many relationship.

    Uses string webservice_id (not FK) to allow references to external
    webservices that may not exist in the local database yet.
    """
    __tablename__ = "role_webservice"

    role_id: Mapped[str] = mapped_column(
        ForeignKey("role.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    webservice_id: Mapped[str] = mapped_column(
        String,
        nullable=False,
        comment="Webservice ID (string, not FK - may reference external webservices)"
    )

    @declared_attr
    def role(cls):
        """Back reference to the parent Role."""
        return relationship("role", back_populates="role_webservices")


@register_entity()
class Role(ParametricEntity):
    __tablename__ = "role"

    app_name: Mapped[str] = mapped_column(
        nullable=True,
        comment="Name of the application/microservice that provides this role"
    )

    @declared_attr
    def role_webservices(cls) -> Mapped[List["RoleWebservice"]]:
        """Relationship to RoleWebservice junction entities."""
        return relationship(
            "role_webservice",
            back_populates="role",
            cascade="all, delete-orphan",
            lazy="selectin"
        )

    def get_webservice_ids(self) -> List[str]:
        """
        Get webservice IDs associated with this role.

        Returns:
            List of webservice ID strings
        """
        return [rw.webservice_id for rw in self.role_webservices]
