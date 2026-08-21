"""
Subscription services.

This module provides:
- SubscriptionService: Core subscription management
"""

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from lys.apps.licensing.consts import (
    BILLING_TERMS_CHANGE_ERROR,
    CANCEL_SUBSCRIPTION_FAILED_ERROR,
    NOTICE_PERIOD_EXPIRED_ERROR,
    CHECKOUT_SESSION_FAILED_ERROR,
    DEFAULT_CURRENCY,
    FREE_PLAN,
    MANUAL_BILLING,
    MANUAL_GRANT,
    NO_ACTIVE_SUBSCRIPTION_ERROR,
    NO_COMMITMENT,
    NO_PROVIDER_SUBSCRIPTION_ERROR,
    PLAN_NOT_FOUND_ERROR,
    PLAN_NOT_PRICED_ERROR,
    SAME_PLAN_ERROR,
)
from lys.apps.licensing.errors import (
    DISCOUNT_ALREADY_GRANTED,
    DISCOUNT_NOT_AVAILABLE,
    DISCOUNT_NOT_FOUND,
    DISCOUNT_WITHOUT_PRICE,
    NO_ACTIVE_SUBSCRIPTION,
    PROVIDER_SUBSCRIPTION_ACTIVE,
    UNKNOWN_BILLING_MODE,
    PLAN_VERSION_NOT_FOUND,
    PLAN_VERSION_NOT_PRICED,
    PLAN_VERSION_PRICE_NOT_FOUND,
    SUBSCRIPTION_ALREADY_EXISTS,
    USER_ALREADY_LICENSED,
    USER_NOT_LICENSED,
)
from lys.apps.licensing.modules.discount.amounts import discounted_amount
from lys.apps.licensing.modules.event.consts import SUBSCRIPTION_CANCELED
from lys.apps.user_auth.modules.event.tasks import trigger_event
from lys.apps.licensing.modules.mollie.models import (
    CancelSubscriptionResult,
    SubscribeToPlanResult,
)
from lys.apps.licensing.modules.mollie.services import get_mollie_client
from lys.apps.licensing.modules.subscription.entities import (
    LicenseBillingMode,
    Subscription,
    subscription_user,
)
from lys.apps.licensing.modules.subscription.prorata import (
    calculate_period_end,
    calculate_prorata,
    is_upgrade,
)
from lys.core.errors import LysError
from lys.core.registries import register_service
from lys.core.services import EntityService

if TYPE_CHECKING:
    # Annotations only: entities are resolved through app_manager at runtime,
    # never imported. Declaring them here lets a consumer of this service see
    # what it is handed without the import ever executing.
    from lys.apps.licensing.modules.discount.entities import SubscriptionDiscount
    from lys.apps.licensing.modules.plan.entities import LicensePlanVersionPrice

logger = logging.getLogger(__name__)


@register_service()
class LicenseBillingModeService(EntityService[LicenseBillingMode]):
    """
    Service for managing billing modes.

    Billing modes are reference data: they are provisioned by fixtures and
    referenced by subscriptions to route collection.
    """


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
    def get_client_subscription_sync(
        cls,
        client_id: str,
        session: Session
    ) -> Subscription | None:
        """
        Get the active subscription for a client (sync — for Celery task contexts).

        Args:
            client_id: Client ID
            session: Sync database session

        Returns:
            Subscription entity or None if no active subscription
        """
        stmt = select(cls.entity_class).where(
            cls.entity_class.client_id == client_id
        )
        result = session.execute(stmt)
        return result.scalar_one_or_none()

    @classmethod
    async def create_subscription(
        cls,
        client_id: str,
        plan_version_id: str,
        session: AsyncSession,
        provider_subscription_id: str | None = None
    ) -> Subscription:
        """
        Create a new subscription for a client.

        Args:
            client_id: Client ID
            plan_version_id: Plan version to subscribe to
            session: Database session
            provider_subscription_id: Optional payment provider subscription ID

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
            provider_subscription_id=provider_subscription_id
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

        Administrative change: it does not talk to the payment provider. An
        immediate change realigns the subscribed price on the new version, using
        the periodicity and currency already subscribed to, so that the plan and
        the price recorded always belong to the same version. A deferred change
        leaves the price alone; it is resolved when apply_pending_plan_changes
        runs.

        Args:
            client_id: Client ID
            new_plan_version_id: New plan version to switch to
            session: Database session
            immediate: If True, change immediately. If False, schedule for period end.

        Returns:
            Updated Subscription entity

        Raises:
            LysError: If client has no subscription, the plan version does not
                exist, or the target version is paid but carries no price on the
                terms currently subscribed to
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
            current_price = subscription.plan_version_price
            new_price = None

            if current_price is not None:
                new_price = new_version.price_for(
                    current_price.period_id,
                    current_price.currency_id,
                    current_price.commitment_id
                )
                if new_price is None and not new_version.is_free:
                    raise LysError(
                        PLAN_VERSION_NOT_PRICED,
                        f"Plan version {new_plan_version_id} has no price for "
                        f"{current_price.period_id}/{current_price.currency_id}/"
                        f"{current_price.commitment_id}"
                    )

            subscription.plan_version_id = new_plan_version_id
            subscription.pending_plan_version_id = None
            subscription.plan_version_price_id = new_price.id if new_price else None
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
    async def is_user_in_subscription(
        cls,
        subscription_id: str,
        user_id: str,
        session: AsyncSession
    ) -> bool:
        """
        Check if a user is already in a subscription.

        Args:
            subscription_id: Subscription ID
            user_id: User ID
            session: Database session

        Returns:
            True if user is already in the subscription
        """
        stmt = select(subscription_user).where(
            subscription_user.c.subscription_id == subscription_id,
            subscription_user.c.user_id == user_id
        ).limit(1)
        result = await session.execute(stmt)
        return result.first() is not None

    @classmethod
    async def add_user_to_subscription(
        cls,
        subscription_id: str,
        user_id: str,
        session: AsyncSession
    ) -> None:
        """
        Add a user to a subscription (license seat).

        Args:
            subscription_id: Subscription ID
            user_id: User ID
            session: Database session

        Raises:
            LysError: If user is already in the subscription
        """
        # Check if user is already in the subscription
        if await cls.is_user_in_subscription(subscription_id, user_id, session):
            raise LysError(
                USER_ALREADY_LICENSED,
                f"User {user_id} is already in subscription {subscription_id}"
            )

        stmt = subscription_user.insert().values(
            subscription_id=subscription_id,
            user_id=user_id
        )
        await session.execute(stmt)

    @classmethod
    async def remove_user_from_subscription(
        cls,
        subscription_id: str,
        user_id: str,
        session: AsyncSession
    ) -> None:
        """
        Remove a user from a subscription.

        Args:
            subscription_id: Subscription ID
            user_id: User ID
            session: Database session

        Raises:
            LysError: If user is not in the subscription
        """
        # Check if user is in the subscription
        if not await cls.is_user_in_subscription(subscription_id, user_id, session):
            raise LysError(
                USER_NOT_LICENSED,
                f"User {user_id} is not in subscription {subscription_id}"
            )

        stmt = subscription_user.delete().where(
            subscription_user.c.subscription_id == subscription_id,
            subscription_user.c.user_id == user_id
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
        stmt = select(func.count()).select_from(subscription_user).where(
            subscription_user.c.subscription_id == subscription_id
        )
        result = await session.execute(stmt)
        return result.scalar() or 0

    @classmethod
    async def is_user_licensed(
        cls,
        user_id: str,
        session: AsyncSession
    ) -> bool:
        """
        Check if a user has a license (is associated with any subscription).

        Args:
            user_id: User ID
            session: Database session

        Returns:
            True if user is associated with a subscription
        """
        stmt = select(subscription_user).where(
            subscription_user.c.user_id == user_id
        ).limit(1)
        result = await session.execute(stmt)
        return result.first() is not None

    # =========================================================================
    # Manual billing (collection handled outside the application)
    # =========================================================================

    @classmethod
    async def get_granted_discount(
        cls,
        subscription: Subscription,
        session: AsyncSession
    ) -> Optional["SubscriptionDiscount"]:
        """Return the discount the subscription benefits from, if any."""
        granted_entity = cls.app_manager.get_entity("subscription_discount")
        result = await session.execute(
            select(granted_entity).where(
                granted_entity.subscription_id == subscription.id
            )
        )

        return result.scalar_one_or_none()

    @classmethod
    def settle(
        cls,
        price: Optional["LicensePlanVersionPrice"],
        granted: Optional["SubscriptionDiscount"],
        commitment_end_date: Optional[datetime]
    ) -> tuple[int | None, dict | None]:
        """
        Settle the amount owed and the receipt that justifies it.

        Synchronous and session-free on purpose: the terms are settled from two
        places that cannot share a session — this service, asynchronously, and
        the renewal task, synchronously. Computing them twice would be the surest
        way to see them drift.

        The receipt reads on its own: it repeats the currency, the periodicity
        and the discount rather than referring to rows that could be revised. A
        catalogue evolves; what a client agreed to on a given day does not.

        Args:
            price: Price subscribed to, or None on a free subscription
            granted: SubscriptionDiscount benefiting the subscription, or None
            commitment_end_date: End of the commitment the terms are settled against

        Returns:
            Tuple of (amount_due, receipt), both None when nothing is owed.
        """
        if price is None:
            return None, None

        amount_due = price.amount
        discount_receipt = None

        if granted is not None:
            amount_due = discounted_amount(price.amount, granted.value, granted.unit_id)
            discount_receipt = {
                "id": granted.discount_id,
                "value": granted.value,
                "unit": granted.unit_id,
            }

        commitment = price.commitment

        receipt = {
            "settled_at": datetime.now(timezone.utc).isoformat(),
            "plan": {
                "id": price.plan_version.plan_id,
                "version": price.plan_version.version,
                "version_id": price.plan_version_id,
            },
            "price": {
                "id": price.id,
                "amount": price.amount,
                "currency": price.currency_id,
                "period": price.period_id,
            },
            "commitment": {
                "id": price.commitment_id,
                "duration_months": commitment.duration_months if commitment else 0,
                "end_date": commitment_end_date.isoformat() if commitment_end_date else None,
            },
            "discount": discount_receipt,
            "amount_due": amount_due,
        }

        return amount_due, receipt

    @classmethod
    async def settle_terms(
        cls,
        subscription: Subscription,
        price: Optional["LicensePlanVersionPrice"],
        session: AsyncSession
    ) -> Subscription:
        """
        Apply the settled terms to a subscription.

        Called by every path that sets its price: the amount and the receipt are
        written in the same move, from the same inputs, so that they can never
        tell two different stories.

        Args:
            subscription: Subscription to settle
            price: Price subscribed to, or None on a free subscription
            session: Database session

        Returns:
            The updated Subscription, with amount_due and receipt set.
        """
        granted = await cls.get_granted_discount(subscription, session)

        subscription.amount_due, subscription.receipt = cls.settle(
            price, granted, subscription.commitment_end_date
        )

        return subscription

    @classmethod
    async def grant_discount(
        cls,
        subscription: Subscription,
        discount_id: str,
        session: AsyncSession,
        price: Optional["LicensePlanVersionPrice"] = None,
        claimed: bool = False
    ) -> "SubscriptionDiscount":
        """
        Grant a discount to a subscription, and re-settle what is owed.

        The value and its unit are copied onto the granted row rather than read
        back from the discount: a discount revised later must not rewrite what
        this client was granted.

        What entitles the client to it is not checked: eligibility is agreed
        commercially, outside the application. What is enforced here is that the
        discount exists, is still offered, and that the subscription does not
        already have one — discounts do not stack.

        Args:
            subscription: Subscription to grant the discount to
            discount_id: Identifier of the discount granted
            session: Database session
            price: Price the terms are settled against. Pass it when the
                subscription was just placed on it: the relationship still
                resolves to what was stored before, and settling on that would
                owe the wrong amount — nothing at all when the client was free
            claimed: Whether the discount is claimed by the client rather than
                granted by an operator. The identifier travels from the client
                in that case, and a business code is guessable, so only a
                discount meant to be claimed is accepted

        Returns:
            The granted SubscriptionDiscount.

        Raises:
            LysError: DISCOUNT_NOT_FOUND if the discount does not exist
            LysError: DISCOUNT_NOT_AVAILABLE if it is no longer offered
            LysError: DISCOUNT_ALREADY_GRANTED if one is already in place
            LysError: DISCOUNT_WITHOUT_PRICE if the subscription owes nothing
        """
        discount_entity = cls.app_manager.get_entity("license_discount")
        discount = await session.get(discount_entity, discount_id)

        if discount is None:
            raise LysError(
                DISCOUNT_NOT_FOUND,
                f"Discount {discount_id} not found"
            )

        if not discount.enabled:
            raise LysError(
                DISCOUNT_NOT_AVAILABLE,
                f"Discount {discount_id} is no longer offered"
            )

        if claimed and discount.grant_id != MANUAL_GRANT:
            raise LysError(
                DISCOUNT_NOT_AVAILABLE,
                f"Discount {discount_id} cannot be claimed"
            )

        settled_price = price if price is not None else subscription.plan_version_price

        if settled_price is None:
            # A discount on a subscription that owes nothing reduces nothing, and
            # would outlive the free plan it was granted on: no price means no
            # commitment either, so nothing would ever end it.
            raise LysError(
                DISCOUNT_WITHOUT_PRICE,
                f"Subscription {subscription.id} carries no price to discount"
            )

        if await cls.get_granted_discount(subscription, session) is not None:
            raise LysError(
                DISCOUNT_ALREADY_GRANTED,
                f"Subscription {subscription.id} already benefits from a discount"
            )

        granted_entity = cls.app_manager.get_entity("subscription_discount")
        granted = granted_entity(
            subscription_id=subscription.id,
            discount_id=discount.id,
            value=discount.value,
            unit_id=discount.unit_id,
        )
        session.add(granted)

        try:
            # Two requests reaching here at once both passed the check above; the
            # unique constraint is what actually keeps a subscription to one
            # discount, and its failure is that same refusal, not a server error.
            await session.flush()
        except IntegrityError as exc:
            raise LysError(
                DISCOUNT_ALREADY_GRANTED,
                f"Subscription {subscription.id} already benefits from a discount"
            ) from exc

        await cls.settle_terms(subscription, settled_price, session)

        return granted

    @classmethod
    async def revoke_discount(
        cls,
        subscription: Subscription,
        session: AsyncSession
    ) -> bool:
        """
        Remove the discount a subscription benefits from, and re-settle.

        This is what makes a discount end with the commitment it was granted
        against: the renewal removes it, and the subscription renews at the
        catalogue price.

        What is owed goes up, so a provider already collecting must be told: it
        knows nothing of the discount and would keep charging the reduced amount
        indefinitely. Refusing the revocation instead would be worse — a discount
        granted by mistake could never be undone on a collected subscription.

        Returns:
            True if a discount was removed, False if there was none.
        """
        granted = await cls.get_granted_discount(subscription, session)

        if granted is None:
            return False

        await session.delete(granted)
        await session.flush()

        await cls.settle_terms(subscription, subscription.plan_version_price, session)
        await cls._align_provider_collection(subscription, session)

        return True

    @classmethod
    async def _align_provider_collection(
        cls,
        subscription: Subscription,
        session: AsyncSession
    ) -> None:
        """Make the provider collect what the subscription now says is owed.

        Silent when nothing is collected automatically: a manually billed
        subscription is invoiced from the amount recorded here, so there is
        nothing to align.

        Called before the transaction is committed, unlike the renewal task
        which defers its provider calls until after — and this is an exception
        to the rule stated there, not an application of it. A commit failing
        after the call leaves the provider collecting the catalogue price while
        the database still holds the discount: the client is charged **more**
        than what is recorded, which is exactly the direction that rule
        forbids. It is accepted here because the window covers a single act,
        performed by an operator watching its result, and a refusal by the
        provider is logged. Deferring instead would require opening a session
        after the commit, which no path does today.
        """
        price = subscription.plan_version_price

        if (
            price is None
            or subscription.amount_due is None
            or subscription.is_manually_billed
            or not subscription.provider_subscription_id
        ):
            return

        client = subscription.client

        if not client or not client.provider_customer_id:
            logger.error(
                f"Cannot align the collection of subscription {subscription.id}: "
                f"no provider customer for its client"
            )
            return

        currency = price.currency
        checkout_service = cls.app_manager.get_service("mollie_checkout")
        aligned = checkout_service.update_subscription_amount(
            customer_id=client.provider_customer_id,
            provider_subscription_id=subscription.provider_subscription_id,
            currency_id=price.currency_id,
            value=f"{currency.to_major_unit(subscription.amount_due):.{currency.minor_unit}f}",
            interval_months=price.period.interval_months
        )

        if not aligned:
            # The provider refused. What is owed is recorded either way, so the
            # collection has to be corrected by hand: say so rather than let it
            # pass unnoticed.
            logger.error(
                f"Provider refused to align the collection of subscription "
                f"{subscription.id} on {subscription.amount_due}"
            )

    @classmethod
    def _reject_if_provider_collects(cls, subscription: Subscription) -> None:
        """
        Refuse to route a subscription as manual while the provider collects it.

        Switching the mode does not stop the provider subscription, and every
        provider branch is skipped once the mode is manual. The client would
        keep being charged automatically while also being invoiced, and a later
        cancellation would no longer stop the collection.

        Args:
            subscription: Subscription about to be switched to manual billing

        Raises:
            LysError: PROVIDER_SUBSCRIPTION_ACTIVE if a provider subscription is live
        """
        if subscription.provider_subscription_id:
            raise LysError(
                PROVIDER_SUBSCRIPTION_ACTIVE,
                f"Subscription {subscription.id} is still collected by the provider. "
                f"Cancel it first, which stops the collection, before billing manually."
            )

    @classmethod
    async def subscribe_manually(
        cls,
        subscription: Subscription,
        plan_version_price_id: str,
        session: AsyncSession,
        discount_id: str | None = None
    ) -> Subscription:
        """
        Place a subscription on a priced plan, collected outside the application.

        No payment is taken and no provider is called: the amount is invoiced by
        other means. The price carries the version, the periodicity, the currency
        and the commitment agreed to, so entitlements, commitment and renewal
        behave as they would under provider billing.

        This is a commercial act performed by an administrator on behalf of a
        client, never by the client themselves. A free plan has no price and is
        therefore reached through cancellation, not through this method.

        Args:
            subscription: Subscription to place on the plan
            plan_version_price_id: Price agreed to, which identifies the plan
                version and the terms
            session: Database session
            discount_id: Discount granted in the same move, if any

        Returns:
            The updated Subscription

        Raises:
            LysError: PROVIDER_SUBSCRIPTION_ACTIVE if the provider still collects
            LysError: PLAN_VERSION_PRICE_NOT_FOUND if the price does not exist
        """
        cls._reject_if_provider_collects(subscription)

        price_service = cls.app_manager.get_service("license_plan_version_price")
        price = await price_service.get_by_id(plan_version_price_id, session)

        if price is None:
            raise LysError(
                PLAN_VERSION_PRICE_NOT_FOUND,
                f"Plan version price {plan_version_price_id} not found"
            )

        now = datetime.now(timezone.utc)

        subscription.billing_mode_id = MANUAL_BILLING
        subscription.plan_version_id = price.plan_version_id
        subscription.plan_version_price_id = price.id
        subscription.pending_plan_version_id = None
        subscription.canceled_at = None
        subscription.current_period_start = now
        subscription.current_period_end = calculate_period_end(
            now, price.period.interval_months
        )
        # Co-termination: a commitment already running is never restarted by a
        # change of plan. The client owes more from now on, but changing plan
        # must not lock them in for longer than what they agreed to. A new term
        # only starts when none is running.
        if not subscription.is_committed:
            subscription.commitment_end_date = (
                calculate_period_end(now, price.commitment.duration_months)
                if price.commitment.is_binding else None
            )

        if discount_id:
            # Granting settles the terms itself, and refuses a second discount.
            # The price is handed over: the subscription was just placed on it,
            # so its relationship still resolves to the previous one — to
            # nothing at all when the client was on the free plan
            await cls.grant_discount(subscription, discount_id, session, price=price)
        else:
            await cls.settle_terms(subscription, price, session)

        return subscription

    @classmethod
    async def set_billing_mode(
        cls,
        subscription: Subscription,
        billing_mode_id: str,
        session: AsyncSession
    ) -> Subscription:
        """
        Change how a subscription is collected.

        This is the migration path between the two modes: an application
        adopting a payment provider releases its manually billed clients one by
        one, so that they can subscribe through checkout.

        Switching to provider billing does not create anything at the provider;
        it only stops routing the subscription as manual. Collection starts when
        the client subscribes.

        Args:
            subscription: Subscription whose collection mode changes
            billing_mode_id: Target billing mode
            session: Database session

        Returns:
            The updated Subscription

        Raises:
            LysError: UNKNOWN_BILLING_MODE if the mode does not exist or is disabled
            LysError: PROVIDER_SUBSCRIPTION_ACTIVE if switching to manual while
                the provider still collects
        """
        if billing_mode_id == MANUAL_BILLING:
            cls._reject_if_provider_collects(subscription)

        billing_mode_service = cls.app_manager.get_service("license_billing_mode")
        billing_mode = await billing_mode_service.get_by_id(billing_mode_id, session)

        # A mode with no service able to honour it would silently collect
        # nothing, so an unknown or withdrawn mode is refused outright
        if billing_mode is None or not billing_mode.enabled:
            raise LysError(
                UNKNOWN_BILLING_MODE,
                f"Billing mode {billing_mode_id} does not exist or is disabled"
            )

        subscription.billing_mode_id = billing_mode_id
        return subscription

    # =========================================================================
    # Subscription Management (with payment provider integration)
    # =========================================================================

    @classmethod
    async def subscribe_to_plan(
        cls,
        client_id: str,
        plan_version_id: str,
        billing_period: str,
        success_url: str,
        webhook_url: str,
        session: AsyncSession,
        currency_id: str = DEFAULT_CURRENCY,
        commitment_id: str = NO_COMMITMENT,
        discount_id: str | None = None
    ) -> SubscribeToPlanResult:
        """
        Subscribe a client to a plan, handling all cases automatically.

        Cases handled:
        - No subscription or FREE plan: Create new paid subscription
        - Upgrade: Calculate prorata and create payment
        - Downgrade: Schedule change for end of billing period
        - Same plan: Return error

        Args:
            client_id: Client ID
            plan_version_id: Target plan version ID
            billing_period: Price period ID (e.g., "MONTHLY")
            success_url: URL to redirect after payment
            webhook_url: URL for payment provider webhooks
            session: Database session
            currency_id: Currency the subscription is billed in
            commitment_id: Contractual commitment subscribed to
            discount_id: Discount claimed at checkout, granted once the payment
                is confirmed. Only honoured when the subscription is taken, not
                when an existing one is upgraded: a discount already granted
                follows the client to their new plan on its own, and claiming a
                second one at that point would stack

        Returns:
            SubscribeToPlanResult with checkout_url or effective_date
        """
        plan_version_entity = cls.app_manager.get_entity("license_plan_version")
        client_entity = cls.app_manager.get_entity("client")

        # Get target plan version
        new_version = await session.get(plan_version_entity, plan_version_id)
        if not new_version:
            return SubscribeToPlanResult(success=False, error=PLAN_NOT_FOUND_ERROR)

        # Get client
        client = await session.get(client_entity, client_id)
        if not client:
            return SubscribeToPlanResult(success=False, error="CLIENT_NOT_FOUND")

        # Get current subscription
        subscription = await cls.get_client_subscription(client_id, session)

        # Determine new plan price. A paid version that carries no price for the
        # requested terms must be rejected here: leaving it at 0 would make both
        # sides of the comparison below equal, route the request to the downgrade
        # branch, and schedule the plan change without any payment.
        new_price_entity = new_version.price_for(billing_period, currency_id, commitment_id)
        if new_price_entity is None and not new_version.is_free:
            logger.warning(
                f"Client {client_id} requested plan version {plan_version_id} "
                f"for {billing_period}/{currency_id}/{commitment_id}, which is not priced"
            )
            return SubscribeToPlanResult(success=False, error=PLAN_NOT_PRICED_ERROR)

        new_price = new_price_entity.amount if new_price_entity else 0

        # Case 1: nothing is being collected yet, so the change starts a
        # collection rather than altering one. A manually billed client reaches
        # checkout through here: the payment is what moves them to the provider,
        # so that the recorded mode never claims a collection that has not
        # started. See LicenseBillingMode for the migration it belongs to.
        if not subscription or not subscription.provider_subscription_id:
            return await cls._handle_new_subscription(
                client=client,
                plan_version_id=plan_version_id,
                billing_period=billing_period,
                success_url=success_url,
                webhook_url=webhook_url,
                session=session,
                currency_id=currency_id,
                commitment_id=commitment_id,
                discount_id=discount_id
            )

        # Changing the periodicity or the currency of a running subscription is
        # not supported: the prorata below compares two amounts assumed to be on
        # the same cadence, so mixing a monthly and a yearly price would bill a
        # meaningless amount. Refuse rather than charge something wrong.
        current_terms = subscription.plan_version_price
        if current_terms is not None and (
            current_terms.period_id != billing_period
            or current_terms.currency_id != currency_id
            or current_terms.commitment_id != commitment_id
        ):
            return SubscribeToPlanResult(success=False, error=BILLING_TERMS_CHANGE_ERROR)

        # Get current plan version and price
        current_version = await session.get(plan_version_entity, subscription.plan_version_id)
        current_price_entity = current_version.price_for(
            billing_period, currency_id, commitment_id
        )
        current_price = current_price_entity.amount if current_price_entity else 0

        # Case 2: Same plan
        if subscription.plan_version_id == plan_version_id:
            return SubscribeToPlanResult(success=False, error=SAME_PLAN_ERROR)

        # Case 3: Upgrade
        if is_upgrade(current_price, new_price):
            return await cls._handle_upgrade(
                client=client,
                subscription=subscription,
                new_version=new_version,
                current_price=current_price,
                new_price=new_price,
                billing_period=billing_period,
                success_url=success_url,
                webhook_url=webhook_url,
                session=session,
                currency_id=currency_id,
                commitment_id=commitment_id
            )

        # Case 4: Downgrade. Under commitment it only takes effect at the term,
        # and only if the notice deadline has not passed. Upgrades stay allowed
        # throughout, since they raise the amount due.
        if not subscription.is_within_notice_period:
            return SubscribeToPlanResult(success=False, error=NOTICE_PERIOD_EXPIRED_ERROR)

        return await cls._handle_downgrade(
            subscription=subscription,
            plan_version_id=plan_version_id,
            session=session
        )

    @classmethod
    async def _handle_new_subscription(
        cls,
        client,
        plan_version_id: str,
        billing_period: str,
        success_url: str,
        webhook_url: str,
        session: AsyncSession,
        currency_id: str = DEFAULT_CURRENCY,
        commitment_id: str = NO_COMMITMENT,
        discount_id: str | None = None
    ) -> SubscribeToPlanResult:
        """Handle new subscription or upgrade from FREE plan."""
        checkout_service = cls.app_manager.get_service("mollie_checkout")
        checkout_url = await checkout_service.create_payment(
            client_id=client.id,
            plan_version_id=plan_version_id,
            billing_period=billing_period,
            redirect_url=success_url,
            webhook_url=webhook_url,
            session=session,
            currency_id=currency_id,
            commitment_id=commitment_id,
            discount_id=discount_id
        )

        if not checkout_url:
            return SubscribeToPlanResult(success=False, error=CHECKOUT_SESSION_FAILED_ERROR)

        return SubscribeToPlanResult(success=True, checkout_url=checkout_url)

    @classmethod
    async def _handle_upgrade(
        cls,
        client,
        subscription,
        new_version,
        current_price: int,
        new_price: int,
        billing_period: str,
        success_url: str,
        webhook_url: str,
        session: AsyncSession,
        currency_id: str = DEFAULT_CURRENCY,
        commitment_id: str = NO_COMMITMENT
    ) -> SubscribeToPlanResult:
        """Handle upgrade with prorata calculation."""
        # No billing period info - treat as new subscription
        if not subscription.current_period_start or not subscription.current_period_end:
            return await cls._handle_new_subscription(
                client=client,
                plan_version_id=new_version.id,
                billing_period=billing_period,
                success_url=success_url,
                webhook_url=webhook_url,
                session=session,
                currency_id=currency_id,
                commitment_id=commitment_id
            )

        # The prorata compares catalogue prices, not what the client owes: a
        # discount is a reduction on a period, and spreading it over the days
        # remaining of a period already paid for would credit it twice. The
        # discount resumes on the next full period, which settle_terms restates.
        prorata_amount = calculate_prorata(
            old_price=current_price,
            new_price=new_price,
            current_period_start=subscription.current_period_start,
            current_period_end=subscription.current_period_end
        )

        # No prorata needed (period almost over) - apply immediately
        if prorata_amount <= 0:
            new_price_entity = new_version.price_for(
                billing_period, currency_id, commitment_id
            )

            subscription.plan_version_id = new_version.id
            subscription.pending_plan_version_id = None
            subscription.plan_version_price_id = new_price_entity.id

            # The plan changed without a payment, so nothing else would restate
            # what is owed. Any discount in place is kept: it was granted against
            # the commitment, which the upgrade does not end.
            await cls.settle_terms(subscription, new_price_entity, session)

            # No payment is made here, so nothing else would align the recurring
            # collection with the plan now granted
            if subscription.provider_subscription_id and client.provider_customer_id:
                checkout_service = cls.app_manager.get_service("mollie_checkout")
                currency = new_price_entity.currency
                checkout_service.update_subscription_amount(
                    customer_id=client.provider_customer_id,
                    provider_subscription_id=subscription.provider_subscription_id,
                    currency_id=new_price_entity.currency_id,
                    # What is owed, not what the catalogue asks: the discount
                    # follows the upgrade, so the collection must follow it too
                    value=f"{currency.to_major_unit(subscription.amount_due):.{currency.minor_unit}f}",
                    interval_months=new_price_entity.period.interval_months
                )

            return SubscribeToPlanResult(success=True, prorata_amount=0)

        # Create prorata payment
        mollie = get_mollie_client()
        if not mollie:
            return SubscribeToPlanResult(success=False, error=CHECKOUT_SESSION_FAILED_ERROR)

        currency = await cls.app_manager.get_service("license_currency").get_by_id(
            currency_id, session
        )

        try:
            payment_data = {
                "amount": {
                    "currency": currency_id,
                    "value": f"{currency.to_major_unit(prorata_amount):.{currency.minor_unit}f}"
                },
                "description": f"Upgrade to {new_version.plan_id} (prorata)",
                "redirectUrl": success_url,
                "webhookUrl": webhook_url,
                "metadata": {
                    "client_id": client.id,
                    "plan_version_id": new_version.id,
                    "billing_period": billing_period,
                    "currency_id": currency_id,
                    "commitment_id": commitment_id,
                    "is_prorata": True
                }
            }

            if client.provider_customer_id:
                payment_data["customerId"] = client.provider_customer_id

            payment = mollie.payments.create(payment_data)

            return SubscribeToPlanResult(
                success=True,
                checkout_url=payment.checkout_url,
                prorata_amount=prorata_amount
            )

        except Exception as e:
            logger.error(f"Error creating prorata payment: {e}")
            return SubscribeToPlanResult(success=False, error=CHECKOUT_SESSION_FAILED_ERROR)

    @classmethod
    async def _handle_downgrade(
        cls,
        subscription,
        plan_version_id: str,
        session: AsyncSession
    ) -> SubscribeToPlanResult:
        """
        Schedule a downgrade for the end of the current period.

        The client keeps the plan already paid for until the period ends, so the
        provider subscription is only touched when the target plan is free: in
        that case collection must stop, and nothing else would stop it.

        For a cheaper paid plan the amount is realigned when the change is
        applied, by apply_pending_plan_changes, since until then the client is
        still on the current plan and owes its price.

        A committed subscription is left alone entirely: the client owes every
        remaining period until the commitment ends, so collection must continue
        and is only stopped by apply_pending_plan_changes at the term.

        Args:
            subscription: The subscription to downgrade
            plan_version_id: Target plan version
            session: Database session

        Returns:
            SubscribeToPlanResult with the effective date
        """
        subscription.pending_plan_version_id = plan_version_id

        plan_version_entity = cls.app_manager.get_entity("license_plan_version")
        target_version = await session.get(plan_version_entity, plan_version_id)

        if (
            target_version is not None
            and target_version.is_free
            and subscription.provider_subscription_id
            and not subscription.is_manually_billed
            and not subscription.is_committed
        ):
            client_entity = cls.app_manager.get_entity("client")
            client = await session.get(client_entity, subscription.client_id)

            if client and client.provider_customer_id:
                checkout_service = cls.app_manager.get_service("mollie_checkout")
                canceled = checkout_service.cancel_provider_subscription(
                    customer_id=client.provider_customer_id,
                    provider_subscription_id=subscription.provider_subscription_id
                )
                if canceled:
                    subscription.canceled_at = datetime.now(timezone.utc)
                else:
                    logger.error(
                        f"Downgrade to a free plan for subscription {subscription.id} could not "
                        f"stop the provider subscription; the client would keep being charged"
                    )

        return SubscribeToPlanResult(
            success=True,
            effective_date=subscription.effective_change_date
        )

    @classmethod
    async def cancel(
        cls,
        client_id: str,
        session: AsyncSession
    ) -> CancelSubscriptionResult:
        """
        Cancel a subscription.

        The cancellation takes effect at the end of the current billing period,
        or at the end of the commitment when the client is still bound. The
        client keeps access until then, then downgrades to FREE plan.

        It is refused once the notice deadline of a committed subscription has
        passed: the commitment is then renewed, and the denunciation has to be
        requested again during the next notice window.

        A committed subscription keeps being collected until the term: the
        provider subscription is stopped by apply_pending_plan_changes on the
        effective date, not here.

        Args:
            client_id: Client ID
            session: Database session

        Returns:
            CancelSubscriptionResult with effective_date
        """
        client_entity = cls.app_manager.get_entity("client")

        # Get client
        client = await session.get(client_entity, client_id)
        if not client:
            return CancelSubscriptionResult(success=False, error="CLIENT_NOT_FOUND")

        # Get subscription
        subscription = await cls.get_client_subscription(client_id, session)
        if not subscription:
            return CancelSubscriptionResult(success=False, error=NO_ACTIVE_SUBSCRIPTION_ERROR)

        if not subscription.is_manually_billed and not subscription.provider_subscription_id:
            return CancelSubscriptionResult(success=False, error=NO_PROVIDER_SUBSCRIPTION_ERROR)

        # Past the notice deadline the commitment is tacitly renewed, so the
        # denunciation can only be received during the next notice window
        if not subscription.is_within_notice_period:
            return CancelSubscriptionResult(success=False, error=NOTICE_PERIOD_EXPIRED_ERROR)

        if not subscription.is_manually_billed and not client.provider_customer_id:
            return CancelSubscriptionResult(success=False, error=CANCEL_SUBSCRIPTION_FAILED_ERROR)

        # Get FREE plan version to downgrade to
        plan_version_service = cls.app_manager.get_service("license_plan_version")
        free_version = await plan_version_service.get_current_version(FREE_PLAN, session)
        if not free_version:
            logger.error(f"No enabled version on the {FREE_PLAN} plan, cannot cancel")
            return CancelSubscriptionResult(success=False, error=CANCEL_SUBSCRIPTION_FAILED_ERROR)

        # A cancellation is a downgrade to the free plan: same scheduling, same
        # handling of the provider subscription
        was_committed = subscription.is_committed
        await cls._handle_downgrade(
            subscription=subscription,
            plan_version_id=free_version.id,
            session=session
        )

        if not was_committed and not subscription.is_manually_billed \
                and subscription.canceled_at is None:
            # Collection was meant to stop now but could not, so the client would
            # keep being charged; report the failure rather than a false success.
            # A committed subscription is expected to keep being charged until
            # the term, so it is not concerned.
            return CancelSubscriptionResult(success=False, error=CANCEL_SUBSCRIPTION_FAILED_ERROR)

        # Trigger subscription canceled event (notification + email)
        client_name = client.name if client else None
        plan_name = None
        if subscription.plan_version and subscription.plan_version.plan:
            plan_name = subscription.plan_version.plan.id
        change_date = subscription.effective_change_date
        effective_date = change_date.isoformat() if change_date else None

        trigger_event.delay(
            event_type=SUBSCRIPTION_CANCELED,
            user_id=None,  # No specific user, sent to LICENSE_ADMIN_ROLE
            email_context={
                "client_name": client_name,
                "plan_name": plan_name,
                "effective_date": effective_date,
                "front_url": cls.app_manager.settings.front_url,
            },
            notification_data={
                "client_name": client_name,
                "plan_name": plan_name,
                "effective_date": effective_date,
            },
            organization_data={"client_ids": [client_id]},
        )

        return CancelSubscriptionResult(
            success=True,
            effective_date=subscription.effective_change_date
        )