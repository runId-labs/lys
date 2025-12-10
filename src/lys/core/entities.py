from datetime import datetime
from typing import Tuple, List, Dict, Union, Any
from uuid import uuid4

from sqlalchemy import Uuid, DateTime, func, Select, BinaryExpression
from sqlalchemy.orm import Mapped, mapped_column

from lys.core.consts.permissions import ROLE_ACCESS_KEY, OWNER_ACCESS_KEY, ORGANIZATION_ROLE_ACCESS_KEY
from lys.core.interfaces.entities import EntityInterface


class Entity(EntityInterface):

    __tablename__: str
    __abstract__: bool = True

    def __init_subclass__(cls, **kwargs):
        """
        Ensure all subclasses are marked as abstract by default.

        This prevents accidental instantiation of incomplete entities.
        Concrete entities must explicitly set __abstract__ = False.
        """
        if not hasattr(cls, '__abstract__') or cls.__abstract__ is None:
            cls.__abstract__ = True
        super().__init_subclass__(**kwargs)

    # Primary key: Auto-generated UUID for technical identification
    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))

    # Audit timestamps: Automatically managed by database
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True, onupdate=func.now())

    @classmethod
    def get_tablename(cls):
        return cls.__tablename__

    @classmethod
    def user_accessing_filters(cls, stmt: Select, user_id: str) \
            -> Tuple[Select, List[BinaryExpression]]:
        """
        filters which define list of users who can access to the entity in a query
        :param stmt:
        :param user_id: user id who wants access to the entity
        :return:
        """
        return stmt, []

    @classmethod
    def organization_accessing_filters(cls, stmt: Select, accessing_organization_id_dict: Dict) \
            -> Tuple[Select, List[BinaryExpression]]:
        """
        filters which define list of organization which can access to the entity in a query
        :param stmt:
        :param accessing_organization_id_dict: dictionary of organization ids which want access to the entity
        :return:
        """
        return stmt, []

    def check_permission(self, user_id: str | None, access_type: Union[dict[str, Any], bool]):
        if isinstance(access_type, bool):
            return access_type

        has_right = False

        # if it is access by role the right is granted
        # because normally webservice checked the permission before
        if access_type.get(ROLE_ACCESS_KEY, False):
            has_right = True
        # check if the user is an owner
        elif access_type.get(OWNER_ACCESS_KEY, False):
            has_right = user_id in self.accessing_users()

        # check if user has access by an organization role
        elif access_type.get(ORGANIZATION_ROLE_ACCESS_KEY, False):
            for accessing_organization_key, accessing_organization_id_list in self.accessing_organizations().items():
                user_organization_id_list = access_type[ORGANIZATION_ROLE_ACCESS_KEY].get(accessing_organization_key, [])
                for user_organization_id in user_organization_id_list:
                    if user_organization_id in accessing_organization_id_list:
                        has_right = True
                        break
                if has_right:
                    break

        return has_right


class ParametricEntity(Entity):
    """
    Base entity for configuration/reference data with business-meaningful IDs.

    This class is used for entities that represent system configuration, reference
    data, or lookup values. Unlike BaseEntity which uses technical UUIDs, these
    entities use business-meaningful string IDs that are human-readable.

    Key Features:
    - String primary key with business meaning (e.g., "ENABLED", "DISABLED")
    - Inherits audit timestamps from BaseEntity
    - Built-in enabled/disabled functionality for activation control
    - Code property for backend logic (avoids GraphQL encoding)

    When to use ParametricEntity:
    - User statuses (ACTIVE, SUSPENDED, DELETED)
    - Order types (STANDARD, EXPRESS, PRIORITY)
    - Payment methods (CREDIT_CARD, PAYPAL, BANK_TRANSFER)
    - Categories, types, enums stored in database

    Example usage:
        class UserStatus(ParametricEntity):
            __tablename__ = "user_statuses"
            __abstract__ = False  # Make it concrete

            name: Mapped[str] = mapped_column()
            description: Mapped[str] = mapped_column(nullable=True)

        # Create instances:
        active_status = UserStatus(id="ACTIVE", name="Active User")
        suspended_status = UserStatus(id="SUSPENDED", name="Suspended", enabled=False)

        # Usage in business logic:
        if user.status.code == "ACTIVE" and user.status.enabled:
            # User can perform actions
    """
    # Override BaseEntity's UUID id with business-meaningful string
    id: Mapped[str] = mapped_column(primary_key=True)

    # Control flag for enabling/disabling parametric values
    enabled: Mapped[bool] = mapped_column(default=True)

    # AI-friendly description for system prompts and tool context
    description: Mapped[str] = mapped_column(nullable=True)

    @property
    def code(self):
        """
        Business identifier in its original form.

        This property provides access to the raw business ID without any encoding
        or transformation that might be applied by GraphQL or other layers.

        Use this property in business logic where you need the actual string value:
        - Conditional logic: if status.code == "ACTIVE"
        - Logging and debugging: logger.info(f"Status: {status.code}")
        - Database queries: filter(UserStatus.id == status.code)

        Returns:
            str: The raw business identifier (same as id)
        """
        return self.id

    def accessing_users(self) -> List[str]:
        """Returns a list of user IDs who can access this entity."""
        return []

    def accessing_organizations(self) -> Dict[str, List[str]]:
        """Returns a dictionary of organization table names to lists of organization IDs who can access this entity."""
        return {}
