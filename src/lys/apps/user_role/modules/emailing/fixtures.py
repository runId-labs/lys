"""
Emailing fixtures for user_role app.

Provides EmailingTypeFixtures with format_roles method to populate
the emailing_type_role association table during fixture loading.

Consumer apps subclass this fixture and override data_list to define
which emailing types should be dispatched to which roles.
"""
from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lys.apps.user_role.modules.emailing.models import EmailingTypeFixturesModel
from lys.apps.user_role.modules.emailing.services import EmailingTypeService
from lys.core.fixtures import EntityFixtures
from lys.core.registries import register_fixture


@register_fixture(depends_on=["RoleFixtures"])
class EmailingTypeFixtures(EntityFixtures[EmailingTypeService]):
    """
    Fixture for assigning roles to emailing types.

    Uses delete_previous_data = False to avoid disabling emailing types
    created by other fixture classes (user_auth, licensing).

    data_list is empty by default. Consumer apps should subclass and
    override data_list to define role assignments.

    The format_roles method converts role ID strings to Role entities
    for the many-to-many relationship on EmailingType.
    """
    model = EmailingTypeFixturesModel
    delete_previous_data = False

    data_list = []

    @classmethod
    async def format_roles(cls, role_ids: List[str], session: AsyncSession) -> List:
        """
        Get Role entities for the given role IDs.

        Called automatically by _format_attributes when "roles" key is present
        in a data_list item's attributes.

        Args:
            role_ids: List of role ID strings (e.g., ["ADMIN", "SUPERVISOR"])
            session: Database session

        Returns:
            List of Role entities for the many-to-many relationship
        """
        role_class = cls.app_manager.get_entity("role")
        result = await session.execute(
            select(role_class).where(role_class.id.in_(role_ids))
        )
        return list(result.scalars().all())