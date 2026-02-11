"""
Celery tasks for the event system.

Provides the unified trigger_event task that handles both
emails and notifications based on event configuration.
"""
import logging

from celery import shared_task, current_app

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def trigger_event(
    self,
    event_type: str,
    user_id: str,
    emailing_id: str | None = None,
    email_context: dict | None = None,
    notification_data: dict | None = None,
    organization_data: dict | None = None,
    additional_user_ids: list[str] | None = None,
):
    """
    Unified event trigger for emails and notifications.

    The event_type key is used as:
    - EmailingType.id for emails
    - NotificationType.id for notifications

    Email handling:
    - If emailing_id is provided: send directly (critical, no config/preference check)
    - If no emailing_id: dispatch via EmailingBatchService to all resolved recipients
      (role-based + org-scoped), with per-recipient preference filtering

    Notification handling:
    - Dispatched via NotificationBatchService to all resolved recipients
    - User preferences are checked per-recipient inside dispatch_sync

    Args:
        event_type: Event type key (e.g., "USER_INVITED", "FINANCIAL_IMPORT_COMPLETED")
        user_id: The user (recipient for emails, triggering user for notifications)
        emailing_id: Pre-created email ID (critical email, always sent)
        email_context: Context for creating email on the fly
        notification_data: Data payload for notification
        organization_data: Organization scoping (e.g., {"client_ids": [...]})
        additional_user_ids: Extra users to notify beyond role-based recipients

    Returns:
        dict: Summary of actions taken
    """
    app_manager = current_app.app_manager

    # Get config from EventService (supports override chain)
    event_service = app_manager.get_service("event")
    channels = event_service.get_channels()

    config = channels.get(event_type)
    if not config:
        logger.error(f"Unknown event type: {event_type}")
        raise ValueError(f"Unknown event type: {event_type}")

    result = {"event_type": event_type, "email_sent": False, "notification_sent": False}

    with app_manager.database.get_sync_session() as session:
        # Handle email
        if emailing_id:
            # Critical email (pre-created), send directly without any check
            try:
                emailing_service = app_manager.get_service("emailing")
                emailing_service.send_email(emailing_id)
                result["email_sent"] = True
                logger.info(f"Event {event_type}: sent critical email {emailing_id}")
            except Exception as e:
                logger.error(f"Event {event_type}: failed to send email {emailing_id}: {e}")
                raise self.retry(exc=e)
        elif config.get("email", False):
            # Non-critical email, dispatch to all resolved recipients
            try:
                emailing_batch_service = app_manager.get_service("emailing_batch")

                # Callback to check per-recipient preference
                def should_send_email(recipient_user_id: str) -> bool:
                    return event_service.should_send(
                        recipient_user_id, event_type, "email", session
                    )

                emailing_ids = emailing_batch_service.dispatch_sync(
                    session=session,
                    type_id=event_type,
                    email_context=email_context,
                    triggered_by_user_id=user_id,
                    additional_user_ids=additional_user_ids,
                    organization_data=organization_data,
                    should_send_fn=should_send_email,
                )
                if emailing_ids:
                    result["email_sent"] = True
                    logger.info(f"Event {event_type}: dispatched {len(emailing_ids)} email(s)")
            except Exception as e:
                logger.error(f"Event {event_type}: failed to dispatch emails: {e}")
                raise self.retry(exc=e)

        # Handle notification
        if config.get("notification", False):
            try:
                notification_batch_service = app_manager.get_service("notification_batch")

                # Callback to check per-recipient preference
                def should_send_notification(recipient_user_id: str) -> bool:
                    return event_service.should_send(
                        recipient_user_id, event_type, "notification", session
                    )

                notification_batch_service.dispatch_sync(
                    session=session,
                    type_id=event_type,
                    data=notification_data,
                    triggered_by_user_id=user_id,
                    additional_user_ids=additional_user_ids,
                    organization_data=organization_data,
                    should_send_fn=should_send_notification,
                )
                result["notification_sent"] = True
                logger.info(f"Event {event_type}: notification dispatched")
            except Exception as e:
                logger.error(f"Event {event_type}: failed to dispatch notification: {e}")
                raise self.retry(exc=e)

        session.commit()

    return result