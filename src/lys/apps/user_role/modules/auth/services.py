"""
Auth service for user_role app.

Extends AuthService to add webservices claim to JWT based on user roles.
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lys.apps.user_auth.modules.auth.services import AuthService
from lys.apps.user_auth.modules.user.entities import User
from lys.core.registries import register_service


@register_service()
class RoleAuthService(AuthService):
    """
    Authentication service that includes role-based webservices in JWT claims.

    Extends the base AuthService to add a 'webservices' claim containing
    the names of all webservices the user can access through their roles.
    """

    @classmethod
    async def generate_access_claims(cls, user: User, session: AsyncSession) -> dict:
        """
        Generate JWT claims including webservices from user roles.

        Extends parent claims by adding role-based webservices to the
        existing webservices dict. Role-based webservices always grant "full" access.

        Args:
            user: The authenticated user entity
            session: Database session for queries

        Returns:
            Dictionary of claims with merged webservices dict
        """
        # Get base claims from parent (includes base webservices)
        claims = await super().generate_access_claims(user, session)

        # Super users get all webservices - handled by permission layer, not JWT
        if user.is_super_user:
            return claims

        # Get webservices from user roles and merge with base webservices
        # Role-based access is always "full" (no row-level filtering)
        role_webservices = await cls._get_user_role_webservices(user.id, session)
        base_webservices = claims.get("webservices", {})

        # Merge: role webservices with "full" access
        for ws_name in role_webservices:
            # Role access upgrades to "full" even if base was "owner"
            base_webservices[ws_name] = "full"

        claims["webservices"] = base_webservices

        return claims

    @classmethod
    async def _get_user_role_webservices(cls, user_id: str, session: AsyncSession) -> list[str]:
        """
        Get all webservice names accessible to user through their roles.

        Args:
            user_id: User ID to query roles for
            session: Database session

        Returns:
            List of webservice names (unique)
        """
        role_entity = cls.app_manager.get_entity("role")

        # Query roles assigned to user that are enabled
        stmt = (
            select(role_entity)
            .where(
                role_entity.users.any(id=user_id),
                role_entity.enabled.is_(True)
            )
        )
        result = await session.execute(stmt)
        roles = list(result.scalars().all())

        # Collect unique webservice names from all roles
        webservice_names = set()
        for role in roles:
            # Load webservices relationship if not loaded
            await session.refresh(role, ["webservices"])
            for ws in role.webservices:
                webservice_names.add(ws.id)

        return list(webservice_names)