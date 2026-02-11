"""
Integration tests for user_role EmailingBatchService (Phase 7.6).

Tests role-based recipient resolution with real database:
- EmailingType with roles resolves recipients from user_role table
- EmailingType without roles falls back to base resolution
- Private data enrichment in email context
- should_send_fn filtering
"""
import uuid
from unittest.mock import patch

import pytest
import pytest_asyncio

from lys.apps.base.modules.emailing.consts import WAITING_EMAILING_STATUS


@pytest_asyncio.fixture
async def emailing_batch_data(user_role_app_manager):
    """Create test data for emailing batch dispatch tests."""
    am = user_role_app_manager

    async with am.database.get_session() as session:
        # Create emailing type WITH role (linked to ROLE_A)
        emailing_type_service = am.get_service("emailing_type")
        await emailing_type_service.create(
            session=session,
            id="TEST_ROLE_EMAIL",
            enabled=True,
            subject="Role Email",
            template="test_role",
            context_description={"front_url": None},
        )

        # Link emailing type to ROLE_A via association table
        from lys.apps.user_role.modules.emailing.entities import emailing_type_role
        await session.execute(
            emailing_type_role.insert().values(
                emailing_type_id="TEST_ROLE_EMAIL",
                role_id="ROLE_A",
            )
        )

        # Create emailing type WITHOUT roles
        await emailing_type_service.create(
            session=session,
            id="TEST_NO_ROLE_EMAIL",
            enabled=True,
            subject="No Role Email",
            template="test_no_role",
            context_description={},
        )

        # Create emailing status WAITING if not exists
        emailing_status_service = am.get_service("emailing_status")
        try:
            await emailing_status_service.create(
                session=session, id=WAITING_EMAILING_STATUS, enabled=True
            )
        except Exception:
            pass  # Already exists

        # Create users with email addresses and private data
        user_entity = am.get_entity("user")
        email_entity = am.get_entity("user_email_address")
        private_data_entity = am.get_entity("user_private_data")

        user_ids = {}
        for name in ["alice", "bob", "charlie"]:
            user_id = str(uuid.uuid4())
            user = user_entity(
                id=user_id,
                password="hashed_pw",
                is_super_user=False,
                language_id="en",
            )
            session.add(user)
            await session.flush()

            email = email_entity(id=f"{name}@test.com", user_id=user_id)
            session.add(email)

            pd = private_data_entity(
                user_id=user_id,
                first_name=name.capitalize(),
                last_name="Test",
            )
            session.add(pd)
            user_ids[name] = user_id

        # Assign ROLE_A to alice and bob via user_role table
        from lys.apps.user_role.modules.user.entities import user_role
        for name in ["alice", "bob"]:
            await session.execute(
                user_role.insert().values(
                    user_id=user_ids[name],
                    role_id="ROLE_A",
                )
            )

        await session.commit()

    return {"app_manager": am, "user_ids": user_ids}


class TestRoleBatchDispatchAsync:
    """Integration tests for async dispatch with role-based resolution."""

    @pytest.mark.asyncio
    async def test_dispatch_with_roles_creates_emails_for_role_users(self, emailing_batch_data):
        """EmailingType with ROLE_A should create emails for alice and bob."""
        am = emailing_batch_data["app_manager"]
        user_ids = emailing_batch_data["user_ids"]

        emailing_batch_service = am.get_service("emailing_batch")

        async with am.database.get_session() as session:
            with patch.object(am.get_service("emailing"), "send_email"):
                result = await emailing_batch_service.dispatch(
                    session=session,
                    type_id="TEST_ROLE_EMAIL",
                    email_context={"front_url": "https://test.com"},
                    triggered_by_user_id=user_ids["alice"],
                )

        # alice and bob have ROLE_A, so 2 emails
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_dispatch_without_roles_only_triggered_by(self, emailing_batch_data):
        """EmailingType without roles should only email the triggered_by user."""
        am = emailing_batch_data["app_manager"]
        user_ids = emailing_batch_data["user_ids"]

        emailing_batch_service = am.get_service("emailing_batch")

        async with am.database.get_session() as session:
            with patch.object(am.get_service("emailing"), "send_email"):
                result = await emailing_batch_service.dispatch(
                    session=session,
                    type_id="TEST_NO_ROLE_EMAIL",
                    email_context={},
                    triggered_by_user_id=user_ids["charlie"],
                )

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_dispatch_enriches_private_data(self, emailing_batch_data):
        """Created Emailing records should have private_data in context."""
        am = emailing_batch_data["app_manager"]
        user_ids = emailing_batch_data["user_ids"]

        emailing_batch_service = am.get_service("emailing_batch")
        emailing_entity = am.get_entity("emailing")

        async with am.database.get_session() as session:
            with patch.object(am.get_service("emailing"), "send_email"):
                result_ids = await emailing_batch_service.dispatch(
                    session=session,
                    type_id="TEST_ROLE_EMAIL",
                    email_context={"front_url": "https://test.com"},
                    triggered_by_user_id=user_ids["alice"],
                )

            # Check that at least one emailing has private_data enriched
            for eid in result_ids:
                emailing = await session.get(emailing_entity, eid)
                assert emailing is not None
                assert "private_data" in emailing.context
                assert "first_name" in emailing.context["private_data"]

    @pytest.mark.asyncio
    async def test_dispatch_with_should_send_fn_filters(self, emailing_batch_data):
        """should_send_fn can filter out specific recipients."""
        am = emailing_batch_data["app_manager"]
        user_ids = emailing_batch_data["user_ids"]

        emailing_batch_service = am.get_service("emailing_batch")

        # Only allow alice
        def allow_alice_only(uid):
            return uid == user_ids["alice"]

        async with am.database.get_session() as session:
            with patch.object(am.get_service("emailing"), "send_email"):
                result = await emailing_batch_service.dispatch(
                    session=session,
                    type_id="TEST_ROLE_EMAIL",
                    email_context={"front_url": "https://test.com"},
                    triggered_by_user_id=user_ids["alice"],
                    should_send_fn=allow_alice_only,
                )

        # Only alice passes the filter
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_dispatch_deduplicates_triggered_by_and_role(self, emailing_batch_data):
        """If triggered_by user also has the role, they get only one email."""
        am = emailing_batch_data["app_manager"]
        user_ids = emailing_batch_data["user_ids"]

        emailing_batch_service = am.get_service("emailing_batch")

        async with am.database.get_session() as session:
            with patch.object(am.get_service("emailing"), "send_email"):
                result = await emailing_batch_service.dispatch(
                    session=session,
                    type_id="TEST_ROLE_EMAIL",
                    email_context={"front_url": "https://test.com"},
                    triggered_by_user_id=user_ids["alice"],
                    additional_user_ids=[user_ids["alice"]],
                )

        # alice has ROLE_A + is triggered_by + additional = still 2 (alice + bob)
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_dispatch_unknown_type_raises(self, emailing_batch_data):
        """Dispatch with unknown type_id raises ValueError."""
        am = emailing_batch_data["app_manager"]

        emailing_batch_service = am.get_service("emailing_batch")

        async with am.database.get_session() as session:
            with pytest.raises(ValueError, match="not found"):
                await emailing_batch_service.dispatch(
                    session=session,
                    type_id="NONEXISTENT_TYPE",
                    email_context={},
                    triggered_by_user_id="fake-id",
                )


    # Note: Sync dispatch_sync tests are skipped for integration because
    # SQLite in-memory databases cannot be shared between async and sync engines.
    # Sync path is covered by unit tests.
