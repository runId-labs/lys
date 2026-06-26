"""
Integration tests for user_auth NotificationService.mark_all_as_read.

Tests cover:
- Marking every unread notification of a user as read (returns 0 remaining)
- Per-user scoping: a user can only clear their own notifications
- Already-read notifications are left untouched (idempotent)
- No-op when the user has no unread notifications

Test approach: Real SQLite in-memory database. Notifications are created
through NotificationBatchService.dispatch (the production path), then cleared
via NotificationService.mark_all_as_read.

The user_auth_app_manager fixture is defined in tests/conftest.py and is shared
across the session, so each test uses freshly generated user IDs to stay isolated.
"""

import pytest
from uuid import uuid4


async def _seed_notification_type(app_manager, type_id):
    """Create a notification type (idempotent across the shared session)."""
    notification_type_service = app_manager.get_service("notification_type")
    async with app_manager.database.get_session() as session:
        try:
            await notification_type_service.create(
                session=session,
                id=type_id,
                enabled=True,
            )
            await session.commit()
        except Exception:
            await session.rollback()


async def _dispatch_to(app_manager, type_id, user_ids):
    """Dispatch one notification to each of the given users."""
    batch_service = app_manager.get_service("notification_batch")
    async with app_manager.database.get_session() as session:
        await batch_service.dispatch(
            session=session,
            type_id=type_id,
            data={"message": "test"},
            additional_user_ids=list(user_ids),
        )
        await session.commit()


class TestMarkAllAsRead:
    """Test NotificationService.mark_all_as_read."""

    @pytest.mark.asyncio
    async def test_marks_all_unread_as_read(self, user_auth_app_manager):
        """All unread notifications of the user are cleared; returns 0 remaining."""
        type_id = "MARK_ALL_BASIC"
        await _seed_notification_type(user_auth_app_manager, type_id)

        user_id = str(uuid4())
        # Two separate dispatches => two notifications for the same user
        await _dispatch_to(user_auth_app_manager, type_id, [user_id])
        await _dispatch_to(user_auth_app_manager, type_id, [user_id])

        notification_service = user_auth_app_manager.get_service("notification")

        async with user_auth_app_manager.database.get_session() as session:
            # Precondition: two unread
            assert await notification_service.count_unread(session, user_id) == 2

            remaining = await notification_service.mark_all_as_read(session, user_id)
            await session.commit()

            assert remaining == 0
            assert await notification_service.count_unread(session, user_id) == 0

    @pytest.mark.asyncio
    async def test_scoped_to_user(self, user_auth_app_manager):
        """Clearing one user's notifications must not affect another user's."""
        type_id = "MARK_ALL_SCOPE"
        await _seed_notification_type(user_auth_app_manager, type_id)

        user_a = str(uuid4())
        user_b = str(uuid4())
        await _dispatch_to(user_auth_app_manager, type_id, [user_a, user_b])

        notification_service = user_auth_app_manager.get_service("notification")

        async with user_auth_app_manager.database.get_session() as session:
            assert await notification_service.count_unread(session, user_a) == 1
            assert await notification_service.count_unread(session, user_b) == 1

            remaining = await notification_service.mark_all_as_read(session, user_a)
            await session.commit()

            assert remaining == 0
            # user_b is untouched
            assert await notification_service.count_unread(session, user_b) == 1

    @pytest.mark.asyncio
    async def test_noop_when_no_unread(self, user_auth_app_manager):
        """Calling on a user with no unread notifications returns 0 and does not error."""
        notification_service = user_auth_app_manager.get_service("notification")
        unknown_user = str(uuid4())

        async with user_auth_app_manager.database.get_session() as session:
            remaining = await notification_service.mark_all_as_read(session, unknown_user)
            await session.commit()

            assert remaining == 0

    @pytest.mark.asyncio
    async def test_idempotent_second_call(self, user_auth_app_manager):
        """A second call after everything is read still returns 0."""
        type_id = "MARK_ALL_IDEMPOTENT"
        await _seed_notification_type(user_auth_app_manager, type_id)

        user_id = str(uuid4())
        await _dispatch_to(user_auth_app_manager, type_id, [user_id])

        notification_service = user_auth_app_manager.get_service("notification")

        async with user_auth_app_manager.database.get_session() as session:
            assert await notification_service.mark_all_as_read(session, user_id) == 0
            await session.commit()

        async with user_auth_app_manager.database.get_session() as session:
            assert await notification_service.mark_all_as_read(session, user_id) == 0
            await session.commit()
