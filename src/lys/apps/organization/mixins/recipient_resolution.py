"""
Organization-scoped recipient resolution mixin.

Extends the role-based RecipientResolutionMixin with organization scoping.
When ``organization_data`` is provided, uses the ``client_user_role`` table
to filter recipients by organization level (client_ids, company_ids, etc.).
Otherwise falls back to parent role-based resolution via the ``user_role`` table.
"""
import logging
from typing import List, Optional

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from lys.apps.user_role.mixins.recipient_resolution import RoleRecipientResolutionMixin

logger = logging.getLogger(__name__)


class OrganizationData(BaseModel):
    """
    Pydantic model for validating organization_data JSON structure.

    Used to scope dispatch to specific organizations/clients in multi-tenant setups.
    Keys follow the pattern "{organization_level}_ids" (e.g., client_ids).

    For applications with additional organization levels (company, establishment, etc.),
    override validate_organization_data() to use a custom Pydantic model with those fields.
    """
    client_ids: Optional[List[str]] = None


class OrganizationRecipientResolutionMixin(RoleRecipientResolutionMixin):
    """
    Extends recipient resolution with organization scoping.

    If organization_data is provided, uses client_user_role table with dynamic
    filters based on organization levels. Otherwise falls back to parent
    role-based resolution via user_role table.
    """

    @classmethod
    def validate_organization_data(cls, organization_data: dict | None) -> OrganizationData | None:
        """
        Validate organization_data JSON structure using Pydantic.

        Override this method to use a custom OrganizationData model with
        additional fields specific to your application.

        Args:
            organization_data: Raw dict from caller

        Returns:
            Validated OrganizationData instance, or None if input is None

        Raises:
            pydantic.ValidationError: If validation fails
        """
        if organization_data is None:
            return None
        return OrganizationData(**organization_data)

    @classmethod
    async def _resolve_recipients(
        cls,
        app_manager,
        session: AsyncSession,
        type_entity,
        triggered_by_user_id: str | None,
        additional_user_ids: List[str] | None,
        organization_data: OrganizationData | None = None,
    ) -> List[str]:
        """
        Resolve recipient user IDs including organization-scoped recipients.

        If organization_data is provided, uses client_user_role table.
        Otherwise, falls back to parent (role-based via user_role table).

        Args:
            app_manager: Application manager for entity/service lookups
            session: Async database session
            type_entity: Type entity with ``roles`` relationship
            triggered_by_user_id: User who triggered the event
            additional_user_ids: Extra users to include
            organization_data: Validated organization scoping data

        Returns:
            Deduplicated list of user IDs
        """
        if not organization_data:
            return await super()._resolve_recipients(
                app_manager=app_manager,
                session=session,
                type_entity=type_entity,
                triggered_by_user_id=triggered_by_user_id,
                additional_user_ids=additional_user_ids,
            )

        recipient_ids = set()

        if triggered_by_user_id:
            recipient_ids.add(triggered_by_user_id)

        if additional_user_ids:
            recipient_ids.update(additional_user_ids)

        role_ids = [role.id for role in type_entity.roles]

        if role_ids:
            recipient_ids.update(
                await cls._resolve_organization_recipients(
                    app_manager, session, role_ids, organization_data
                )
            )

        return list(recipient_ids)

    @classmethod
    async def _resolve_organization_recipients(
        cls,
        app_manager,
        session: AsyncSession,
        role_ids: List[str],
        organization_data: OrganizationData,
    ) -> set[str]:
        """
        Resolve recipient user IDs from client_user_role table with organization scoping.

        Dynamically builds query filters based on organization_data keys.
        For each key in organization_data (e.g., client_ids, company_ids):
        - Converts to attribute name (client_ids -> client_id)
        - Checks if attribute exists on client_user_role or user entity
        - Adds filter if attribute exists, logs warning if not

        Args:
            app_manager: Application manager for entity/service lookups
            session: Async database session
            role_ids: Role IDs to filter by
            organization_data: Validated organization scoping data

        Returns:
            Set of recipient user IDs
        """
        recipient_ids = set()

        client_user_role_entity = app_manager.get_entity("client_user_role", nullable=True)
        user_entity = app_manager.get_entity("user", nullable=True)

        if not client_user_role_entity:
            logger.warning("client_user_role entity not found, skipping organization-scoped recipients")
            return recipient_ids

        org_filters = cls._build_organization_filters(
            organization_data, client_user_role_entity, user_entity
        )

        if org_filters and user_entity:
            stmt = (
                select(client_user_role_entity.user_id)
                .select_from(client_user_role_entity)
                .join(user_entity, client_user_role_entity.user_id == user_entity.id)
                .where(client_user_role_entity.role_id.in_(role_ids), *org_filters)
            )
            result = await session.execute(stmt)
            for row in result:
                recipient_ids.add(row[0])

        return recipient_ids

    @classmethod
    def _resolve_recipients_sync(
        cls,
        app_manager,
        session: Session,
        type_entity,
        triggered_by_user_id: str | None,
        additional_user_ids: List[str] | None,
        organization_data: OrganizationData | None = None,
    ) -> List[str]:
        """
        Synchronous version of organization-scoped recipient resolution.

        Args:
            app_manager: Application manager for entity/service lookups
            session: Sync database session
            type_entity: Type entity with ``roles`` relationship
            triggered_by_user_id: User who triggered the event
            additional_user_ids: Extra users to include
            organization_data: Validated organization scoping data

        Returns:
            Deduplicated list of user IDs
        """
        if not organization_data:
            return super()._resolve_recipients_sync(
                app_manager=app_manager,
                session=session,
                type_entity=type_entity,
                triggered_by_user_id=triggered_by_user_id,
                additional_user_ids=additional_user_ids,
            )

        recipient_ids = set()

        if triggered_by_user_id:
            recipient_ids.add(triggered_by_user_id)

        if additional_user_ids:
            recipient_ids.update(additional_user_ids)

        role_ids = [role.id for role in type_entity.roles]

        if role_ids:
            recipient_ids.update(
                cls._resolve_organization_recipients_sync(
                    app_manager, session, role_ids, organization_data
                )
            )

        return list(recipient_ids)

    @classmethod
    def _resolve_organization_recipients_sync(
        cls,
        app_manager,
        session: Session,
        role_ids: List[str],
        organization_data: OrganizationData,
    ) -> set[str]:
        """
        Synchronous version of organization recipient resolution.

        Args:
            app_manager: Application manager for entity/service lookups
            session: Sync database session
            role_ids: Role IDs to filter by
            organization_data: Validated organization scoping data

        Returns:
            Set of recipient user IDs
        """
        recipient_ids = set()

        client_user_role_entity = app_manager.get_entity("client_user_role", nullable=True)
        user_entity = app_manager.get_entity("user", nullable=True)

        if not client_user_role_entity:
            logger.warning("client_user_role entity not found, skipping organization-scoped recipients")
            return recipient_ids

        org_filters = cls._build_organization_filters(
            organization_data, client_user_role_entity, user_entity
        )

        if org_filters and user_entity:
            stmt = (
                select(client_user_role_entity.user_id)
                .select_from(client_user_role_entity)
                .join(user_entity, client_user_role_entity.user_id == user_entity.id)
                .where(client_user_role_entity.role_id.in_(role_ids), *org_filters)
            )
            result = session.execute(stmt)
            for row in result:
                recipient_ids.add(row[0])

        return recipient_ids

    @classmethod
    def _build_organization_filters(
        cls,
        organization_data: OrganizationData,
        client_user_role_entity,
        user_entity,
    ) -> list:
        """
        Build SQLAlchemy filter clauses from organization_data.

        Dynamically maps organization_data keys (e.g., client_ids) to entity
        attributes (e.g., client_id) on either client_user_role or user entity.

        Args:
            organization_data: Validated organization scoping data
            client_user_role_entity: The client_user_role entity class
            user_entity: The user entity class (may be None)

        Returns:
            List of SQLAlchemy filter clauses
        """
        org_filters = []
        org_data_dict = organization_data.model_dump(exclude_none=True)

        for key, ids in org_data_dict.items():
            if not ids:
                continue

            if key.endswith("_ids"):
                attr_name = key[:-1]  # client_ids -> client_id
            else:
                logger.warning(
                    f"Unexpected organization_data key format: '{key}'. "
                    f"Expected pattern: '{{level}}_ids' (e.g., client_ids)"
                )
                continue

            # client_id is on user entity, other org levels on client_user_role
            if attr_name == "client_id" and user_entity and hasattr(user_entity, attr_name):
                attr = getattr(user_entity, attr_name)
            elif hasattr(client_user_role_entity, attr_name):
                attr = getattr(client_user_role_entity, attr_name)
            else:
                logger.warning(
                    f"Attribute '{attr_name}' not found on client_user_role or user entity. "
                    f"Skipping filter for organization_data key '{key}'."
                )
                continue

            org_filters.append(attr.in_(ids))

        return org_filters