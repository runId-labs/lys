"""
E2E GraphQL execution tests exercising the idiomatic decorators end-to-end:
- `currentLegalDocument` (public `lys_field`)
- `acceptLegalDocument` (`lys_creation` — persists a consent proof)
- `anonymizedUsers` (`lys_connection` — internal service feed, relay pagination)
"""
import uuid

import pytest
from sqlalchemy import select

pytestmark = pytest.mark.asyncio


CURRENT_DOCUMENT_QUERY = """
query Current($type: String!, $lang: String!) {
    currentLegalDocument(typeId: $type, languageId: $lang) {
        id
        typeId
        languageId
        versionNumber
        pdfUrl
    }
}
"""

ACCEPT_MUTATION = """
mutation Accept($versionId: ID!) {
    acceptLegalDocument(versionId: $versionId) {
        id
        versionId
        acceptedByEmail
    }
}
"""

ANONYMIZED_USERS_QUERY = """
query Anonymized($since: DateTime!) {
    anonymizedUsers(since: $since, first: 100) {
        edges { node { id anonymizedAt } }
        pageInfo { hasNextPage }
    }
}
"""


class TestCurrentLegalDocument:

    async def test_public_query_returns_current_version(self, legal_client):
        resp = await legal_client.post("/graphql", json={
            "query": CURRENT_DOCUMENT_QUERY,
            "variables": {"type": "TERMS_OF_USE", "lang": "en"},
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("errors") is None, data
        doc = data["data"]["currentLegalDocument"]
        assert doc["typeId"] == "TERMS_OF_USE"
        assert doc["versionNumber"] == 1
        assert doc["pdfUrl"].startswith("/legal/versions/")

    async def test_missing_language_errors(self, legal_client):
        resp = await legal_client.post("/graphql", json={
            "query": CURRENT_DOCUMENT_QUERY,
            "variables": {"type": "TERMS_OF_USE", "lang": "de"},
        })
        data = resp.json()
        # currentLegalDocument is non-null, so a strict-resolution error nulls `data`.
        assert data.get("errors")  # no silent language fallback
        assert data.get("data") is None or data["data"].get("currentLegalDocument") is None


class TestAcceptLegalDocument:

    async def test_records_consent_via_creation(self, legal_client, legal_manager, user_token):
        # Create a real user (with email_address + private_data) to accept as.
        user_service = legal_manager.get_service("user")
        async with legal_manager.database.get_session() as session:
            user = await user_service.create_user(
                session=session,
                email="accepter@example.com",
                password="password123",
                language_id="en",
                first_name="Ann",
                last_name="Accepter",
                send_verification_email=False,
            )
            user_id = user.id

        version_gid = _global_id("LegalDocumentVersionNode", legal_manager._e2e_version_id)
        token, _ = await user_token(
            user_id=user_id, webservices={"accept_legal_document": "full"}
        )

        resp = await legal_client.post(
            "/graphql",
            json={"query": ACCEPT_MUTATION, "variables": {"versionId": version_gid}},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("errors") is None, data
        acc = data["data"]["acceptLegalDocument"]
        assert acc["acceptedByEmail"] == "accepter@example.com"

        # A proof row was persisted for this user + version.
        acceptance_entity = legal_manager.get_entity("legal_document_acceptance")
        async with legal_manager.database.get_session() as session:
            rows = (await session.execute(
                select(acceptance_entity).where(acceptance_entity.user_id == user_id)
            )).scalars().all()
        assert len(rows) == 1
        assert rows[0].version_id == legal_manager._e2e_version_id
        # F1: the persisted context carries a minimized IP (host octet zeroed), never the
        # full address.
        ctx = rows[0].acceptance_context
        if ctx and ctx.get("ip_address"):
            assert ctx["ip_address"].endswith(".0")


class TestAnonymizedUsersConnection:

    async def test_internal_service_feed(self, legal_client, legal_manager, service_token):
        resp = await legal_client.post(
            "/graphql",
            json={
                "query": ANONYMIZED_USERS_QUERY,
                "variables": {"since": "2020-01-01T00:00:00+00:00"},
            },
            headers={"Authorization": f"Service {service_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("errors") is None, data
        edges = data["data"]["anonymizedUsers"]["edges"]
        # ids are Relay global ids (never raw in clear); decode to the raw user id.
        raw_ids = {_decode_global_id(e["node"]["id"]) for e in edges}
        assert legal_manager._e2e_anonymized_user_id in raw_ids
        assert all(e["node"]["anonymizedAt"] is not None for e in edges)

    async def test_requires_service_auth(self, legal_client):
        """Without a Service token the internal feed is not accessible."""
        resp = await legal_client.post("/graphql", json={
            "query": ANONYMIZED_USERS_QUERY,
            "variables": {"since": "2020-01-01T00:00:00+00:00"},
        })
        data = resp.json()
        assert data["data"] is None or data["data"].get("anonymizedUsers") is None
        assert data.get("errors")


def _global_id(type_name: str, node_id: str) -> str:
    """Encode a Relay global id (base64 of 'Type:id')."""
    import base64
    return base64.b64encode(f"{type_name}:{node_id}".encode()).decode()


def _decode_global_id(global_id: str) -> str:
    """Decode a Relay global id to its raw id."""
    import base64
    return base64.b64decode(global_id).decode().split(":", 1)[1]
