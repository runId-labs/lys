"""
Subscription services.

This module provides:
- SubscriptionService: Core subscription management
"""
from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lys.apps.licensing.errors import (
    SUBSCRIPTION_ALREADY_EXISTS,
    NO_ACTIVE_SUBSCRIPTION,
    PLAN_VERSION_NOT_FOUND
)
from lys.apps.licensing.modules.subscription.entities import Subscription, subscription_user
from lys.core.errors import LysError
from lys.core.registries import register_service
from lys.core.services import EntityService


@register_service()
class SubscriptionService(EntityService[Subscription]):
    """
    Service for managing client subscriptions.

    Each client has at most one active subscription at a time.
    Subscriptions link clients to plan versions.
    """

    @classmethod
    async def get_client_subscription(
        cls,
        client_id: str,
        session: AsyncSession
    ) -> Subscription | None:
        """
        Get the active subscription for a client.

        Args:
            client_id: Client ID
            session: Database session

        Returns:
            Subscription entity or None if no active subscription
        """
        stmt = select(cls.entity_class).where(
            cls.entity_class.client_id == client_id
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @classmethod
    async def create_subscription(
        cls,
        client_id: str,
        plan_version_id: str,
        session: AsyncSession,
        stripe_subscription_id: str | None = None
    ) -> Subscription:
        """
        Create a new subscription for a client.

        Args:
            client_id: Client ID
            plan_version_id: Plan version to subscribe to
            session: Database session
            stripe_subscription_id: Optional Stripe subscription ID

        Returns:
            New Subscription entity

        Raises:
            LysError: If client already has a subscription
        """
        # Check if client already has a subscription
        existing = await cls.get_client_subscription(client_id, session)
        if existing:
            raise LysError(
                SUBSCRIPTION_ALREADY_EXISTS,
                f"Client {client_id} already has an active subscription"
            )

        # Verify plan version exists
        plan_version_service = cls.app_manager.get_service("license_plan_version")
        plan_version = await plan_version_service.get_by_id(plan_version_id, session)
        if not plan_version:
            raise LysError(
                PLAN_VERSION_NOT_FOUND,
                f"Plan version {plan_version_id} not found"
            )

        return await cls.create(
            session,
            client_id=client_id,
            plan_version_id=plan_version_id,
            stripe_subscription_id=stripe_subscription_id
        )

    @classmethod
    async def change_plan(
        cls,
        client_id: str,
        new_plan_version_id: str,
        session: AsyncSession,
        immediate: bool = True
    ) -> Subscription:
        """
        Change the subscription plan for a client.

        Args:
            client_id: Client ID
            new_plan_version_id: New plan version to switch to
            session: Database session
            immediate: If True, change immediately. If False, schedule for period end.

        Returns:
            Updated Subscription entity

        Raises:
            LysError: If client has no subscription or plan version not found
        """
        subscription = await cls.get_client_subscription(client_id, session)
        if not subscription:
            raise LysError(
                NO_ACTIVE_SUBSCRIPTION,
                f"Client {client_id} has no active subscription"
            )

        # Verify new plan version exists
        plan_version_service = cls.app_manager.get_service("license_plan_version")
        new_version = await plan_version_service.get_by_id(new_plan_version_id, session)
        if not new_version:
            raise LysError(
                PLAN_VERSION_NOT_FOUND,
                f"Plan version {new_plan_version_id} not found"
            )

        if immediate:
            subscription.plan_version_id = new_plan_version_id
            subscription.pending_plan_version_id = None
        else:
            # Schedule change for billing period end (downgrade)
            subscription.pending_plan_version_id = new_plan_version_id

        return subscription

    @classmethod
    async def apply_pending_change(
        cls,
        subscription_id: str,
        session: AsyncSession
    ) -> Subscription | None:
        """
        Apply a pending plan change (called at billing period end).

        Args:
            subscription_id: Subscription ID
            session: Database session

        Returns:
            Updated Subscription or None if no pending change
        """
        subscription = await cls.get_by_id(subscription_id, session)
        if not subscription or not subscription.pending_plan_version_id:
            return None

        subscription.plan_version_id = subscription.pending_plan_version_id
        subscription.pending_plan_version_id = None
        return subscription

    @classmethod
    async def add_user_to_subscription(
        cls,
        subscription_id: str,
        client_user_id: str,
        session: AsyncSession
    ) -> None:
        """
        Add a user to a subscription (license seat).

        Args:
            subscription_id: Subscription ID
            client_user_id: Client user ID
            session: Database session
        """
        stmt = subscription_user.insert().values(
            subscription_id=subscription_id,
            client_user_id=client_user_id
        )
        await session.execute(stmt)

    @classmethod
    async def remove_user_from_subscription(
        cls,
        subscription_id: str,
        client_user_id: str,
        session: AsyncSession
    ) -> None:
        """
        Remove a user from a subscription.

        Args:
            subscription_id: Subscription ID
            client_user_id: Client user ID
            session: Database session
        """
        stmt = subscription_user.delete().where(
            subscription_user.c.subscription_id == subscription_id,
            subscription_user.c.client_user_id == client_user_id
        )
        await session.execute(stmt)

    @classmethod
    async def get_subscription_user_count(
        cls,
        subscription_id: str,
        session: AsyncSession
    ) -> int:
        """
        Get the number of users on a subscription.

        Args:
            subscription_id: Subscription ID
            session: Database session

        Returns:
            Number of users
        """
        from sqlalchemy import func
        stmt = select(func.count()).select_from(subscription_user).where(
            subscription_user.c.subscription_id == subscription_id
        )
        result = await session.execute(stmt)
        return result.scalar() or 0