"""
Webservice service for licensing app.

Extends OrganizationWebserviceService to add license verification.
Users must have an active subscription (via subscription_user) to access
webservices with ORGANIZATION_ROLE access level.
"""

from typing import Any, List, Optional

from sqlalchemy import Select, BinaryExpression, and_, exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from lys.apps.base.modules.webservice.entities import Webservice
from lys.apps.licensing.modules.subscription.entities import subscription_user
from lys.apps.organization.consts import ORGANIZATION_ROLE_ACCESS_LEVEL
from lys.apps.organization.modules.webservice.services import OrganizationWebserviceService
from lys.apps.user_role.modules.webservice.services import RoleWebserviceService
from lys.core.registries import register_service


@register_service()
class LicensingWebserviceService(OrganizationWebserviceService):
    @classmethod
    async def _accessible_webservices_or_where(
            cls,
            stmt: Select,
            user: dict[str, Any] | None
    ) -> tuple[Select, Optional[BinaryExpression]]:
        """
        Build access filters including license verification.

        Extends RoleWebserviceService (skipping OrganizationWebserviceService) to add
        organization role access WITH license verification.

        Access is granted when ALL conditions are met:
        1. Webservice has ORGANIZATION_ROLE access level enabled
        2. User has a client_user_role that grants access to this webservice
        3. User's client_user has an active license (exists in subscription_user table)

        Args:
            stmt: SQLAlchemy select statement
            user: Connected user dictionary with id, or None for anonymous

        Returns:
            Tuple of (statement, where_clause) with license-verified filters added
        """
        # Call RoleWebserviceService directly (skip OrganizationWebserviceService)
        # to avoid duplicate organization role conditions
        stmt, where = await RoleWebserviceService._accessible_webservices_or_where(stmt, user)

        # Add organization role + license verification if user is connected and not super user
        if user is not None and user.get("is_super_user", False) is False:
            user_id = user.get("sub")
            if user_id:
                # Get required entities
                access_level_entity = cls.app_manager.get_entity("access_level")
                role_entity = cls.app_manager.get_entity("role")
                role_webservice_entity = cls.app_manager.get_entity("role_webservice")
                client_user_role_entity = cls.app_manager.get_entity("client_user_role")
                client_user_entity = cls.app_manager.get_entity("client_user")
                client_entity = cls.app_manager.get_entity("client")
                subscription_entity = cls.app_manager.get_entity("subscription")

                # Base condition: ORGANIZATION_ROLE access level enabled
                org_role_access_level_condition = cls.entity_class.access_levels.any(
                    access_level_entity.id == ORGANIZATION_ROLE_ACCESS_LEVEL,
                    enabled=True
                )

                # Condition: user has org role via client_user_role
                # Path: webservice -> role_webservice -> role -> client_user_roles -> client_user
                user_has_org_role_condition = exists(
                    select(role_webservice_entity.id)
                    .join(role_entity, role_webservice_entity.role_id == role_entity.id)
                    .where(
                        role_webservice_entity.webservice_id == cls.entity_class.id,
                        role_entity.client_user_roles.any(
                            client_user_role_entity.client_user.has(
                                client_user_entity.user_id == user_id
                            )
                        )
                    )
                )

                # === NON-LICENSED WEBSERVICES ===
                # For non-licensed webservices: owner OR user with org role has access
                non_licensed_condition = and_(
                    cls.entity_class.is_licenced.is_(False),
                    org_role_access_level_condition,
                    or_(
                        # Owner has access
                        cls.entity_class.access_levels.any(
                            and_(
                                access_level_entity.id == ORGANIZATION_ROLE_ACCESS_LEVEL,
                                client_entity.owner_id == user_id
                            )
                        ),
                        # User with org role has access
                        user_has_org_role_condition
                    )
                )

                # === LICENSED WEBSERVICES ===
                # For licensed webservices: requires license verification
                # Owner: needs client to have a subscription
                owner_licensed_condition = and_(
                    org_role_access_level_condition,
                    client_entity.owner_id == user_id,
                    client_entity.id.in_(
                        select(subscription_entity.client_id)
                    )
                )

                # Client user: needs to be in subscription_user table
                client_user_licensed_condition = and_(
                    org_role_access_level_condition,
                    exists(
                        select(role_webservice_entity.id)
                        .join(role_entity, role_webservice_entity.role_id == role_entity.id)
                        .where(
                            role_webservice_entity.webservice_id == cls.entity_class.id,
                            role_entity.client_user_roles.any(
                                and_(
                                    client_user_role_entity.client_user.has(
                                        client_user_entity.user_id == user_id
                                    ),
                                    # License verification: client_user exists in subscription_user
                                    client_user_role_entity.client_user_id.in_(
                                        select(subscription_user.c.client_user_id)
                                    )
                                )
                            )
                        )
                    )
                )

                licensed_condition = and_(
                    cls.entity_class.is_licenced.is_(True),
                    or_(owner_licensed_condition, client_user_licensed_condition)
                )

                # Combine: non-licensed OR licensed with valid subscription
                org_role_condition = or_(non_licensed_condition, licensed_condition)

                # Add to existing where clause
                if where is not None:
                    where |= org_role_condition
                else:
                    where = org_role_condition

        return stmt, where

    @classmethod
    async def _user_has_org_role_for_webservice_with_license(
            cls,
            user_id: str,
            webservice_id: str,
            session: AsyncSession
    ) -> bool:
        """
        Check if user has an organization role that grants access to this webservice
        AND has an active license (exists in subscription_user).

        Args:
            user_id: The user ID
            webservice_id: The webservice ID
            session: Database session

        Returns:
            True if user has an organization role that includes this webservice
            AND has an active license
        """
        # Get required entities
        role_entity = cls.app_manager.get_entity("role")
        role_webservice_entity = cls.app_manager.get_entity("role_webservice")
        client_user_role_entity = cls.app_manager.get_entity("client_user_role")
        client_user_entity = cls.app_manager.get_entity("client_user")

        # Query to find a role that:
        # 1. Grants access to this webservice (via role_webservice join)
        # 2. Is assigned to a client_user belonging to this user
        # 3. The client_user has an active license (exists in subscription_user table)
        stmt = (
            select(role_entity)
            .join(role_webservice_entity, role_entity.id == role_webservice_entity.role_id)
            .where(
                # Condition 1: Role grants access to this webservice
                role_webservice_entity.webservice_id == webservice_id,
                # Condition 2 & 3: User has this role via client_user_role AND has license
                role_entity.client_user_roles.any(
                    and_(
                        # User has this role via their client_user
                        client_user_role_entity.client_user.has(
                            client_user_entity.user_id == user_id
                        ),
                        # License verification: client_user exists in subscription_user
                        client_user_role_entity.client_user_id.in_(
                            select(subscription_user.c.client_user_id)
                        )
                    )
                )
            )
            .limit(1)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none() is not None

    @classmethod
    async def _owner_client_has_subscription(
            cls,
            user_id: str,
            session: AsyncSession
    ) -> bool:
        """
        Check if the owner's client has an active subscription.

        Args:
            user_id: The owner's user ID
            session: Database session

        Returns:
            True if the owner's client has a subscription
        """
        client_entity = cls.app_manager.get_entity("client")
        subscription_entity = cls.app_manager.get_entity("subscription")

        # Find if user owns a client that has a subscription
        stmt = (
            select(subscription_entity)
            .where(
                subscription_entity.client_id.in_(
                    select(client_entity.id).where(client_entity.owner_id == user_id)
                )
            )
            .limit(1)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none() is not None

    @classmethod
    async def get_user_access_levels(
            cls,
            webservice: Webservice,
            user: dict[str, Any] | None,
            session: AsyncSession
    ) -> List:
        """
        Get the access levels through which the user can access this webservice.

        For owners:
        - Non-licensed webservices: full access to all ORGANIZATION_ROLE webservices
        - Licensed webservices: access only if their client has a subscription

        For client users:
        - Non-licensed webservices: access via organization role check
        - Licensed webservices: access if they have a license (in subscription_user table)

        Args:
            webservice: The Webservice entity
            user: Connected user dictionary with id, or None for anonymous
            session: Database session

        Returns:
            List of AccessLevel entities the user qualifies for
        """
        if user is not None:
            client_service = cls.app_manager.get_service("client")
            is_owner = await client_service.user_is_client_owner(user["sub"], session)

            if is_owner:
                # Owner access depends on whether webservice requires license
                if webservice.is_licenced:
                    # Licensed webservice: owner needs client to have subscription
                    if await cls._owner_client_has_subscription(user["sub"], session):
                        return [al for al in webservice.access_levels if al.enabled]
                    else:
                        # No subscription, fall through to base access levels (no ORGANIZATION_ROLE)
                        return await RoleWebserviceService.get_user_access_levels(
                            webservice, user, session
                        )
                else:
                    # Non-licensed webservice: owner has full access
                    return [al for al in webservice.access_levels if al.enabled]

        # For licensed webservices, override ORGANIZATION_ROLE check with license verification
        if webservice.is_licenced:
            # Get base access levels from RoleWebserviceService (skip Organization)
            qualified = await RoleWebserviceService.get_user_access_levels(
                webservice, user, session
            )

            for access_level in webservice.access_levels:
                if not access_level.enabled:
                    continue

                # ORGANIZATION_ROLE: check org role + license
                if access_level.id == ORGANIZATION_ROLE_ACCESS_LEVEL:
                    if user is not None:
                        if await cls._user_has_org_role_for_webservice_with_license(
                            user["sub"], webservice.id, session
                        ):
                            qualified.append(access_level)

            return qualified

        # For non-licensed webservices, use standard organization role check (no license)
        return await super().get_user_access_levels(webservice, user, session)