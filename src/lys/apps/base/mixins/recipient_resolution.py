"""
Base mixin for recipient resolution in batch dispatch services.

Provides the foundational recipient resolution logic used by both
NotificationBatchService and EmailingBatchService.

Override chain:
    base.RecipientResolutionMixin (triggered_by + additional)
    → user_role.RoleRecipientResolutionMixin (+ role-based)
    → organization.OrganizationRecipientResolutionMixin (+ org-scoped)
"""
from typing import List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session


class RecipientResolutionMixin:
    """
    Mixin providing recipient resolution for batch dispatch services.

    Base implementation resolves recipients from:
    1. The user who triggered the event (if provided)
    2. Any additional user IDs explicitly specified

    All methods receive ``app_manager`` as an explicit parameter so the mixin
    remains self-contained and testable without requiring a specific host class.
    """

    @classmethod
    async def _resolve_recipients(
        cls,
        app_manager,
        session: AsyncSession,
        type_entity,
        triggered_by_user_id: str | None,
        additional_user_ids: List[str] | None,
    ) -> List[str]:
        """
        Resolve recipient user IDs for a batch dispatch.

        Base implementation only includes:
        1. The triggering user
        2. Additional explicit user IDs

        Args:
            app_manager: Application manager for entity/service lookups
            session: Async database session
            type_entity: The type entity (NotificationType or EmailingType)
            triggered_by_user_id: User who triggered the event
            additional_user_ids: Extra users to include

        Returns:
            Deduplicated list of user IDs
        """
        recipient_ids = set()

        if triggered_by_user_id:
            recipient_ids.add(triggered_by_user_id)

        if additional_user_ids:
            recipient_ids.update(additional_user_ids)

        return list(recipient_ids)

    @classmethod
    def _resolve_recipients_sync(
        cls,
        app_manager,
        session: Session,
        type_entity,
        triggered_by_user_id: str | None,
        additional_user_ids: List[str] | None,
    ) -> List[str]:
        """
        Synchronous version of recipient resolution for Celery tasks.

        Args:
            app_manager: Application manager for entity/service lookups
            session: Sync database session
            type_entity: The type entity (NotificationType or EmailingType)
            triggered_by_user_id: User who triggered the event
            additional_user_ids: Extra users to include

        Returns:
            Deduplicated list of user IDs
        """
        recipient_ids = set()

        if triggered_by_user_id:
            recipient_ids.add(triggered_by_user_id)

        if additional_user_ids:
            recipient_ids.update(additional_user_ids)

        return list(recipient_ids)