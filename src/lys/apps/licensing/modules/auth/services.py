"""
Auth service for licensing app.

Extends OrganizationAuthService to filter organization webservices based on
license status. Only users with active licenses can access licensed webservices.
"""
from sqlalchemy import select, exists
from sqlalchemy.ext.asyncio import AsyncSession

from lys.apps.licensing.modules.subscription.entities import subscription_user
from lys.apps.organization.consts import ORGANIZATION_ROLE_ACCESS_LEVEL
from lys.apps.organization.modules.auth.services import OrganizationAuthService
from lys.apps.user_auth.modules.user.entities import User
from lys.core.registries import register_service


@register_service()
class LicensingAuthService(OrganizationAuthService):
    """
    Authentication service that filters webservices based on license status.

    For licensed webservices (is_licenced=True):
    - Owners: need their client to have an active subscription
    - Client users: need to be in the subscription_user table

    For non-licensed webservices: same behavior as OrganizationAuthService
    """

    @classmethod
    async def _get_owner_webservices(cls, user_id: str, session: AsyncSession) -> dict:
        """
        Get webservices for clients owned by the user.

        For licensed webservices, the client must have an active subscription.

        Args:
            user_id: User ID
            session: Database session

        Returns:
            Dictionary: {client_id: {"level": "client", "webservices": [...]}}
        """
        client_entity = cls.app_manager.get_entity("client")
        webservice_entity = cls.app_manager.get_entity("webservice")
        access_level_entity = cls.app_manager.get_entity("access_level")
        subscription_entity = cls.app_manager.get_entity("subscription")

        # Get owned clients
        stmt = select(client_entity).where(client_entity.owner_id == user_id)
        result = await session.execute(stmt)
        owned_clients = list(result.scalars().all())

        if not owned_clients:
            return {}

        # Get clients with active subscriptions
        stmt = select(subscription_entity.client_id)
        result = await session.execute(stmt)
        clients_with_subscription = {str(row[0]) for row in result.all()}

        # Get all webservices with ORGANIZATION_ROLE_ACCESS_LEVEL enabled
        stmt = (
            select(webservice_entity)
            .where(
                webservice_entity.access_levels.any(
                    access_level_entity.id == ORGANIZATION_ROLE_ACCESS_LEVEL,
                    enabled=True
                )
            )
        )
        result = await session.execute(stmt)
        all_org_webservices = list(result.scalars().all())

        # Separate licensed and non-licensed webservices
        licensed_ws_names = [ws.id for ws in all_org_webservices if ws.is_licenced]
        non_licensed_ws_names = [ws.id for ws in all_org_webservices if not ws.is_licenced]

        organizations = {}
        for client in owned_clients:
            client_id = str(client.id)

            # Owner gets non-licensed webservices always
            webservices = list(non_licensed_ws_names)

            # Owner gets licensed webservices only if client has subscription
            if client_id in clients_with_subscription:
                webservices.extend(licensed_ws_names)

            if webservices:
                organizations[client_id] = {
                    "level": "client",
                    "webservices": webservices
                }

        return organizations

    @classmethod
    async def _get_client_user_role_webservices(cls, user_id: str, session: AsyncSession) -> dict:
        """
        Get webservices from client_user_roles, filtered by license status.

        For licensed webservices, the client_user must be in subscription_user table.

        Args:
            user_id: User ID
            session: Database session

        Returns:
            Dictionary: {client_id: {"level": "client", "webservices": [...]}}
        """
        client_user_entity = cls.app_manager.get_entity("client_user")

        # Get client_user entries for this user
        stmt = select(client_user_entity).where(client_user_entity.user_id == user_id)
        result = await session.execute(stmt)
        client_users = list(result.scalars().all())

        # Get client_user_ids that have a license (are in subscription_user)
        licensed_client_user_ids = set()
        for client_user in client_users:
            stmt = select(exists().where(subscription_user.c.client_user_id == client_user.id))
            result = await session.execute(stmt)
            if result.scalar():
                licensed_client_user_ids.add(client_user.id)

        organizations = {}

        for client_user in client_users:
            await session.refresh(client_user, ["client_user_roles"])

            has_license = client_user.id in licensed_client_user_ids

            # Collect webservices from all roles
            webservice_names = set()
            for client_user_role in client_user.client_user_roles:
                await session.refresh(client_user_role, ["role"])
                role = client_user_role.role

                if role and role.enabled:
                    await session.refresh(role, ["webservices"])
                    for ws in role.webservices:
                        # Include webservice only if:
                        # - It's not licensed, OR
                        # - User has a license
                        if not ws.is_licenced or has_license:
                            webservice_names.add(ws.id)

            if webservice_names:
                organizations[str(client_user.client_id)] = {
                    "level": "client",
                    "webservices": list(webservice_names)
                }

        return organizations