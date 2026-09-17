"""
Celery tasks for user token GDPR retention (869e7tjpn).

Two daily poll jobs, one per token kind:
- `purge_expired_refresh_tokens` - deletes UserRefreshToken rows whose retention
  has lapsed (dead at revocation, or at connection_expire_at otherwise).
- `purge_expired_one_time_tokens` - deletes UserOneTimeToken rows whose retention
  has lapsed (dead at consumption, or at the type's computed expiry otherwise).

Both are **synchronous** and use `get_sync_session()` - the lys Celery convention
(as in `licensing.tasks` / `legal.tasks`). Retention is a fixed, decided duration
(the ticket's table, not a per-deployment tuning knob), so it is a module constant
rather than a settings field - unlike lys.apps.legal.retention_days, which existed
before this ticket and stayed configurable for backward compatibility.
"""
import logging

from celery import current_app, shared_task

logger = logging.getLogger("lys.user_auth")

TOKEN_RETENTION_DAYS = 30


@shared_task
def purge_expired_refresh_tokens() -> int:
    """Delete refresh tokens whose retention has lapsed. Returns rows deleted."""
    app_manager = current_app.app_manager
    service = app_manager.get_service("user_refresh_token")

    with app_manager.database.get_sync_session() as session:
        deleted = service.purge_expired(TOKEN_RETENTION_DAYS, session=session)

    logger.info("Refresh token retention purge: %s row(s) deleted", deleted)
    return deleted


@shared_task
def purge_expired_one_time_tokens() -> int:
    """Delete one-time tokens whose retention has lapsed. Returns rows deleted."""
    app_manager = current_app.app_manager
    service = app_manager.get_service("user_one_time_token")

    with app_manager.database.get_sync_session() as session:
        deleted = service.purge_expired(TOKEN_RETENTION_DAYS, session=session)

    logger.info("One-time token retention purge: %s row(s) deleted", deleted)
    return deleted
