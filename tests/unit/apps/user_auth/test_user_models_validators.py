"""
Unit tests for user_auth user model validators.

Tests the Pydantic field validators for various input models.
"""
import pytest
from pydantic import ValidationError

from lys.core.errors import LysError


class TestCreateUserInputModelValidators:
    """Tests for CreateUserInputModel validators."""

    def test_email_is_lowercased_and_stripped(self):
        """Test that email is lowercased and stripped."""
        from lys.apps.user_auth.modules.user.models import CreateUserInputModel
        model = CreateUserInputModel(
            email="  Test@Example.COM  ",
            password="password123",
            language_code="en"
        )
        assert model.email == "test@example.com"

    def test_language_code_validated(self):
        """Test that language_code is validated."""
        from lys.apps.user_auth.modules.user.models import CreateUserInputModel
        model = CreateUserInputModel(
            email="test@example.com",
            password="password123",
            language_code="en"
        )
        assert model.language_code == "en"


class TestUpdateUserPrivateDataInputModelValidators:
    """Tests for UpdateUserPrivateDataInputModel validators."""

    def test_language_code_none_returns_none(self):
        """Test that None language_code is returned as None."""
        from lys.apps.user_auth.modules.user.models import UpdateUserPrivateDataInputModel
        model = UpdateUserPrivateDataInputModel(language_code=None)
        assert model.language_code is None

    def test_valid_language_code_passes(self):
        """Test that a valid language code passes validation."""
        from lys.apps.user_auth.modules.user.models import UpdateUserPrivateDataInputModel
        model = UpdateUserPrivateDataInputModel(language_code="en")
        assert model.language_code == "en"


class TestUpdateUserInputModelValidators:
    """Tests for UpdateUserInputModel validators."""

    def test_language_code_none_returns_none(self):
        """Test that None language_code is returned as None."""
        from lys.apps.user_auth.modules.user.models import UpdateUserInputModel
        model = UpdateUserInputModel(language_code=None)
        assert model.language_code is None

    def test_valid_language_code_passes(self):
        """Test that a valid language code passes validation."""
        from lys.apps.user_auth.modules.user.models import UpdateUserInputModel
        model = UpdateUserInputModel(language_code="fr")
        assert model.language_code == "fr"


class TestUpdateUserEmailInputModelValidators:
    """Tests for UpdateUserEmailInputModel validators."""

    def test_email_is_lowercased_and_stripped(self):
        """Test that email is lowercased and stripped."""
        from lys.apps.user_auth.modules.user.models import UpdateUserEmailInputModel
        model = UpdateUserEmailInputModel(new_email="  Test@Example.COM  ")
        assert model.new_email == "test@example.com"


class TestUpdateUserStatusInputModelValidators:
    """Tests for UpdateUserStatusInputModel validators."""

    def test_deleted_status_raises_error(self):
        """Test that DELETED status raises LysError."""
        from lys.apps.user_auth.modules.user.models import UpdateUserStatusInputModel
        with pytest.raises(LysError):
            UpdateUserStatusInputModel(
                status_code="DELETED",
                reason="This is a valid reason for changing status"
            )

    def test_valid_status_passes(self):
        """Test that valid status passes."""
        from lys.apps.user_auth.modules.user.models import UpdateUserStatusInputModel
        model = UpdateUserStatusInputModel(
            status_code="ACTIVE",
            reason="This is a valid reason for changing status"
        )
        assert model.status_code == "ACTIVE"


class TestAnonymizeUserInputModelValidators:
    """Tests for AnonymizeUserInputModel validators."""

    def test_reason_is_stripped(self):
        """Test that reason is stripped of whitespace."""
        from lys.apps.user_auth.modules.user.models import AnonymizeUserInputModel
        model = AnonymizeUserInputModel(reason="  This is a valid reason  ")
        assert model.reason == "This is a valid reason"

    def test_reason_without_whitespace_passes(self):
        """Test that reason without whitespace passes."""
        from lys.apps.user_auth.modules.user.models import AnonymizeUserInputModel
        model = AnonymizeUserInputModel(reason="Valid reason text here")
        assert model.reason == "Valid reason text here"


class TestUpdateUserAuditLogInputModelValidators:
    """Tests for UpdateUserAuditLogInputModel validators."""

    def test_message_is_stripped(self):
        """Test that message is stripped of whitespace."""
        from lys.apps.user_auth.modules.user.models import UpdateUserAuditLogInputModel
        model = UpdateUserAuditLogInputModel(message="  Some observation message  ")
        assert model.message == "Some observation message"


class TestListUserAuditLogsInputModelValidators:
    """Tests for ListUserAuditLogsInputModel validators."""

    def test_invalid_user_filter_raises_error(self):
        """Test that invalid user_filter value raises LysError."""
        from lys.apps.user_auth.modules.user.models import ListUserAuditLogsInputModel
        with pytest.raises(LysError):
            ListUserAuditLogsInputModel(user_filter="invalid_value")

    def test_author_user_filter_passes(self):
        """Test that 'author' user_filter passes."""
        from lys.apps.user_auth.modules.user.models import ListUserAuditLogsInputModel
        model = ListUserAuditLogsInputModel(user_filter="author")
        assert model.user_filter == "author"

    def test_target_user_filter_passes(self):
        """Test that 'target' user_filter passes."""
        from lys.apps.user_auth.modules.user.models import ListUserAuditLogsInputModel
        model = ListUserAuditLogsInputModel(user_filter="target")
        assert model.user_filter == "target"

    def test_none_user_filter_passes(self):
        """Test that None user_filter passes."""
        from lys.apps.user_auth.modules.user.models import ListUserAuditLogsInputModel
        model = ListUserAuditLogsInputModel(user_filter=None)
        assert model.user_filter is None
