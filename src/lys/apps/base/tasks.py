"""
Celery tasks for base app.

Tasks defined here can be executed by Celery workers
and scheduled via Celery Beat.
"""

from celery import shared_task, current_app


@shared_task
def send_pending_email(emailing_id: str):
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
        print(f"Email {emailing_id} sent successfully")
        return True

    except Exception as e:
        # Log error - status already updated by send_email
        print(f"Failed to send email {emailing_id}: {e}")
        return False


@shared_task
def cleanup_old_ai_conversations(hours: int = 24):
    """
    Delete AI conversations older than specified hours.

    This task should be scheduled via Celery Beat to run periodically
    (e.g., daily) to clean up old conversation history.

    Args:
        hours: Age threshold in hours (default: 24)

    Returns:
        int: Number of deleted conversations
    """
    import asyncio
    from lys.core.databases import DatabaseManager

    app_manager = current_app.app_manager
    conversation_service = app_manager.get_service("ai_conversation")

    async def _cleanup():
        async with DatabaseManager.async_session() as session:
            count = await conversation_service.delete_old_conversations(
                session=session,
                hours=hours
            )
            await session.commit()
            return count

    try:
        count = asyncio.run(_cleanup())
        print(f"Deleted {count} old AI conversations (older than {hours} hours)")
        return count

    except Exception as e:
        print(f"Failed to cleanup AI conversations: {e}")
        return 0