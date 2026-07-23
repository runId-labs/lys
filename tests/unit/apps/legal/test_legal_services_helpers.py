"""
Unit tests for service-owned helpers: GDPR data minimization (IP truncation, user-agent
capping) applied when building the acceptance context.
"""
from lys.apps.legal.modules.legal_document.services import (
    _MAX_USER_AGENT_LENGTH,
    LegalDocumentAcceptanceService,
    LegalDocumentVersionService,
    _anonymize_ip,
)


class TestNormalizeSource:

    def test_bare_path_becomes_object(self):
        assert LegalDocumentVersionService._normalize_source("legal/tou_en.md") == {
            "path": "legal/tou_en.md"
        }

    def test_object_passes_through(self):
        source = {"path": "legal/tou_en.md", "template": "legal.html"}
        assert LegalDocumentVersionService._normalize_source(source) == source


class TestAnonymizeIp:

    def test_ipv4_zeroes_host_octet(self):
        assert _anonymize_ip("192.168.1.55") == "192.168.1.0"
        assert _anonymize_ip("8.8.8.8") == "8.8.8.0"

    def test_ipv6_truncates_to_48(self):
        assert _anonymize_ip("2001:db8:abcd:1234:5678:9abc:def0:1234") == "2001:db8:abcd::"

    def test_none_and_invalid(self):
        assert _anonymize_ip(None) is None
        assert _anonymize_ip("") is None
        assert _anonymize_ip("not-an-ip") is None


class TestBuildAcceptanceContext:

    def test_minimizes_ip_and_caps_agent(self):
        ctx = LegalDocumentAcceptanceService._build_acceptance_context(
            "10.20.30.40", "Mozilla/5.0", None
        )
        assert ctx["ip_address"] == "10.20.30.0"
        assert ctx["user_agent"] == "Mozilla/5.0"

    def test_caps_long_user_agent(self):
        ctx = LegalDocumentAcceptanceService._build_acceptance_context(
            "1.1.1.1", "A" * 5000, None
        )
        assert len(ctx["user_agent"]) == _MAX_USER_AGENT_LENGTH

    def test_merges_extra(self):
        ctx = LegalDocumentAcceptanceService._build_acceptance_context(
            None, None, {"source": "signup"}
        )
        assert ctx == {"source": "signup"}

    def test_all_empty_returns_none(self):
        assert LegalDocumentAcceptanceService._build_acceptance_context(None, None, None) is None
