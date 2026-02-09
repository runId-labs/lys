"""
Unit tests for EmailingService logic (compute_context, get_subject).
"""
from unittest.mock import Mock, patch, MagicMock


class TestComputeContext:
    """Tests for EmailingService.compute_context() — static method, no DB."""

    def test_scalar_string(self):
        from lys.apps.base.modules.emailing.services import EmailingService
        result = EmailingService.compute_context(
            {"name": None},
            name="Alice"
        )
        assert result == {"name": "Alice"}

    def test_scalar_int(self):
        from lys.apps.base.modules.emailing.services import EmailingService
        result = EmailingService.compute_context(
            {"count": None},
            count=42
        )
        assert result == {"count": 42}

    def test_scalar_float(self):
        from lys.apps.base.modules.emailing.services import EmailingService
        result = EmailingService.compute_context(
            {"rate": None},
            rate=3.14
        )
        assert result == {"rate": 3.14}

    def test_entity_attrs(self):
        from lys.apps.base.modules.emailing.services import EmailingService
        from lys.core.entities import Entity

        mock_user = Mock(spec=Entity)
        mock_user.first_name = "Alice"
        mock_user.last_name = "Smith"

        result = EmailingService.compute_context(
            {"user": ["first_name", "last_name"]},
            user=mock_user
        )
        assert result == {"first_name": "Alice", "last_name": "Smith"}

    def test_nested_entity(self):
        from lys.apps.base.modules.emailing.services import EmailingService
        from lys.core.entities import Entity

        mock_company = Mock(spec=Entity)
        mock_company.name = "Corp"

        mock_user = Mock(spec=Entity)
        mock_user.company = mock_company

        result = EmailingService.compute_context(
            {"user": [{"company": ["name"]}]},
            user=mock_user
        )
        assert result == {"company": {"name": "Corp"}}

    def test_none_value_ignored(self):
        from lys.apps.base.modules.emailing.services import EmailingService
        result = EmailingService.compute_context(
            {"user": ["first_name"]},
            user=None
        )
        assert result == {}

    def test_empty_context_description(self):
        from lys.apps.base.modules.emailing.services import EmailingService
        result = EmailingService.compute_context({})
        assert result == {}

    def test_missing_kwarg_ignored(self):
        from lys.apps.base.modules.emailing.services import EmailingService
        result = EmailingService.compute_context(
            {"user": ["first_name"]},
        )
        assert result == {}

    def test_entity_with_none_description(self):
        from lys.apps.base.modules.emailing.services import EmailingService
        from lys.core.entities import Entity

        mock_user = Mock(spec=Entity)
        result = EmailingService.compute_context(
            {"user": None},
            user=mock_user
        )
        assert result == {}

    def test_mixed_scalars_and_entities(self):
        from lys.apps.base.modules.emailing.services import EmailingService
        from lys.core.entities import Entity

        mock_user = Mock(spec=Entity)
        mock_user.email = "test@example.com"

        result = EmailingService.compute_context(
            {"user": ["email"], "token": None, "front_url": None},
            user=mock_user,
            token="abc123",
            front_url="https://app.example.com"
        )
        assert result == {
            "email": "test@example.com",
            "token": "abc123",
            "front_url": "https://app.example.com"
        }


class TestGetSubject:
    """Tests for EmailingService.get_subject() — needs mocked get_translations."""

    def test_found_in_translations(self):
        from lys.apps.base.modules.emailing.services import EmailingService
        with patch.object(EmailingService, "get_translations", return_value={
            "user_password_reset": {"subject": "Reset your password"}
        }):
            result = EmailingService.get_subject("user_password_reset", "en", "Fallback")
            assert result == "Reset your password"

    def test_fallback_when_template_not_found(self):
        from lys.apps.base.modules.emailing.services import EmailingService
        with patch.object(EmailingService, "get_translations", return_value={}):
            result = EmailingService.get_subject("unknown_template", "en", "Fallback Subject")
            assert result == "Fallback Subject"

    def test_fallback_when_no_subject_key(self):
        from lys.apps.base.modules.emailing.services import EmailingService
        with patch.object(EmailingService, "get_translations", return_value={
            "user_password_reset": {"body": "Some body text"}
        }):
            result = EmailingService.get_subject("user_password_reset", "en", "Default Subject")
            assert result == "Default Subject"
