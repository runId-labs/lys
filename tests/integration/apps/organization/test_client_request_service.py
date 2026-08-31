"""
Integration tests for ClientRequestService.

Tests cover:
- Counting open requests per client
- Cancelling and scrubbing a user's open requests on anonymization
- Settled requests being left untouched
- Identity-map resynchronization after the bulk update
"""

import pytest
from uuid import uuid4

from lys.apps.organization.modules.client_request.consts import (
    CLIENT_REQUEST_REASON_REQUESTER_ANONYMIZED,
    CLIENT_REQUEST_STATUS_CANCELLED,
    CLIENT_REQUEST_STATUS_ERROR,
    CLIENT_REQUEST_STATUS_PENDING,
    CLIENT_REQUEST_STATUS_PROCESSED,
)


async def _create_client_and_user(organization_app_manager, label: str):
    client_service = organization_app_manager.get_service("client")
    user_service = organization_app_manager.get_service("user")

    async with organization_app_manager.database.get_session() as session:
        client = await client_service.create_client_with_owner(
            session=session,
            client_name=f"Corp-{label}-{uuid4().hex[:8]}",
            email=f"owner-{label}-{uuid4().hex[:8]}@example.com",
            password="Password123!",
            language_id="en",
            send_verification_email=False
        )

    async with organization_app_manager.database.get_session() as session:
        user = await user_service.create_client_user(
            session=session,
            client_id=client.id,
            email=f"user-{label}-{uuid4().hex[:8]}@example.com",
            language_id="en"
        )

    return client, user


class TestClientRequestServiceCancelOpenForAnonymizedUser:
    """Test ClientRequestService.cancel_open_for_anonymized_user."""

    @pytest.mark.asyncio
    async def test_cancels_and_scrubs_open_requests(self, organization_app_manager):
        client_request_service = organization_app_manager.get_service("client_request")
        client, user = await _create_client_and_user(organization_app_manager, "cancel")

        async with organization_app_manager.database.get_session() as session:
            request = await client_request_service.create(
                session=session,
                type_id="SUPPORT",
                status_id=CLIENT_REQUEST_STATUS_PENDING,
                client_id=client.id,
                user_id=user.id,
                contact_phone="+33612345678",
                message="Please call me back",
            )
            await session.commit()
            request_id = request.id

        async with organization_app_manager.database.get_session() as session:
            cancelled = await client_request_service.cancel_open_for_anonymized_user(
                user_id=user.id, session=session
            )
            await session.commit()

        assert cancelled == 1

        async with organization_app_manager.database.get_session() as session:
            request = await client_request_service.get_by_id(request_id, session)
            assert request.status_id == CLIENT_REQUEST_STATUS_CANCELLED
            assert request.reason_code == CLIENT_REQUEST_REASON_REQUESTER_ANONYMIZED
            assert request.contact_phone is None
            assert request.message is None
            assert request.processed_at is not None

    @pytest.mark.asyncio
    async def test_leaves_settled_requests_untouched(self, organization_app_manager):
        client_request_service = organization_app_manager.get_service("client_request")
        client, user = await _create_client_and_user(organization_app_manager, "settled")

        async with organization_app_manager.database.get_session() as session:
            request = await client_request_service.create(
                session=session,
                type_id="SUPPORT",
                status_id=CLIENT_REQUEST_STATUS_PROCESSED,
                client_id=client.id,
                user_id=user.id,
                contact_phone="+33612345678",
                message="Already handled",
            )
            await session.commit()
            request_id = request.id

        async with organization_app_manager.database.get_session() as session:
            cancelled = await client_request_service.cancel_open_for_anonymized_user(
                user_id=user.id, session=session
            )
            await session.commit()

        assert cancelled == 0

        async with organization_app_manager.database.get_session() as session:
            request = await client_request_service.get_by_id(request_id, session)
            assert request.status_id == CLIENT_REQUEST_STATUS_PROCESSED
            assert request.contact_phone == "+33612345678"
            assert request.message == "Already handled"

    @pytest.mark.asyncio
    async def test_resynchronizes_already_loaded_orm_objects(self, organization_app_manager):
        """A ClientRequest loaded before the bulk update must reflect it afterwards."""
        client_request_service = organization_app_manager.get_service("client_request")
        client, user = await _create_client_and_user(organization_app_manager, "sync")

        async with organization_app_manager.database.get_session() as session:
            request = await client_request_service.create(
                session=session,
                type_id="SUPPORT",
                status_id=CLIENT_REQUEST_STATUS_PENDING,
                client_id=client.id,
                user_id=user.id,
                contact_phone="+33600000000",
                message="Call me",
            )
            await session.commit()

            # Load it into this session's identity map before the bulk update runs.
            loaded = await client_request_service.get_by_id(request.id, session)

            await client_request_service.cancel_open_for_anonymized_user(
                user_id=user.id, session=session
            )

            assert loaded.status_id == CLIENT_REQUEST_STATUS_CANCELLED
            assert loaded.contact_phone is None
            assert loaded.message is None


class TestClientRequestServiceGetOpenForClient:
    """Test ClientRequestService.get_open_for_client."""

    @pytest.mark.asyncio
    async def test_returns_only_open_requests_oldest_first(self, organization_app_manager):
        client_request_service = organization_app_manager.get_service("client_request")
        client, user = await _create_client_and_user(organization_app_manager, "open")

        async with organization_app_manager.database.get_session() as session:
            pending = await client_request_service.create(
                session=session, type_id="SUPPORT", status_id=CLIENT_REQUEST_STATUS_PENDING,
                client_id=client.id, user_id=user.id,
            )
            error = await client_request_service.create(
                session=session, type_id="SUPPORT", status_id=CLIENT_REQUEST_STATUS_ERROR,
                client_id=client.id, user_id=user.id,
            )
            await client_request_service.create(
                session=session, type_id="SUPPORT", status_id=CLIENT_REQUEST_STATUS_PROCESSED,
                client_id=client.id, user_id=user.id,
            )
            await session.commit()

        async with organization_app_manager.database.get_session() as session:
            open_requests = await client_request_service.get_open_for_client(client.id, session)

        assert [request.id for request in open_requests] == [pending.id, error.id]

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_open_requests(self, organization_app_manager):
        client_request_service = organization_app_manager.get_service("client_request")
        client, user = await _create_client_and_user(organization_app_manager, "no-open")

        async with organization_app_manager.database.get_session() as session:
            await client_request_service.create(
                session=session, type_id="SUPPORT", status_id=CLIENT_REQUEST_STATUS_PROCESSED,
                client_id=client.id, user_id=user.id,
            )
            await session.commit()

        async with organization_app_manager.database.get_session() as session:
            open_requests = await client_request_service.get_open_for_client(client.id, session)

        assert open_requests == []

    @pytest.mark.asyncio
    async def test_does_not_leak_requests_from_other_clients(self, organization_app_manager):
        client_request_service = organization_app_manager.get_service("client_request")
        client_a, user_a = await _create_client_and_user(organization_app_manager, "leak-a")
        client_b, user_b = await _create_client_and_user(organization_app_manager, "leak-b")

        async with organization_app_manager.database.get_session() as session:
            await client_request_service.create(
                session=session, type_id="SUPPORT", status_id=CLIENT_REQUEST_STATUS_PENDING,
                client_id=client_b.id, user_id=user_b.id,
            )
            await session.commit()

        async with organization_app_manager.database.get_session() as session:
            open_requests = await client_request_service.get_open_for_client(client_a.id, session)

        assert open_requests == []


class TestClientRequestServiceCountOpenByClient:
    """Test ClientRequestService.count_open_by_client."""

    @pytest.mark.asyncio
    async def test_counts_only_open_requests_per_client(self, organization_app_manager):
        client_request_service = organization_app_manager.get_service("client_request")
        client, user = await _create_client_and_user(organization_app_manager, "count")

        async with organization_app_manager.database.get_session() as session:
            await client_request_service.create(
                session=session, type_id="SUPPORT", status_id=CLIENT_REQUEST_STATUS_PENDING,
                client_id=client.id, user_id=user.id,
            )
            await client_request_service.create(
                session=session, type_id="SUPPORT", status_id=CLIENT_REQUEST_STATUS_ERROR,
                client_id=client.id, user_id=user.id,
            )
            await client_request_service.create(
                session=session, type_id="SUPPORT", status_id=CLIENT_REQUEST_STATUS_PROCESSED,
                client_id=client.id, user_id=user.id,
            )
            await session.commit()

        async with organization_app_manager.database.get_session() as session:
            counts = await client_request_service.count_open_by_client([client.id], session)

        assert counts == {client.id: 2}

    @pytest.mark.asyncio
    async def test_returns_empty_dict_for_no_client_ids(self, organization_app_manager):
        client_request_service = organization_app_manager.get_service("client_request")

        async with organization_app_manager.database.get_session() as session:
            counts = await client_request_service.count_open_by_client([], session)

        assert counts == {}
