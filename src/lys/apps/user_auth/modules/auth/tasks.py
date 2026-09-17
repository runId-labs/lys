"""
Celery task for login attempt GDPR retention (869e7tjpn).

`purge_expired_login_attempts` deletes UserLoginAttempt rows past their
retention (1 year, counted from the recording date - CNIL guidance for
connection/security logs).

**Synchronous**, uses `get_sync_session()` - the lys Celery convention (as in
`licensing.tasks` / `legal.tasks` / `user_auth.modules.user.tasks`). Retention
is a fixed, decided duration (the ticket's table, not a per-deployment tuning
knob), so it is a module constant rather than a settings field.
"""
import logging

from celery import current_app, shared_task

logger = logging.getLogger("lys.user_auth")

LOGIN_ATTEMPT_RETENTION_DAYS = 365


@shared_task
def purge_expired_login_attempts() -> int:
    """Delete login attempts whose retention has lapsed. Returns rows deleted."""
    app_manager = current_app.app_manager
    service = app_manager.get_service("user_login_attempt")

    with app_manager.database.get_sync_session() as session:
        deleted = service.purge_expired(LOGIN_ATTEMPT_RETENTION_DAYS, session=session)

    logger.info("Login attempt retention purge: %s row(s) deleted", deleted)
    return deleted
