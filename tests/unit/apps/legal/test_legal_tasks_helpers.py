"""
Unit tests for legal task helpers: relay-id decoding hardening and the per-edge skip that
keeps one malformed record from crashing the whole daily reconciliation.
"""
import base64
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from lys.apps.legal import tasks


def _gid(raw: str, type_name: str = "AnonymizedUserNode") -> str:
    return base64.b64encode(f"{type_name}:{raw}".encode()).decode()


class TestDecodeRelayId:

    def test_decodes_valid_uuid(self):
        raw = str(uuid.uuid4())
        assert tasks._decode_relay_id(_gid(raw)) == raw

    def test_bad_base64_raises_value_error(self):
        with pytest.raises(ValueError):
            tasks._decode_relay_id("!!!not-base64!!!")

    def test_missing_separator_raises_value_error(self):
        with pytest.raises(ValueError):
            tasks._decode_relay_id(base64.b64encode(b"noseparator").decode())

    def test_non_uuid_payload_raises_value_error(self):
        with pytest.raises(ValueError):
            tasks._decode_relay_id(_gid("not-a-uuid"))


class _FakeClient:
    def __init__(self, response, **kwargs):
        self._response = response

    def query_sync(self, query, variables=None):
        return self._response


class TestFetchAnonymizedUsers:

    def test_skips_malformed_records_keeps_valid(self, monkeypatch):
        good_id = str(uuid.uuid4())
        response = {
            "anonymizedUsers": {
                "edges": [
                    {"node": {"id": _gid(good_id), "anonymizedAt": "2020-01-01T00:00:00+00:00"}},
                    {"node": {"id": "!!!not-base64!!!", "anonymizedAt": "2020-01-01T00:00:00+00:00"}},
                    {"node": {"id": _gid("not-a-uuid"), "anonymizedAt": "2020-01-01T00:00:00+00:00"}},
                ],
                "pageInfo": {"hasNextPage": False},
            }
        }
        monkeypatch.setattr(tasks, "GraphQLClient", lambda **kwargs: _FakeClient(response))

        users = tasks._fetch_anonymized_users(
            SimpleNamespace(secret_key="secret"), "http://user-auth/graphql",
            datetime.now(timezone.utc),
        )
        # Only the valid record survives; the two malformed ones are skipped, not fatal.
        assert users == [{"id": good_id, "anonymized_at": "2020-01-01T00:00:00+00:00"}]
