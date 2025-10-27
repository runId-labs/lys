from sqlalchemy import ForeignKey, Table, Column, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship, declared_attr

from lys.apps.base.modules.webservice.entities import Webservice as BaseWebservice
from lys.core.entities import ParametricEntity
from lys.core.registers import register_entity


@register_entity()
class WebservicePublicType(ParametricEntity):
    """
    Configuration entity for webservice public access types.

    This entity defines the different ways a webservice can be accessed
    by public (unauthenticated) users. Examples include:
    - NO_LIMITATION: Accessible to anyone
    - DISCONNECTED: Only accessible to non-authenticated users
    """
    __tablename__ = "webservice_public_type"


@register_entity()
class AuthWebservice(BaseWebservice):
    """
    Webservice entity with integrated authentication and authorization.

    This entity represents a webservice in the system with comprehensive
    access control features including licensing, public access configuration,
    and granular permission levels.

    Attributes:....
        public_type_id: Type of public access allowed (if any)
        public_type: Relationship to WebservicePublicType configuration
        access_levels: Many-to-many relationship with AccessLevel entities

    Business Logic:
        - Public webservices can be accessed based on their public_type
        - Private webservices require authentication and proper access levels
        - Licensed webservices require additional license validation
    """

    public_type_id: Mapped[str] = mapped_column(
        ForeignKey("webservice_public_type.id", ondelete='SET NULL'),
        nullable=True,
        comment="Type of public access allowed (None = private webservice)"
    )

    @declared_attr
    def public_type(self):
        """Relationship to public type configuration with eager loading."""
        return relationship("webservice_public_type", lazy="selectin")

    @property
    def is_public(self):
        """
        Determine if webservice allows public access.

        Returns:
            bool: True if webservice has a public type configured, False otherwise
        """
        return self.public_type_id is not None
