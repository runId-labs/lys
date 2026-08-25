"""
Unit tests for the client_request module services.

Tests the pure lifecycle-transition logic (mark_processed/mark_failed/mark_cancelled).
cancel_open_for_anonymized_user builds a real SQLAlchemy statement against the mapped
entity class, which requires a loaded AppManager — it is tested at integration level.
"""

from types import SimpleNamespace

from lys.apps.organization.modules.client_request.consts import (
    CLIENT_REQUEST_STATUS_CANCELLED,
    CLIENT_REQUEST_STATUS_ERROR,
    CLIENT_REQUEST_STATUS_PROCESSED,
)
from lys.apps.organization.modules.client_request.services import ClientRequestService


class TestClientRequestServiceLifecycleTransitions:
    """Tests for the mark_* transition helpers."""

    def test_mark_processed_sets_status_reason_and_timestamp(self):
        request = SimpleNamespace(status_id="PENDING", reason_code=None, processed_at=None)

        result = ClientRequestService.mark_processed(request, reason_code="DONE")

        assert result is request
        assert result.status_id == CLIENT_REQUEST_STATUS_PROCESSED
        assert result.reason_code == "DONE"
        assert result.processed_at is not None

    def test_mark_failed_sets_status_and_reason_but_not_processed_at(self):
        request = SimpleNamespace(status_id="PENDING", reason_code=None, processed_at=None)

        result = ClientRequestService.mark_failed(request, reason_code="UPSTREAM_TIMEOUT")

        assert result.status_id == CLIENT_REQUEST_STATUS_ERROR
        assert result.reason_code == "UPSTREAM_TIMEOUT"
        assert result.processed_at is None

    def test_mark_cancelled_sets_status_reason_and_timestamp(self):
        request = SimpleNamespace(status_id="PENDING", reason_code=None, processed_at=None)

        result = ClientRequestService.mark_cancelled(request, reason_code="CLIENT_WITHDREW")

        assert result.status_id == CLIENT_REQUEST_STATUS_CANCELLED
        assert result.reason_code == "CLIENT_WITHDREW"
        assert result.processed_at is not None


class TestClientRequestServiceGetOpenForClientSignature:
    """Signature checks for get_open_for_client (query behavior is tested at integration level)."""

    def test_is_async(self):
        import inspect

        assert inspect.iscoroutinefunction(ClientRequestService.get_open_for_client)

    def test_signature(self):
        import inspect

        sig = inspect.signature(ClientRequestService.get_open_for_client)
        assert "client_id" in sig.parameters
        assert "session" in sig.parameters
