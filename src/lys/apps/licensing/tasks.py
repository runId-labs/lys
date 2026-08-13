"""
Celery tasks for the licensing module.

Tasks:
- apply_pending_plan_changes: Daily task to apply scheduled downgrades
"""

import logging
from datetime import datetime, timezone

from celery import shared_task, current_app
from sqlalchemy import select

logger = logging.getLogger(__name__)


@shared_task
def apply_pending_plan_changes():
    """
    Apply pending plan changes whose billing period has ended.

    This task should be scheduled to run daily (e.g., via Celery Beat).
    It finds all subscriptions with:
    - pending_plan_version_id set (scheduled downgrade/cancellation)
    - current_period_end <= now (period has ended)

    And applies the pending plan change.

    Returns:
        int: Number of applied changes
    """
    app_manager = current_app.app_manager
    subscription_entity = app_manager.get_entity("subscription")
    plan_version_entity = app_manager.get_entity("license_plan_version")

    now = datetime.now(timezone.utc)
    applied_count = 0
    provider_updates = []

    with app_manager.database.get_sync_session() as session:
        # Find subscriptions with pending changes whose period has ended
        stmt = select(subscription_entity).where(
            subscription_entity.pending_plan_version_id.isnot(None),
            subscription_entity.current_period_end <= now
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
                        current_price.period_id, current_price.currency_id
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

                # Apply the pending change
                subscription.plan_version_id = new_plan_version_id
                subscription.pending_plan_version_id = None
                subscription.plan_version_price_id = new_price.id if new_price else None

                # Clear provider subscription ID if canceled
                # (the provider subscription was already stopped when the
                # cancellation or the downgrade to a free plan was requested)
                if subscription.canceled_at is not None:
                    subscription.provider_subscription_id = None
                    subscription.canceled_at = None
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
    if provider_updates:
        checkout_service = app_manager.get_service("mollie_checkout")
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

    logger.info(f"Applied {applied_count} pending plan changes")
    return applied_count