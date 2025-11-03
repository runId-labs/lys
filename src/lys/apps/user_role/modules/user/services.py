from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lys.apps.user_auth.modules.user.services import UserService as AuthUserService
from lys.apps.user_role.modules.user.entities import User
from lys.core.registers import register_service


@register_service()
class UserService(AuthUserService):
    """
    Extended UserService with role management capabilities.

    Extends the base UserService from user_auth to add role assignment functionality.
    """

    @classmethod
    async def create_user(
        cls,
        session: AsyncSession,
        email: str,
        password: str,
        language_id: str,
        send_verification_email: bool = True,
        background_tasks=None,
        roles: Optional[List[str]] = None,
        first_name: str | None = None,
        last_name: str | None = None,
        gender_id: str | None = None
    ) -> User:
        """
        Create a new user with optional role assignments.

        This method extends the base create_user from user_auth to support role assignment
        during user creation.

        Args:
            session: Database session for executing queries
            email: Email address for the new user (will be normalized to lowercase)
            password: Plain text password (will be hashed)
            language_id: Language ID for the user
            send_verification_email: Whether to send email verification email (default: True)
            background_tasks: FastAPI BackgroundTasks for scheduling email (optional)
            roles: Optional list of role IDs to assign to the new user
            first_name: Optional first name (GDPR-protected)
            last_name: Optional last name (GDPR-protected)
            gender_id: Optional gender ID (MALE, FEMALE, OTHER)

        Returns:
            User: The created user entity with assigned roles

        Raises:
            LysError: If validation fails (duplicate email, invalid password, etc.)
        """
        # Query role entities if provided
        role_entities = []
        if roles:
            role_service = cls.app_manager.get_service("role")
            role_entity = role_service.entity_class

            stmt = select(role_entity).where(role_entity.id.in_(roles))
            result = await session.execute(stmt)
            role_entities = list(result.scalars().all())

        # Create user with roles via parent's _create_user_internal
        user = await cls._create_user_internal(
            session=session,
            email=email,
            password=password,
            language_id=language_id,
            is_super_user=False,
            send_verification_email=send_verification_email,
            background_tasks=background_tasks,
            first_name=first_name,
            last_name=last_name,
            gender_id=gender_id,
            roles=role_entities
        )

        return user