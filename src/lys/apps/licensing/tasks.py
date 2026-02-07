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

    now = datetime.now(timezone.utc)
    applied_count = 0

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

                # Apply the pending change
                subscription.plan_version_id = new_plan_version_id
                subscription.pending_plan_version_id = None

                # Clear provider subscription ID if canceled
                # (subscription was already canceled on Mollie)
                if subscription.canceled_at is not None:
                    subscription.provider_subscription_id = None
                    subscription.canceled_at = None

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

    logger.info(f"Applied {applied_count} pending plan changes")
    return applied_count