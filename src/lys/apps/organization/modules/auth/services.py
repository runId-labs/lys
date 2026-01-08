"""
Auth service for organization app.

Extends RoleAuthService to add organizations claim to JWT based on client ownership
and client user roles.

=============================================================================
IMPORTANT: JWT CLAIMS GENERATION OVERRIDE CHAIN
=============================================================================

The generate_access_claims() method follows an inheritance chain where each
app extends the JWT claims with its own access levels:

    AuthService.generate_access_claims()
        → Handles: PUBLIC, CONNECTED, OWNER access levels
        → Returns: {"sub", "is_super_user", "webservices"}

            ↓ super()

    RoleAuthService.generate_access_claims()
        → Adds: ROLE access level webservices (from user's global roles)
        → Merges into: webservices dict

            ↓ super()

    OrganizationAuthService.generate_access_claims()  [THIS CLASS]
        → Adds: ORGANIZATION_ROLE access level
        → Adds: "organizations" claim (per-org scoped webservices)

Each class MUST call super() first, then extend the claims.

NOTE: For super_users, the permission layer grants access to everything,
but AI tool filtering uses JWT claims. See AIToolService.get_accessible_tools()
which bypasses filtering for super_users.
=============================================================================
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lys.apps.organization.consts import ORGANIZATION_ROLE_ACCESS_LEVEL
from lys.apps.user_auth.modules.user.entities import User
from lys.apps.user_role.modules.auth.services import RoleAuthService
from lys.core.registries import register_service


@register_service()
class OrganizationAuthService(RoleAuthService):
    """
    Authentication service that includes organization-scoped webservices in JWT claims.

    Extends RoleAuthService to add an 'organizations' claim containing
    the webservices each user can access within each organization.

    See module docstring for the full override chain documentation.

    JWT Structure:
    {
        "sub": "user-id",
        "is_super_user": false,
        "webservices": ["logout", "me", ...],
        "organizations": {
            "client-uuid-1": {
                "level": "client",
                "webservices": ["manage_billing", "list_projects"]
            }
        }
    }
    """

    @classmethod
    async def generate_access_claims(cls, user: User, session: AsyncSession) -> dict:
        """
        Generate JWT claims including organizations from ownership and roles.

        Args:
            user: The authenticated user entity
            session: Database session for queries

        Returns:
            Dictionary of claims including organizations dict
        """
        # Get base claims from parent (includes webservices from user roles)
        claims = await super().generate_access_claims(user, session)

        # Super users don't need organization claims - handled by permission layer
        if user.is_super_user:
            return claims

        # Get organization access
        organizations = await cls._get_user_organizations(user.id, session)
        if organizations:
            claims["organizations"] = organizations

        return claims

    @classmethod
    async def _get_user_organizations(cls, user_id: str, session: AsyncSession) -> dict:
        """
        Get all organizations the user has access to with their webservices.

        For owners: all webservices with ORGANIZATION_ROLE_ACCESS_LEVEL enabled
        For client users: webservices from their assigned roles

        Args:
            user_id: User ID
            session: Database session

        Returns:
            Dictionary: {org_id: {"level": "client", "webservices": [...]}}
        """
        organizations = {}

        # Get webservices for owned clients
        owned_orgs = await cls._get_owner_webservices(user_id, session)
        organizations.update(owned_orgs)

        # Get webservices from client_user_roles
        role_orgs = await cls._get_client_user_role_webservices(user_id, session)

        # Merge: if user is both owner and has roles, combine webservices
        for org_id, org_data in role_orgs.items():
            if org_id in organizations:
                # Owner already has all ORGANIZATION_ROLE webservices
                # Role webservices are a subset, so owner wins
                pass
            else:
                organizations[org_id] = org_data

        return organizations

    @classmethod
    async def _get_owner_webservices(cls, user_id: str, session: AsyncSession) -> dict:
        """
        Get webservices for clients owned by the user.

        Owners get all webservices that have ORGANIZATION_ROLE_ACCESS_LEVEL enabled.

        Args:
            user_id: User ID
            session: Database session

        Returns:
            Dictionary: {client_id: {"level": "client", "webservices": [...]}}
        """
        client_entity = cls.app_manager.get_entity("client")
        webservice_entity = cls.app_manager.get_entity("webservice")
        access_level_entity = cls.app_manager.get_entity("access_level")

        # Get owned clients
        stmt = select(client_entity.id).where(client_entity.owner_id == user_id)
        result = await session.execute(stmt)
        owned_client_ids = [str(row[0]) for row in result.all()]

        if not owned_client_ids:
            return {}

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
        org_webservices = [ws.id for ws in result.scalars().all()]

        # Each owned client gets all organization webservices
        organizations = {}
        for client_id in owned_client_ids:
            organizations[client_id] = {
                "level": "client",
                "webservices": org_webservices
            }

        return organizations

    @classmethod
    async def _get_client_user_role_webservices(cls, user_id: str, session: AsyncSession) -> dict:
        """
        Get webservices from client_user_roles.

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

        organizations = {}

        for client_user in client_users:
            await session.refresh(client_user, ["client_user_roles"])

            # Collect webservices from all roles
            webservice_ids = set()
            for client_user_role in client_user.client_user_roles:
                await session.refresh(client_user_role, ["role"])
                role = client_user_role.role

                if role and role.enabled:
                    webservice_ids.update(role.get_webservice_ids())

            if webservice_ids:
                organizations[str(client_user.client_id)] = {
                    "level": "client",
                    "webservices": list(webservice_ids)
                }

        return organizations