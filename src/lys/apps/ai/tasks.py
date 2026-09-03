"""
Celery tasks for AI app.

Tasks:
- summarize_conversation: Fill a pending conversation-compaction summary off the request path
- generate_conversation_title: Title a conversation from its opening message off the request path
- index_pending_messages: Fill the search vectors left empty, on a schedule
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


@shared_task
def generate_conversation_title(conversation_id: str):
    """
    Title a conversation from its opening message, in the background.

    Titling is cosmetic: a listing falls back to the truncated opening message while
    `title` is null, so a failure here degrades the label instead of breaking the
    listing, and is logged rather than retried.

    Args:
        conversation_id: ID of the conversation to title.
    """
    app_manager = current_app.app_manager
    conversation_service = app_manager.get_service("ai_conversation")
    ai_service = app_manager.get_service("ai")

    try:
        with app_manager.database.get_sync_session() as session:
            conversation_service.fill_title(session, ai_service, conversation_id)
            session.commit()
        logger.info(f"Titled conversation {conversation_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to title conversation {conversation_id}: {e}")
        return False


@shared_task
def index_pending_messages(batch_size: int = 500):
    """
    Index the messages that carry no search vector yet.

    Periodic rather than enqueued per message: it leaves the write path untouched, picks
    up whatever was written while the worker was down, and retries on its own what failed
    - where a lost per-message task would be lost for good. It also indexes the messages
    that predate the feature, so no separate backfill is needed.

    The delay before a message becomes searchable is immaterial: search exists to reach
    behind the compaction boundary, so it is only ever asked about messages that are
    already dozens of turns old.

    Args:
        batch_size: Messages indexed per run, capping the work of a single pass.
    """
    app_manager = current_app.app_manager
    conversation_service = app_manager.get_service("ai_conversation")
    ai_service = app_manager.get_service("ai")

    try:
        with app_manager.database.get_sync_session() as session:
            indexed = conversation_service.index_pending_messages(session, ai_service, batch_size)
            session.commit()
        if indexed:
            logger.info(f"Indexed {indexed} message(s) for search")
        return indexed
    except Exception as e:
        logger.error(f"Failed to index pending messages: {e}")
        return 0
