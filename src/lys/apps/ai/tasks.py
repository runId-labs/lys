"""
Celery tasks for AI app.

Tasks:
- summarize_conversation: Fill a pending conversation-compaction summary off the request path
"""

import logging

from celery import shared_task, current_app

logger = logging.getLogger(__name__)


@shared_task
def summarize_conversation(summary_id: str):
    """
    Fill a pending conversation-compaction summary row in the background.

    A pending AIConversationSummary row (completed=False) is created at enqueue time with
    its boundary message set; this task summarizes the messages from the previous summary
    boundary up to this row's boundary, merges them with the previous summary, and marks
    the row completed. On failure the pending row is deleted so the next trigger re-enqueues
    (keeps the completed=False concurrency guard from getting stuck).

    Args:
        summary_id: ID of the pending AIConversationSummary row to fill.
    """
    app_manager = current_app.app_manager
    conversation_service = app_manager.get_service("ai_conversation")
    ai_service = app_manager.get_service("ai")

    try:
        with app_manager.database.get_sync_session() as session:
            conversation_service.fill_summary(session, ai_service, summary_id)
            session.commit()
        logger.info(f"Filled conversation summary {summary_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to fill conversation summary {summary_id}: {e}")
        try:
            with app_manager.database.get_sync_session() as session:
                conversation_service.discard_pending_summary_sync(session, summary_id)
                session.commit()
        except Exception as ce:
            logger.error(f"Failed to discard pending summary {summary_id}: {ce}")
        return False
