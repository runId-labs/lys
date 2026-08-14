"""
Celery tasks for the licensing module.

Tasks:
- apply_pending_plan_changes: Daily task to apply scheduled downgrades
"""

import logging
from datetime import datetime, timezone

from celery import shared_task, current_app
from sqlalchemy import and_, or_, select

from lys.apps.licensing.modules.subscription.prorata import calculate_period_end

logger = logging.getLogger(__name__)


def _renew_commitment(subscription) -> int:
    """
    Tacitly renew a commitment that reached its term undenounced.

    Business practice rarely renews for the initial duration, so the renewed
    span comes from the commitment itself. A commitment with no renewal span
    simply ends, and the client becomes free to leave at any period end.

    Args:
        subscription: Subscription whose commitment term has passed

    Returns:
        1 if the commitment was renewed, 0 if it ended
    """
    price = subscription.plan_version_price
    commitment = price.commitment if price is not None else None

    if commitment is None or not commitment.is_renewable:
        subscription.commitment_end_date = None
        logger.info(
            f"Commitment of subscription {subscription.id} ended and was not renewed"
        )
        return 0

    subscription.commitment_end_date = calculate_period_end(
        subscription.commitment_end_date, commitment.renewal_months
    )
    logger.info(
        f"Commitment of subscription {subscription.id} tacitly renewed for "
        f"{commitment.renewal_months} months, until {subscription.commitment_end_date}"
    )
    return 1


@shared_task
def apply_pending_plan_changes():
    """
    Apply pending plan changes whose billing period has ended.

    This task should be scheduled to run daily (e.g., via Celery Beat).

    It first tacitly renews the commitments that reached their term without
    being denounced, then applies the pending changes that are now due: at the
    commitment term when the subscription is committed, at the end of the
    billing period otherwise.

    Returns:
        int: Number of applied changes
    """
    app_manager = current_app.app_manager
    subscription_entity = app_manager.get_entity("subscription")
    plan_version_entity = app_manager.get_entity("license_plan_version")

    now = datetime.now(timezone.utc)
    applied_count = 0
    renewed_count = 0
    provider_updates = []
    provider_cancellations = []

    with app_manager.database.get_sync_session() as session:
        # Renew the commitments that reached their term without being denounced.
        # A denounced subscription carries a pending change, so this selection is
        # disjoint from the one below and the two cannot conflict.
        renewal_stmt = select(subscription_entity).where(
            subscription_entity.pending_plan_version_id.is_(None),
            subscription_entity.commitment_end_date.isnot(None),
            subscription_entity.commitment_end_date <= now
        )
        for subscription in session.execute(renewal_stmt).scalars().all():
            try:
                renewed_count += _renew_commitment(subscription)
            except Exception as e:
                logger.error(
                    f"Error renewing commitment for subscription {subscription.id}: {e}"
                )

        # Find subscriptions with pending changes that are now due. A commitment
        # outlives the billing period, so it drives the date when it is set.
        stmt = select(subscription_entity).where(
            subscription_entity.pending_plan_version_id.isnot(None),
            or_(
                and_(
                    subscription_entity.commitment_end_date.isnot(None),
                    subscription_entity.commitment_end_date <= now
                ),
                and_(
                    subscription_entity.commitment_end_date.is_(None),
                    subscription_entity.current_period_end <= now
                )
            )
        )
        result = session.execute(stmt)
        subscriptions = result.scalars().all()

        for subscription in subscriptions:
            try:
                old_plan_version_id = subscription.plan_version_id
                new_plan_version_id = subscription.pending_plan_version_id

                # Resolve the price of the new plan on the same terms the client
                # subscribed to, before the current price reference is replaced
                current_price = subscription.plan_version_price
                new_price = None
                new_plan_version = session.get(plan_version_entity, new_plan_version_id)

                if current_price is not None and new_plan_version is not None:
                    new_price = new_plan_version.price_for(
                        current_price.period_id,
                        current_price.currency_id,
                        current_price.commitment_id
                    )

                    if new_price is None and not new_plan_version.is_free:
                        # Applying the change would grant a paid plan we cannot
                        # bill, while the provider keeps collecting the previous
                        # amount. Leave the change pending so it is retried once
                        # the missing price is published.
                        logger.error(
                            f"Cannot apply pending change for subscription {subscription.id}: "
                            f"plan version {new_plan_version_id} has no price for "
                            f"{current_price.period_id}/{current_price.currency_id}"
                        )
                        continue

                # A commitment that reached its term is over, whatever happens next
                subscription.commitment_end_date = None

                # Apply the pending change
                subscription.plan_version_id = new_plan_version_id
                subscription.pending_plan_version_id = None
                subscription.plan_version_price_id = new_price.id if new_price else None

                if subscription.canceled_at is not None:
                    # The provider subscription was already stopped when the change
                    # was requested, on an uncommitted subscription
                    subscription.provider_subscription_id = None
                    subscription.canceled_at = None
                elif new_price is None and subscription.provider_subscription_id:
                    # Committed subscription reaching its term on a free plan:
                    # collection ran until now and must be stopped at this point
                    provider_cancellations.append({
                        "subscription_id": subscription.id,
                        "customer_id": subscription.client.provider_customer_id
                        if subscription.client else None,
                        "provider_subscription_id": subscription.provider_subscription_id,
                    })
                    subscription.provider_subscription_id = None
                elif new_price is not None and subscription.provider_subscription_id:
                    # Downgrade to a cheaper paid plan: the new price applies from
                    # now on, so the recurring collection must follow. Deferred
                    # until the database is committed, so that a failed commit
                    # cannot leave the provider charging an amount we did not record.
                    client = subscription.client
                    if client and client.provider_customer_id:
                        provider_updates.append({
                            "subscription_id": subscription.id,
                            "customer_id": client.provider_customer_id,
                            "provider_subscription_id": subscription.provider_subscription_id,
                            "currency_id": new_price.currency_id,
                            "value": new_price.major_unit_value,
                            "interval_months": new_price.period.interval_months,
                        })

                # Execute downgrade actions for quota rules
                checker_service = app_manager.get_service("license_checker")
                downgrade_results = checker_service.execute_downgrade(
                    subscription.client_id, new_plan_version_id, session
                )
                if downgrade_results:
                    logger.info(
                        f"Downgrade results for subscription {subscription.id}: "
                        f"{downgrade_results}"
                    )

                logger.info(
                    f"Applied pending plan change for subscription {subscription.id}: "
                    f"{old_plan_version_id} -> {new_plan_version_id}"
                )
                applied_count += 1

            except Exception as e:
                logger.error(
                    f"Error applying pending change for subscription {subscription.id}: {e}"
                )

        session.commit()

    # The database is the reference: align the provider only once the changes
    # are durable. A failure here leaves a recorded price the provider has not
    # caught up with, which is recoverable; the reverse would not be.
    if provider_updates or provider_cancellations:
        checkout_service = app_manager.get_service("mollie_checkout")

        for cancellation in provider_cancellations:
            if not cancellation["customer_id"]:
                logger.error(
                    f"Subscription {cancellation['subscription_id']} reached its commitment term "
                    f"but has no provider customer; collection may still be running"
                )
                continue

            stopped = checkout_service.cancel_provider_subscription(
                customer_id=cancellation["customer_id"],
                provider_subscription_id=cancellation["provider_subscription_id"]
            )
            if not stopped:
                logger.error(
                    f"Subscription {cancellation['subscription_id']} reached its commitment term "
                    f"but provider subscription {cancellation['provider_subscription_id']} "
                    f"could not be stopped; the client would keep being charged"
                )

        for update in provider_updates:
            updated = checkout_service.update_subscription_amount(
                customer_id=update["customer_id"],
                provider_subscription_id=update["provider_subscription_id"],
                currency_id=update["currency_id"],
                value=update["value"],
                interval_months=update["interval_months"]
            )
            if not updated:
                logger.error(
                    f"Subscription {update['subscription_id']} moved to a new price but the "
                    f"provider subscription {update['provider_subscription_id']} still charges "
                    f"the previous amount"
                )

    logger.info(
        f"Applied {applied_count} pending plan changes and renewed {renewed_count} commitments"
    )
    return applied_count