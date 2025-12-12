"""
Interface for permission management system.

This module defines the abstract interface for implementing permission checks
and access control constraints in the lys framework. It provides a pluggable
architecture for different permission strategies.
"""
from abc import abstractmethod, ABC
from typing import Type, Tuple, Optional, Dict, TYPE_CHECKING

from sqlalchemy import Select, BinaryExpression

from lys.core.interfaces.entities import EntityInterface

if TYPE_CHECKING:
    from lys.core.contexts import Context


class PermissionInterface(ABC):
    """
    Abstract interface for permission management.

    This interface defines the contract for implementing permission checks
    in the lys framework. Implementations can provide custom business logic
    for access control at both the webservice and entity levels.
    """

    @classmethod
    @abstractmethod
    async def check_webservice_permission(cls, webservice_id: str,
                                          context: "Context") -> tuple[bool | Dict | None, str | None]:
        """
        Check if a user has permission to access a specific webservice.

        This method implements the business logic for webservice access control,
        considering factors like user authentication, webservice configuration,
        and access levels.

        Args:
            webservice_id: The webservice identifier to check access for
            context: Request context containing user information, app_manager, and access type

        Returns:
            Tuple containing:
            - access_type: bool (allowed/denied), Dict (conditional access with metadata), or None
            - error_code: String error code if access denied, None if allowed

        Examples:
            - (True, None): Full access granted
            - (False, "ACCESS_DENIED"): Access denied with error code
            - ({"owner": True}, None): Conditional access (user can only see their own data)
        """
        raise NotImplementedError

    @classmethod
    @abstractmethod
    async def add_statement_access_constraints(cls, stmt: Select, or_where: BinaryExpression, context,
                                               entity_type: Optional[Type[EntityInterface]]
                                               ) -> Tuple[Select, BinaryExpression]:
        """
        Add access control constraints to SQLAlchemy statements.

        This method modifies SQL queries to enforce row-level security based on
        the user's access permissions. It integrates with the entity's
        user_accessing_filters method to apply appropriate WHERE clauses.

        Args:
            stmt: SQLAlchemy Select statement to modify
            or_where: Existing OR conditions to combine with
            context: Request context with user info and access type
            entity_type: The entity class being queried (for accessing filters)

        Returns:
            Tuple containing:
            - stmt: Modified Select statement with access constraints
            - or_where: Updated OR conditions with access filters

        Note:
            This method works in conjunction with EntityInterface.user_accessing_filters()
            to provide fine-grained access control at the database level.
        """
        raise NotImplementedError
