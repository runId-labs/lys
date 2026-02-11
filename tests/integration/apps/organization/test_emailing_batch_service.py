"""
Integration tests for organization EmailingBatchService (Phase 7.7).

Tests organization-scoped recipient resolution with real database:
- dispatch with organization_data filters by client_ids
- dispatch without organization_data falls back to role-based resolution
- Combination of role + org scoping
"""
import uuid
from unittest.mock import patch

import pytest
import pytest_asyncio

from lys.apps.base.modules.emailing.consts import WAITING_EMAILING_STATUS


@pytest_asyncio.fixture
async def org_emailing_data(organization_app_manager):
    """Create test data for organization emailing batch dispatch tests."""
    am = organization_app_manager

    async with am.database.get_session() as session:
        # Create emailing type with NORMAL_ROLE
        emailing_type_service = am.get_service("emailing_type")
        await emailing_type_service.create(
            session=session,
            id="TEST_ORG_EMAIL",
            enabled=True,
            subject="Org Email",
            template="test_org",
            context_description={"front_url": None},
        )

        # Link emailing type to NORMAL_ROLE
        from lys.apps.user_role.modules.emailing.entities import emailing_type_role
        await session.execute(
            emailing_type_role.insert().values(
                emailing_type_id="TEST_ORG_EMAIL",
                role_id="NORMAL_ROLE",
            )
        )

        # Create emailing type WITHOUT roles (for fallback test)
        await emailing_type_service.create(
            session=session,
            id="TEST_ORG_NO_ROLE",
            enabled=True,
            subject="Org No Role",
            template="test_org_no_role",
            context_description={},
        )

        # Ensure WAITING emailing status exists
        emailing_status_service = am.get_service("emailing_status")
        try:
            await emailing_status_service.create(
                session=session, id=WAITING_EMAILING_STATUS, enabled=True
            )
        except Exception:
            pass

        # Create 2 clients
        client_entity = am.get_entity("client")
        user_entity = am.get_entity("user")
        email_entity = am.get_entity("user_email_address")
        private_data_entity = am.get_entity("user_private_data")
        client_user_role_entity = am.get_entity("client_user_role")

        # Create a supervisor user (owner for clients)
        owner_id = str(uuid.uuid4())
        owner = user_entity(
            id=owner_id, password="pw", is_super_user=True, language_id="en"
        )
        session.add(owner)
        await session.flush()
        owner_email = email_entity(id="owner@test.com", user_id=owner_id)
        session.add(owner_email)

        client_a_id = str(uuid.uuid4())
        client_a = client_entity(id=client_a_id, name="Client A", owner_id=owner_id)
        session.add(client_a)

        client_b_id = str(uuid.uuid4())
        client_b = client_entity(id=client_b_id, name="Client B", owner_id=owner_id)
        session.add(client_b)
        await session.flush()

        # Create users in each client
        user_ids = {}
        for name, cid in [("alice", client_a_id), ("bob", client_a_id), ("charlie", client_b_id)]:
            uid = str(uuid.uuid4())
            user = user_entity(
                id=uid, password="pw", is_super_user=False,
                language_id="en", client_id=cid,
            )
            session.add(user)
            await session.flush()

            email = email_entity(id=f"{name}@org-test.com", user_id=uid)
            session.add(email)

            pd = private_data_entity(
                user_id=uid, first_name=name.capitalize(), last_name="Org",
            )
            session.add(pd)

            # Assign NORMAL_ROLE via user_role table
            from lys.apps.user_role.modules.user.entities import user_role
            await session.execute(
                user_role.insert().values(user_id=uid, role_id="NORMAL_ROLE")
            )

            # Assign NORMAL_ROLE via client_user_role table
            cur = client_user_role_entity(user_id=uid, role_id="NORMAL_ROLE")
            session.add(cur)

            user_ids[name] = uid

        await session.commit()

    return {
        "app_manager": am,
        "user_ids": user_ids,
        "client_a_id": client_a_id,
        "client_b_id": client_b_id,
        "owner_id": owner_id,
    }


class TestOrgBatchDispatchAsync:
    """Integration tests for async dispatch with organization scoping."""

    @pytest.mark.asyncio
    async def test_dispatch_with_org_data_filters_by_client(self, org_emailing_data):
        """Dispatch with client_ids=[client_a] only emails users in client A."""
        am = org_emailing_data["app_manager"]
        user_ids = org_emailing_data["user_ids"]
        client_a_id = org_emailing_data["client_a_id"]

        emailing_batch_service = am.get_service("emailing_batch")

        async with am.database.get_session() as session:
            with patch.object(am.get_service("emailing"), "send_email"):
                result = await emailing_batch_service.dispatch(
                    session=session,
                    type_id="TEST_ORG_EMAIL",
                    email_context={"front_url": "https://test.com"},
                    triggered_by_user_id=None,
                    organization_data={"client_ids": [client_a_id]},
                )

        # alice and bob are in client A with NORMAL_ROLE
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_dispatch_with_org_data_other_client(self, org_emailing_data):
        """Dispatch with client_ids=[client_b] only emails users in client B."""
        am = org_emailing_data["app_manager"]
        client_b_id = org_emailing_data["client_b_id"]

        emailing_batch_service = am.get_service("emailing_batch")

        async with am.database.get_session() as session:
            with patch.object(am.get_service("emailing"), "send_email"):
                result = await emailing_batch_service.dispatch(
                    session=session,
                    type_id="TEST_ORG_EMAIL",
                    email_context={"front_url": "https://test.com"},
                    triggered_by_user_id=None,
                    organization_data={"client_ids": [client_b_id]},
                )

        # Only charlie is in client B
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_dispatch_with_both_clients(self, org_emailing_data):
        """Dispatch with both client_ids emails all 3 users."""
        am = org_emailing_data["app_manager"]
        client_a_id = org_emailing_data["client_a_id"]
        client_b_id = org_emailing_data["client_b_id"]

        emailing_batch_service = am.get_service("emailing_batch")

        async with am.database.get_session() as session:
            with patch.object(am.get_service("emailing"), "send_email"):
                result = await emailing_batch_service.dispatch(
                    session=session,
                    type_id="TEST_ORG_EMAIL",
                    email_context={"front_url": "https://test.com"},
                    triggered_by_user_id=None,
                    organization_data={"client_ids": [client_a_id, client_b_id]},
                )

        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_dispatch_without_org_data_falls_back_to_roles(self, org_emailing_data):
        """Without organization_data, falls back to role-based resolution (all role users)."""
        am = org_emailing_data["app_manager"]
        user_ids = org_emailing_data["user_ids"]

        emailing_batch_service = am.get_service("emailing_batch")

        async with am.database.get_session() as session:
            with patch.object(am.get_service("emailing"), "send_email"):
                result = await emailing_batch_service.dispatch(
                    session=session,
                    type_id="TEST_ORG_EMAIL",
                    email_context={"front_url": "https://test.com"},
                    triggered_by_user_id=user_ids["alice"],
                    organization_data=None,
                )

        # No org scoping → role resolution finds all 3 users with NORMAL_ROLE + triggered_by (alice, deduplicated)
        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_dispatch_org_enriches_private_data(self, org_emailing_data):
        """Organization dispatch enriches context with private_data."""
        am = org_emailing_data["app_manager"]
        client_b_id = org_emailing_data["client_b_id"]

        emailing_batch_service = am.get_service("emailing_batch")
        emailing_entity = am.get_entity("emailing")

        async with am.database.get_session() as session:
            with patch.object(am.get_service("emailing"), "send_email"):
                result_ids = await emailing_batch_service.dispatch(
                    session=session,
                    type_id="TEST_ORG_EMAIL",
                    email_context={"front_url": "https://test.com"},
                    triggered_by_user_id=None,
                    organization_data={"client_ids": [client_b_id]},
                )

            for eid in result_ids:
                emailing = await session.get(emailing_entity, eid)
                assert "private_data" in emailing.context
                assert emailing.context["private_data"]["first_name"] == "Charlie"


    # Note: Sync dispatch_sync tests are skipped for integration because
    # SQLite in-memory databases cannot be shared between async and sync engines.
    # Sync path is covered by unit tests.
