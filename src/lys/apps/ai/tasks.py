"""
Celery tasks for AI app.

Tasks:
- cleanup_old_ai_conversations: Daily task to delete old conversation history
"""

import asyncio
import logging

from celery import shared_task, current_app

logger = logging.getLogger(__name__)


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
    from lys.core.managers.database import DatabaseManager

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
        logger.info(f"Deleted {count} old AI conversations (older than {hours} hours)")
        return count

    except Exception as e:
        logger.error(f"Failed to cleanup AI conversations: {e}")
        return 0