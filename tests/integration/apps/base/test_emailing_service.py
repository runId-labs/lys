"""
Integration tests for base EmailingService.

Tests cover:
- generate_emailing (creation, context, default status)

Note: send_email tests are omitted because the method uses get_sync_session()
which creates a separate sync engine that cannot share SQLite in-memory databases
with the async engine used in tests. send_email is covered by unit tests.
"""

import pytest

from lys.apps.base.modules.emailing.consts import WAITING_EMAILING_STATUS


class TestEmailingServiceGenerateEmailing:
    """Test EmailingService.generate_emailing."""

    @pytest.mark.asyncio
    async def test_generate_emailing_creates_record(self, user_auth_app_manager):
        """Test generating an emailing record."""
        emailing_service = user_auth_app_manager.get_service("emailing")

        from lys.apps.user_auth.modules.emailing.consts import USER_PASSWORD_RESET_EMAILING_TYPE

        async with user_auth_app_manager.database.get_session() as session:
            emailing = await emailing_service.generate_emailing(
                type_id=USER_PASSWORD_RESET_EMAILING_TYPE,
                email_address="test@example.com",
                language_id="en",
                session=session
            )

            assert emailing.id is not None
            assert emailing.email_address == "test@example.com"
            assert emailing.type_id == USER_PASSWORD_RESET_EMAILING_TYPE
            assert emailing.language_id == "en"

    @pytest.mark.asyncio
    async def test_generate_emailing_default_status(self, user_auth_app_manager):
        """Test that generated emailing has WAITING status by default."""
        emailing_service = user_auth_app_manager.get_service("emailing")

        from lys.apps.user_auth.modules.emailing.consts import USER_PASSWORD_RESET_EMAILING_TYPE

        async with user_auth_app_manager.database.get_session() as session:
            emailing = await emailing_service.generate_emailing(
                type_id=USER_PASSWORD_RESET_EMAILING_TYPE,
                email_address="status@example.com",
                language_id="en",
                session=session
            )

            assert emailing.status_id == WAITING_EMAILING_STATUS

    @pytest.mark.asyncio
    async def test_generate_emailing_with_context(self, user_auth_app_manager):
        """Test that context is properly computed and stored."""
        emailing_service = user_auth_app_manager.get_service("emailing")

        from lys.apps.user_auth.modules.emailing.consts import USER_PASSWORD_RESET_EMAILING_TYPE

        async with user_auth_app_manager.database.get_session() as session:
            emailing = await emailing_service.generate_emailing(
                type_id=USER_PASSWORD_RESET_EMAILING_TYPE,
                email_address="context@example.com",
                language_id="fr",
                session=session,
                reset_url="https://example.com/reset/token123"
            )

            assert emailing.id is not None
            # Context is computed from context_description (empty in test fixture)
            assert emailing.context is not None
