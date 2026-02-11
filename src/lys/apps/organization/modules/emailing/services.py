"""
Emailing services for organization app.

Extends EmailingBatchService with organization-scoped recipient resolution
via OrganizationRecipientResolutionMixin.
Inherits role-based resolution from user_role app.
"""
from typing import List, Callable

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from lys.apps.organization.mixins.recipient_resolution import OrganizationRecipientResolutionMixin
from lys.apps.user_role.modules.emailing.services import (
    EmailingBatchService as BaseEmailingBatchService,
)
from lys.core.registries import register_service


@register_service()
class EmailingBatchService(OrganizationRecipientResolutionMixin, BaseEmailingBatchService):
    """
    Extended EmailingBatchService with organization-scoped recipient resolution.

    Inherits from user_role.EmailingBatchService which provides role-based resolution.

    Adds:
    - organization_data parameter for multi-tenant scoping
    - Resolution of recipients from client_user_role table based on organization levels

    Organization data validation and recipient resolution are provided by
    OrganizationRecipientResolutionMixin.
    """

    @classmethod
    async def dispatch(
        cls,
        session: AsyncSession,
        type_id: str,
        email_context: dict | None = None,
        triggered_by_user_id: str | None = None,
        additional_user_ids: List[str] | None = None,
        organization_data: dict | None = None,
        should_send_fn: Callable[[str], bool] | None = None,
    ) -> List[str]:
        """
        Create and send emails to all resolved recipients.

        Extended implementation adds organization_data for multi-tenant scoping.

        Args:
            session: Async database session
            type_id: EmailingType ID (e.g., "LICENSE_GRANTED")
            email_context: Context data for the email template
            triggered_by_user_id: User who triggered the event
            additional_user_ids: Extra users to email
            organization_data: Organization scoping (e.g., {"client_ids": ["uuid1", "uuid2"]})
            should_send_fn: Optional callback to filter recipients by user preference.

        Returns:
            List of created Emailing IDs

        Raises:
            ValueError: If EmailingType not found
            pydantic.ValidationError: If organization_data is invalid
        """
        # Validate organization_data
        validated_org_data = cls.validate_organization_data(organization_data)

        # Fetch EmailingType
        emailing_type = await session.get(
            cls.app_manager.get_entity("emailing_type"),
            type_id
        )
        if not emailing_type:
            raise ValueError(f"EmailingType '{type_id}' not found")

        # Resolve recipients via mixin
        recipient_user_ids = await cls._resolve_recipients(
            app_manager=cls.app_manager,
            session=session,
            type_entity=emailing_type,
            triggered_by_user_id=triggered_by_user_id,
            additional_user_ids=additional_user_ids,
            organization_data=validated_org_data,
        )

        # Create and send emails
        return await cls._create_and_send_emails(
            session=session,
            type_id=type_id,
            email_context=email_context,
            recipient_user_ids=recipient_user_ids,
            should_send_fn=should_send_fn,
        )

    @classmethod
    def dispatch_sync(
        cls,
        session: Session,
        type_id: str,
        email_context: dict | None = None,
        triggered_by_user_id: str | None = None,
        additional_user_ids: List[str] | None = None,
        organization_data: dict | None = None,
        should_send_fn: Callable[[str], bool] | None = None,
    ) -> List[str]:
        """
        Synchronous version of dispatch for use in Celery tasks.

        Extended implementation adds organization_data for multi-tenant scoping.

        Args:
            session: Sync database session
            type_id: EmailingType ID (e.g., "LICENSE_GRANTED")
            email_context: Context data for the email template
            triggered_by_user_id: User who triggered the event
            additional_user_ids: Extra users to email
            organization_data: Organization scoping (e.g., {"client_ids": ["uuid1", "uuid2"]})
            should_send_fn: Optional callback to filter recipients by user preference.

        Returns:
            List of created Emailing IDs
        """
        # Validate organization_data
        validated_org_data = cls.validate_organization_data(organization_data)

        # Fetch EmailingType
        emailing_type = session.get(
            cls.app_manager.get_entity("emailing_type"),
            type_id
        )
        if not emailing_type:
            raise ValueError(f"EmailingType '{type_id}' not found")

        # Resolve recipients via mixin
        recipient_user_ids = cls._resolve_recipients_sync(
            app_manager=cls.app_manager,
            session=session,
            type_entity=emailing_type,
            triggered_by_user_id=triggered_by_user_id,
            additional_user_ids=additional_user_ids,
            organization_data=validated_org_data,
        )

        # Create and send emails
        return cls._create_and_send_emails_sync(
            session=session,
            type_id=type_id,
            email_context=email_context,
            recipient_user_ids=recipient_user_ids,
            should_send_fn=should_send_fn,
        )