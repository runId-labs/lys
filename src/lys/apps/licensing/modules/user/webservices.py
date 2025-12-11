"""
User webservices for licensing app.
"""

import logging
from typing import Annotated, Optional

import strawberry
from sqlalchemy import Select, select, or_, exists
from strawberry import relay

from lys.apps.licensing.modules.subscription.entities import subscription_user
from lys.apps.licensing.modules.user.nodes import ClientUserNode
from lys.apps.organization.consts import ORGANIZATION_ROLE_ACCESS_LEVEL
from lys.apps.organization.modules.user.entities import ClientUser
from lys.apps.user_role.consts import ROLE_ACCESS_LEVEL
from lys.core.contexts import Info
from lys.core.graphql.connection import lys_connection
from lys.core.graphql.edit import lys_edition
from lys.core.graphql.registries import register_query, register_mutation
from lys.core.graphql.types import Query, Mutation

logger = logging.getLogger(__name__)


@strawberry.type
@register_query()
class LicensingUserQuery(Query):
    @lys_connection(
        ClientUserNode,
        access_levels=[ROLE_ACCESS_LEVEL, ORGANIZATION_ROLE_ACCESS_LEVEL],
        is_licenced=False,
        allow_override=True,
        description="Search client users with license filtering. Filter by client_id, role, or license status.",
        options={"generate_tool": True}
    )
    async def all_client_users(
        self,
        info: Info,
        client_id: Annotated[Optional[relay.GlobalID], strawberry.argument(description="Filter by organization/client ID")] = None,
        search: Annotated[Optional[str], strawberry.argument(description="Search by user email, first name, or last name")] = None,
        role_code: Annotated[Optional[str], strawberry.argument(description="Filter by organization role code")] = None,
        is_licensed: Annotated[Optional[bool], strawberry.argument(description="Filter by license status: true=licensed, false=unlicensed")] = None
    ) -> Select:
        """
        Get all client-user relationships with optional filtering including license status.

        This query is accessible to users with ROLE or ORGANIZATION_ROLE access level.
        Returns the many-to-many relationships between clients and users.

        Args:
            info: GraphQL context
            client_id: Optional GlobalID to filter by specific client
            search: Optional search string to filter by user's email, first_name, or last_name
            role_code: Optional role code to filter client users by organization role
            is_licensed: Optional filter for license status:
                - True: users with a license (in subscription_user table)
                - False: users without a license (not in subscription_user table)
                - None: no filtering on license status

        Returns:
            Select: SQLAlchemy select statement for client_user relationships ordered by creation date
        """
        client_user_entity = info.context.app_manager.get_entity("client_user")
        user_entity = info.context.app_manager.get_entity("user")
        email_entity = info.context.app_manager.get_entity("user_email_address")
        private_data_entity = info.context.app_manager.get_entity("user_private_data")

        # Base query
        stmt = select(client_user_entity)

        # Join with user, email, and private_data if search is provided
        if search:
            stmt = (
                stmt
                .join(user_entity, client_user_entity.user)
                .join(email_entity)
                .join(private_data_entity)
            )

            search_pattern = f"%{search.lower()}%"
            stmt = stmt.where(
                or_(
                    email_entity.id.ilike(search_pattern),
                    private_data_entity.first_name.ilike(search_pattern),
                    private_data_entity.last_name.ilike(search_pattern)
                )
            )

        # Apply client filter if provided
        if client_id:
            stmt = stmt.where(client_user_entity.client_id == client_id.node_id)

        # Apply role filter if provided
        if role_code:
            client_user_role_entity = info.context.app_manager.get_entity("client_user_role")
            role_entity = info.context.app_manager.get_entity("role")

            stmt = (
                stmt
                .join(client_user_role_entity, client_user_entity.client_user_roles)
                .join(role_entity, client_user_role_entity.role)
                .where(role_entity.id == role_code)
            )

        # Apply license filter if provided
        if is_licensed is not None:
            licensed_subquery = exists().where(
                subscription_user.c.client_user_id == client_user_entity.id
            )

            if is_licensed:
                stmt = stmt.where(licensed_subquery)
            else:
                stmt = stmt.where(~licensed_subquery)

        stmt = stmt.order_by(client_user_entity.created_at.desc())

        return stmt


@register_mutation()
@strawberry.type
class LicensingUserMutation(Mutation):
    @lys_edition(
        ensure_type=ClientUserNode,
        is_public=False,
        access_levels=[ROLE_ACCESS_LEVEL, ORGANIZATION_ROLE_ACCESS_LEVEL],
        is_licenced=False,
        description="Add a client user to their organization's subscription (grant license). Accessible to license administrators.",
        options={"generate_tool": True}
    )
    async def add_client_user_to_subscription(
        self,
        obj: ClientUser,
        info: Info
    ):
        """
        Add a client user to their organization's subscription.

        This grants the user a license seat, allowing them to access
        webservices that require license verification.

        Args:
            obj: ClientUser entity (fetched and validated by lys_edition)
            info: GraphQL context

        Returns:
            ClientUser: The updated client user
        """
        session = info.context.session
        client_user_service = info.context.app_manager.get_service("client_user")

        await client_user_service.add_to_subscription(obj, session)

        logger.info(
            f"Client user {obj.id} added to subscription "
            f"by {info.context.connected_user['sub']}"
        )

        return obj

    @lys_edition(
        ensure_type=ClientUserNode,
        is_public=False,
        access_levels=[ROLE_ACCESS_LEVEL, ORGANIZATION_ROLE_ACCESS_LEVEL],
        is_licenced=False,
        description="Remove a client user from their organization's subscription (revoke license). Accessible to license administrators.",
        options={"generate_tool": True}
    )
    async def remove_client_user_from_subscription(
        self,
        obj: ClientUser,
        info: Info
    ):
        """
        Remove a client user from their organization's subscription.

        This revokes the user's license seat. They will no longer
        be able to access webservices that require license verification.

        Args:
            obj: ClientUser entity (fetched and validated by lys_edition)
            info: GraphQL context

        Returns:
            ClientUser: The updated client user
        """
        session = info.context.session
        client_user_service = info.context.app_manager.get_service("client_user")

        await client_user_service.remove_from_subscription(obj, session)

        logger.info(
            f"Client user {obj.id} removed from subscription "
            f"by {info.context.connected_user['sub']}"
        )

        return obj