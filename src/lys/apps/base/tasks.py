"""
Celery tasks for base app.

Tasks defined here can be executed by Celery workers
and scheduled via Celery Beat.
"""
import logging

from celery import shared_task, current_app

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_pending_email(self, emailing_id: str):
    """
    Send a single pending email.

    This task sends an email by its ID.
    Successfully sent emails are marked as SENT.
    Failed emails are marked as ERROR with error details.

    Args:
        emailing_id: The ID of the emailing to send

    Returns:
        bool: True if sent successfully, False otherwise

    Example:
        # Called from BackgroundTask after DB commit
        # background_tasks.add_task(lambda: send_pending_email.delay(emailing_id))
    """
    # Access app_manager from celery app
    app_manager = current_app.app_manager

    # Get emailing service from app_manager
    emailing_service = app_manager.get_service("emailing")

    try:
        # Call send_email service method
        emailing_service.send_email(emailing_id)
        logger.info(f"Email {emailing_id} sent successfully")
        return True

    except Exception as e:
        logger.error(f"Failed to send email {emailing_id}: {e}")
        raise self.retry(exc=e)

