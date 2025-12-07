"""
Webservice service for licensing app.

Extends OrganizationWebserviceService to add license verification.
Users must have an active subscription (via subscription_user) to access
webservices with ORGANIZATION_ROLE access level.
"""

from typing import Any, List, Optional

from sqlalchemy import Select, BinaryExpression, and_, or_, select
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
            user_id = user.get("id")
            if user_id:
                # Get required entities
                access_level_entity = cls.app_manager.get_entity("access_level")
                role_entity = cls.app_manager.get_entity("role")
                client_user_role_entity = cls.app_manager.get_entity("client_user_role")
                client_user_entity = cls.app_manager.get_entity("client_user")

                # Base condition: ORGANIZATION_ROLE access level + user has org role
                org_role_base_condition = and_(
                    cls.entity_class.access_levels.any(
                        access_level_entity.id == ORGANIZATION_ROLE_ACCESS_LEVEL,
                        enabled=True
                    ),
                    cls.entity_class.roles.any(
                        role_entity.client_user_roles.any(
                            client_user_role_entity.client_user.has(
                                client_user_entity.user_id == user_id
                            )
                        )
                    )
                )

                # Condition for non-licensed webservices: no license check needed
                non_licensed_condition = and_(
                    cls.entity_class.is_licenced.is_(False),
                    org_role_base_condition
                )

                # Condition for licensed webservices: requires license verification
                licensed_condition = and_(
                    cls.entity_class.is_licenced.is_(True),
                    cls.entity_class.access_levels.any(
                        access_level_entity.id == ORGANIZATION_ROLE_ACCESS_LEVEL,
                        enabled=True
                    ),
                    cls.entity_class.roles.any(
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
        role_entity = cls.app_manager.get_entity("role")
        client_user_role_entity = cls.app_manager.get_entity("client_user_role")
        client_user_entity = cls.app_manager.get_entity("client_user")

        stmt = (
            select(role_entity)
            .where(
                role_entity.webservices.any(id=webservice_id),
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

        For licensed webservices (is_licenced=True), requires license verification.
        For non-licensed webservices, uses standard organization role check.

        Args:
            webservice: The Webservice entity
            user: Connected user dictionary with id, or None for anonymous
            session: Database session

        Returns:
            List of AccessLevel entities the user qualifies for
        """
        # Client owner gets all enabled access levels (from parent)
        if user is not None:
            client_service = cls.app_manager.get_service("client")
            if await client_service.user_is_client_owner(user["id"], session):
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
                            user["id"], webservice.id, session
                        ):
                            qualified.append(access_level)

            return qualified

        # For non-licensed webservices, use standard organization role check (no license)
        return await super().get_user_access_levels(webservice, user, session)