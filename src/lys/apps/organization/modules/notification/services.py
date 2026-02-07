"""
Notification services for organization app.

Extends NotificationBatchService with organization-scoped recipient resolution.
Inherits role-based resolution from user_role app.
"""
import logging
from typing import List, Optional, Callable

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from lys.apps.organization.modules.notification.entities import NotificationBatch
from lys.apps.user_role.modules.notification.entities import NotificationType
from lys.apps.user_role.modules.notification.services import (
    NotificationBatchService as BaseNotificationBatchService,
)
from lys.core.registries import register_service


class OrganizationData(BaseModel):
    """
    Pydantic model for validating organization_data JSON structure.

    Used to scope notifications to specific organizations/clients in multi-tenant setups.
    Keys follow the pattern "{organization_level}_ids" (e.g., client_ids).

    For applications with additional organization levels (company, establishment, etc.),
    override validate_organization_data() to use a custom Pydantic model with those fields.
    """
    client_ids: Optional[List[str]] = None


@register_service()
class NotificationBatchService(BaseNotificationBatchService):
    """
    Extended NotificationBatchService with organization-scoped recipient resolution.

    Inherits from user_role.NotificationBatchService which provides role-based resolution.

    Adds:
    - organization_data parameter for multi-tenant scoping
    - Resolution of recipients from client_user_role table based on organization levels
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
    async def dispatch(
        cls,
        session: AsyncSession,
        type_id: str,
        data: dict | None = None,
        triggered_by_user_id: str | None = None,
        additional_user_ids: List[str] | None = None,
        organization_data: dict | None = None,
        should_send_fn: Callable[[str], bool] | None = None,
    ) -> NotificationBatch:
        """
        Create a notification batch and dispatch to all recipients.

        Extended implementation adds organization_data for multi-tenant scoping.

        Args:
            session: Database session
            type_id: NotificationType ID (e.g., "ORDER_CREATED")
            data: Event data for frontend formatting
            triggered_by_user_id: User who triggered the notification
            additional_user_ids: Extra users to notify
            organization_data: Organization scoping (e.g., {"client_ids": ["uuid1", "uuid2"]})
            should_send_fn: Optional callback to filter recipients by user preference.
                            Signature: (user_id: str) -> bool
                            If None, all recipients receive the notification.

        Returns:
            Created NotificationBatch with associated Notifications

        Raises:
            ValueError: If NotificationType not found
            pydantic.ValidationError: If organization_data is invalid
        """
        # Validate organization_data
        validated_org_data = cls.validate_organization_data(organization_data)

        # Fetch NotificationType
        notification_type = await session.get(
            cls.app_manager.get_entity("notification_type"),
            type_id
        )
        if not notification_type:
            raise ValueError(f"NotificationType '{type_id}' not found")

        # Create the batch with organization_data
        batch = await cls.create(
            session,
            type_id=type_id,
            triggered_by_user_id=triggered_by_user_id,
            data=data,
            organization_data=organization_data,
        )

        # Resolve recipient user IDs
        recipient_user_ids = await cls._resolve_recipients(
            session=session,
            notification_type=notification_type,
            triggered_by_user_id=triggered_by_user_id,
            additional_user_ids=additional_user_ids,
            organization_data=validated_org_data,
        )

        # Create individual notifications and publish signals
        await cls._create_notifications_and_publish(
            session=session,
            batch=batch,
            recipient_user_ids=recipient_user_ids,
            should_send_fn=should_send_fn,
        )

        return batch

    @classmethod
    async def _resolve_recipients(
        cls,
        session: AsyncSession,
        notification_type: NotificationType,
        triggered_by_user_id: str | None,
        additional_user_ids: List[str] | None,
        organization_data: OrganizationData | None = None,
    ) -> List[str]:
        """
        Resolve recipient user IDs including organization-scoped recipients.

        If organization_data is provided, uses client_user_role table.
        Otherwise, falls back to user_role (inherited from parent).

        Args:
            session: Database session
            notification_type: The NotificationType entity
            triggered_by_user_id: User who triggered the notification
            additional_user_ids: Extra users to include
            organization_data: Validated organization scoping data

        Returns:
            Deduplicated list of user IDs
        """
        # If no organization_data, use parent implementation (role-based via user_role table)
        if not organization_data:
            return await super()._resolve_recipients(
                session=session,
                notification_type=notification_type,
                triggered_by_user_id=triggered_by_user_id,
                additional_user_ids=additional_user_ids,
            )

        # With organization_data, resolve via client_user_role table
        recipient_ids = set()

        # Add triggered_by user
        if triggered_by_user_id:
            recipient_ids.add(triggered_by_user_id)

        # Add additional users
        if additional_user_ids:
            recipient_ids.update(additional_user_ids)

        # Get role IDs from notification type
        role_ids = [role.id for role in notification_type.roles]

        if role_ids:
            recipient_ids.update(
                await cls._resolve_organization_recipients(
                    session, role_ids, organization_data
                )
            )

        return list(recipient_ids)

    @classmethod
    async def _resolve_organization_recipients(
        cls,
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
            session: Database session
            role_ids: Role IDs to filter by
            organization_data: Validated organization scoping data

        Returns:
            Set of recipient user IDs
        """
        logger = logging.getLogger(__name__)
        recipient_ids = set()

        # Get entities
        client_user_role_entity = cls.app_manager.get_entity("client_user_role", nullable=True)
        user_entity = cls.app_manager.get_entity("user", nullable=True)

        if not client_user_role_entity:
            logger.warning("client_user_role entity not found, skipping organization-scoped recipients")
            return recipient_ids

        # Build dynamic filters from organization_data
        org_filters = []
        org_data_dict = organization_data.model_dump(exclude_none=True)

        for key, ids in org_data_dict.items():
            if not ids:
                continue

            # Convert key pattern: client_ids -> client_id
            if key.endswith("_ids"):
                attr_name = key[:-1]  # Remove trailing 's'
            else:
                logger.warning(
                    f"Unexpected organization_data key format: '{key}'. "
                    f"Expected pattern: '{{level}}_ids' (e.g., client_ids)"
                )
                continue

            # Check if attribute exists on client_user_role or user entity
            # client_id is on user entity, other org levels (company_id, etc.) are on client_user_role
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

        # Execute query if we have valid filters
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
    def dispatch_sync(
        cls,
        session: Session,
        type_id: str,
        data: dict | None = None,
        triggered_by_user_id: str | None = None,
        additional_user_ids: List[str] | None = None,
        organization_data: dict | None = None,
        should_send_fn: Callable[[str], bool] | None = None,
    ) -> NotificationBatch:
        """
        Synchronous version of dispatch for use in Celery tasks.

        Extended implementation adds organization_data for multi-tenant scoping.

        Args:
            session: Sync database session
            type_id: NotificationType ID (e.g., "FINANCIAL_IMPORT_COMPLETED")
            data: Event data for frontend formatting
            triggered_by_user_id: User who triggered the notification
            additional_user_ids: Extra users to notify
            organization_data: Organization scoping (e.g., {"client_ids": ["uuid1", "uuid2"]})
            should_send_fn: Optional callback to filter recipients by user preference.
                            Signature: (user_id: str) -> bool
                            If None, all recipients receive the notification.
        """
        # Validate organization_data
        validated_org_data = cls.validate_organization_data(organization_data)

        # Fetch NotificationType
        notification_type = session.get(
            cls.app_manager.get_entity("notification_type"),
            type_id
        )
        if not notification_type:
            raise ValueError(f"NotificationType '{type_id}' not found")

        # Create the batch with organization_data
        batch = cls.entity_class(
            type_id=type_id,
            triggered_by_user_id=triggered_by_user_id,
            data=data,
            organization_data=organization_data,
        )
        session.add(batch)
        session.flush()

        # Resolve recipient user IDs
        recipient_user_ids = cls._resolve_recipients_sync(
            session=session,
            notification_type=notification_type,
            triggered_by_user_id=triggered_by_user_id,
            additional_user_ids=additional_user_ids,
            organization_data=validated_org_data,
        )

        # Create individual notifications and publish signals
        cls._create_notifications_and_publish_sync(
            session=session,
            batch=batch,
            recipient_user_ids=recipient_user_ids,
            should_send_fn=should_send_fn,
        )

        return batch

    @classmethod
    def _resolve_recipients_sync(
        cls,
        session: Session,
        notification_type: NotificationType,
        triggered_by_user_id: str | None,
        additional_user_ids: List[str] | None,
        organization_data: OrganizationData | None = None,
    ) -> List[str]:
        """
        Synchronous version of organization-scoped recipient resolution.
        """
        # If no organization_data, use parent implementation (role-based via user_role table)
        if not organization_data:
            return super()._resolve_recipients_sync(
                session=session,
                notification_type=notification_type,
                triggered_by_user_id=triggered_by_user_id,
                additional_user_ids=additional_user_ids,
            )

        # With organization_data, resolve via client_user_role table
        recipient_ids = set()

        # Add triggered_by user
        if triggered_by_user_id:
            recipient_ids.add(triggered_by_user_id)

        # Add additional users
        if additional_user_ids:
            recipient_ids.update(additional_user_ids)

        # Get role IDs from notification type
        role_ids = [role.id for role in notification_type.roles]

        if role_ids:
            recipient_ids.update(
                cls._resolve_organization_recipients_sync(
                    session, role_ids, organization_data
                )
            )

        return list(recipient_ids)

    @classmethod
    def _resolve_organization_recipients_sync(
        cls,
        session: Session,
        role_ids: List[str],
        organization_data: OrganizationData,
    ) -> set[str]:
        """
        Synchronous version of organization recipient resolution.
        """
        logger = logging.getLogger(__name__)
        recipient_ids = set()

        # Get entities
        client_user_role_entity = cls.app_manager.get_entity("client_user_role", nullable=True)
        user_entity = cls.app_manager.get_entity("user", nullable=True)

        if not client_user_role_entity:
            logger.warning("client_user_role entity not found, skipping organization-scoped recipients")
            return recipient_ids

        # Build dynamic filters from organization_data
        org_filters = []
        org_data_dict = organization_data.model_dump(exclude_none=True)

        for key, ids in org_data_dict.items():
            if not ids:
                continue

            # Convert key pattern: client_ids -> client_id
            if key.endswith("_ids"):
                attr_name = key[:-1]  # Remove trailing 's'
            else:
                logger.warning(
                    f"Unexpected organization_data key format: '{key}'. "
                    f"Expected pattern: '{{level}}_ids' (e.g., client_ids)"
                )
                continue

            # Check if attribute exists on client_user_role or user entity
            # client_id is on user entity, other org levels (company_id, etc.) are on client_user_role
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

        # Execute query if we have valid filters
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