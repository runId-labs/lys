"""
Unit tests for UserService logic (reset_password, verify_email, update_status, anonymize_user).

Isolation: All tests use inline imports + patch.object. No global state modified.
"""
import pytest
from unittest.mock import AsyncMock, Mock, patch, MagicMock


class TestResetPassword:
    """Tests for UserService.reset_password()."""

    @pytest.mark.asyncio
    async def test_invalid_token_raises(self):
        from lys.apps.user_auth.modules.user.services import UserService
        from lys.core.errors import LysError

        mock_session = AsyncMock()
        mock_token_service = AsyncMock()
        mock_token_service.get_by_id = AsyncMock(return_value=None)

        with patch.object(UserService, "app_manager", create=True) as mock_am:
            mock_am.get_service.return_value = mock_token_service
            with pytest.raises(LysError, match="INVALID_RESET_TOKEN_ERROR"):
                await UserService.reset_password("bad-token", "newpass", mock_session)

    @pytest.mark.asyncio
    async def test_wrong_token_type_raises(self):
        from lys.apps.user_auth.modules.user.services import UserService
        from lys.core.errors import LysError

        mock_session = AsyncMock()
        mock_token = Mock()
        mock_token.type_id = "EMAIL_VERIFICATION"
        mock_token.is_expired = False
        mock_token.is_used = False

        mock_token_service = AsyncMock()
        mock_token_service.get_by_id = AsyncMock(return_value=mock_token)

        with patch.object(UserService, "app_manager", create=True) as mock_am:
            mock_am.get_service.return_value = mock_token_service
            with pytest.raises(LysError, match="INVALID_RESET_TOKEN_ERROR"):
                await UserService.reset_password("token-id", "newpass", mock_session)

    @pytest.mark.asyncio
    async def test_expired_token_raises(self):
        from lys.apps.user_auth.modules.user.services import UserService
        from lys.apps.base.modules.one_time_token.consts import PASSWORD_RESET_TOKEN_TYPE
        from lys.core.errors import LysError

        mock_session = AsyncMock()
        mock_token = Mock()
        mock_token.type_id = PASSWORD_RESET_TOKEN_TYPE
        mock_token.is_expired = True
        mock_token.is_used = False

        mock_token_service = AsyncMock()
        mock_token_service.get_by_id = AsyncMock(return_value=mock_token)

        with patch.object(UserService, "app_manager", create=True) as mock_am:
            mock_am.get_service.return_value = mock_token_service
            with pytest.raises(LysError, match="EXPIRED_RESET_TOKEN_ERROR"):
                await UserService.reset_password("token-id", "newpass", mock_session)

    @pytest.mark.asyncio
    async def test_used_token_raises(self):
        from lys.apps.user_auth.modules.user.services import UserService
        from lys.apps.base.modules.one_time_token.consts import PASSWORD_RESET_TOKEN_TYPE
        from lys.core.errors import LysError

        mock_session = AsyncMock()
        mock_token = Mock()
        mock_token.type_id = PASSWORD_RESET_TOKEN_TYPE
        mock_token.is_expired = False
        mock_token.is_used = True

        mock_token_service = AsyncMock()
        mock_token_service.get_by_id = AsyncMock(return_value=mock_token)

        with patch.object(UserService, "app_manager", create=True) as mock_am:
            mock_am.get_service.return_value = mock_token_service
            with pytest.raises(LysError, match="INVALID_RESET_TOKEN_ERROR"):
                await UserService.reset_password("token-id", "newpass", mock_session)

    @pytest.mark.asyncio
    async def test_user_not_found_raises(self):
        from lys.apps.user_auth.modules.user.services import UserService
        from lys.apps.base.modules.one_time_token.consts import PASSWORD_RESET_TOKEN_TYPE
        from lys.core.errors import LysError

        mock_session = AsyncMock()
        mock_token = Mock()
        mock_token.type_id = PASSWORD_RESET_TOKEN_TYPE
        mock_token.is_expired = False
        mock_token.is_used = False
        mock_token.user_id = "user-123"

        mock_token_service = AsyncMock()
        mock_token_service.get_by_id = AsyncMock(return_value=mock_token)

        with patch.object(UserService, "app_manager", create=True) as mock_am:
            mock_am.get_service.return_value = mock_token_service
            with patch.object(UserService, "get_by_id", new_callable=AsyncMock, return_value=None):
                with pytest.raises(LysError, match="INVALID_RESET_TOKEN_ERROR"):
                    await UserService.reset_password("token-id", "newpass", mock_session)

    @pytest.mark.asyncio
    async def test_success_updates_password_and_marks_used(self):
        from lys.apps.user_auth.modules.user.services import UserService
        from lys.apps.base.modules.one_time_token.consts import PASSWORD_RESET_TOKEN_TYPE

        mock_session = AsyncMock()
        mock_token = Mock()
        mock_token.type_id = PASSWORD_RESET_TOKEN_TYPE
        mock_token.is_expired = False
        mock_token.is_used = False
        mock_token.user_id = "user-123"

        mock_user = Mock()
        mock_user.password = "old-hash"

        mock_token_service = AsyncMock()
        mock_token_service.get_by_id = AsyncMock(return_value=mock_token)
        mock_token_service.mark_as_used = AsyncMock()

        with patch.object(UserService, "app_manager", create=True) as mock_am:
            mock_am.get_service.return_value = mock_token_service
            with patch.object(UserService, "get_by_id", new_callable=AsyncMock, return_value=mock_user):
                with patch("lys.apps.user_auth.modules.user.services.AuthUtils") as MockAuthUtils:
                    MockAuthUtils.hash_password.return_value = "new-hash"
                    result = await UserService.reset_password("token-id", "newpass", mock_session)

        assert result is mock_user
        assert mock_user.password == "new-hash"
        mock_token_service.mark_as_used.assert_called_once()


class TestVerifyEmail:
    """Tests for UserService.verify_email()."""

    @pytest.mark.asyncio
    async def test_invalid_token_raises(self):
        from lys.apps.user_auth.modules.user.services import UserService
        from lys.core.errors import LysError

        mock_session = AsyncMock()
        mock_token_service = AsyncMock()
        mock_token_service.get_by_id = AsyncMock(return_value=None)

        with patch.object(UserService, "app_manager", create=True) as mock_am:
            mock_am.get_service.return_value = mock_token_service
            with pytest.raises(LysError, match="INVALID_RESET_TOKEN_ERROR"):
                await UserService.verify_email("bad-token", mock_session)

    @pytest.mark.asyncio
    async def test_wrong_type_raises(self):
        from lys.apps.user_auth.modules.user.services import UserService
        from lys.core.errors import LysError

        mock_session = AsyncMock()
        mock_token = Mock()
        mock_token.type_id = "PASSWORD_RESET"

        mock_token_service = AsyncMock()
        mock_token_service.get_by_id = AsyncMock(return_value=mock_token)

        with patch.object(UserService, "app_manager", create=True) as mock_am:
            mock_am.get_service.return_value = mock_token_service
            with pytest.raises(LysError, match="INVALID_RESET_TOKEN_ERROR"):
                await UserService.verify_email("token-id", mock_session)

    @pytest.mark.asyncio
    async def test_already_validated_raises(self):
        from lys.apps.user_auth.modules.user.services import UserService
        from lys.apps.base.modules.one_time_token.consts import EMAIL_VERIFICATION_TOKEN_TYPE
        from lys.core.errors import LysError
        from datetime import datetime

        mock_session = AsyncMock()
        mock_token = Mock()
        mock_token.type_id = EMAIL_VERIFICATION_TOKEN_TYPE
        mock_token.is_expired = False
        mock_token.is_used = False
        mock_token.user_id = "user-123"

        mock_email = Mock()
        mock_email.validated_at = datetime(2024, 1, 1)
        mock_email.id = "test@test.com"

        mock_user = Mock()
        mock_user.email_address = mock_email

        mock_token_service = AsyncMock()
        mock_token_service.get_by_id = AsyncMock(return_value=mock_token)

        with patch.object(UserService, "app_manager", create=True) as mock_am:
            mock_am.get_service.return_value = mock_token_service
            with patch.object(UserService, "get_by_id", new_callable=AsyncMock, return_value=mock_user):
                with pytest.raises(LysError, match="EMAIL_ALREADY_VALIDATED_ERROR"):
                    await UserService.verify_email("token-id", mock_session)

    @pytest.mark.asyncio
    async def test_success_sets_validated_at(self):
        from lys.apps.user_auth.modules.user.services import UserService
        from lys.apps.base.modules.one_time_token.consts import EMAIL_VERIFICATION_TOKEN_TYPE

        mock_session = AsyncMock()
        mock_token = Mock()
        mock_token.type_id = EMAIL_VERIFICATION_TOKEN_TYPE
        mock_token.is_expired = False
        mock_token.is_used = False
        mock_token.user_id = "user-123"

        mock_email = Mock()
        mock_email.validated_at = None

        mock_user = Mock()
        mock_user.email_address = mock_email

        mock_token_service = AsyncMock()
        mock_token_service.get_by_id = AsyncMock(return_value=mock_token)
        mock_token_service.mark_as_used = AsyncMock()

        with patch.object(UserService, "app_manager", create=True) as mock_am:
            mock_am.get_service.return_value = mock_token_service
            with patch.object(UserService, "get_by_id", new_callable=AsyncMock, return_value=mock_user):
                result = await UserService.verify_email("token-id", mock_session)

        assert result is mock_user
        assert mock_email.validated_at is not None
        mock_token_service.mark_as_used.assert_called_once()


class TestUpdateStatus:
    """Tests for UserService.update_status()."""

    @pytest.mark.asyncio
    async def test_deleted_status_raises(self):
        from lys.apps.user_auth.modules.user.services import UserService
        from lys.core.errors import LysError

        mock_session = AsyncMock()
        mock_user = Mock()
        with patch.object(UserService, "app_manager", create=True):
            with pytest.raises(LysError, match="INVALID_STATUS_CHANGE"):
                await UserService.update_status(mock_user, "DELETED", "reason", "author-1", mock_session)

    @pytest.mark.asyncio
    async def test_invalid_status_raises(self):
        from lys.apps.user_auth.modules.user.services import UserService
        from lys.core.errors import LysError

        mock_session = AsyncMock()
        mock_user = Mock()

        mock_status_service = AsyncMock()
        mock_status_service.get_by_id = AsyncMock(return_value=None)

        with patch.object(UserService, "app_manager", create=True) as mock_am:
            mock_am.get_service.side_effect = lambda name: {
                "user_status": mock_status_service,
            }.get(name)
            with pytest.raises(LysError, match="INVALID_USER_STATUS"):
                await UserService.update_status(mock_user, "INVALID", "reason", "author-1", mock_session)

    @pytest.mark.asyncio
    async def test_success_updates_and_creates_audit_log(self):
        from lys.apps.user_auth.modules.user.services import UserService

        mock_session = AsyncMock()
        mock_user = Mock()
        mock_user.id = "user-123"
        mock_user.status_id = "ENABLED"

        mock_status = Mock()
        mock_status_service = AsyncMock()
        mock_status_service.get_by_id = AsyncMock(return_value=mock_status)

        mock_audit_service = AsyncMock()
        mock_audit_service.create_audit_log = AsyncMock()

        with patch.object(UserService, "app_manager", create=True) as mock_am:
            mock_am.get_service.side_effect = lambda name: {
                "user_status": mock_status_service,
                "user_audit_log": mock_audit_service,
            }.get(name)
            result = await UserService.update_status(
                mock_user, "DISABLED", "bad behavior", "admin-1", mock_session
            )

        assert result is mock_user
        assert mock_user.status_id == "DISABLED"
        mock_audit_service.create_audit_log.assert_called_once()
        call_kwargs = mock_audit_service.create_audit_log.call_args[1]
        assert "ENABLED" in call_kwargs["message"]
        assert "DISABLED" in call_kwargs["message"]


class TestAnonymizeUser:
    """Tests for UserService.anonymize_user()."""

    @pytest.mark.asyncio
    async def test_user_not_found_raises(self):
        from lys.apps.user_auth.modules.user.services import UserService
        from lys.core.errors import LysError

        mock_session = AsyncMock()
        with patch.object(UserService, "get_by_id", new_callable=AsyncMock, return_value=None):
            with patch.object(UserService, "app_manager", create=True):
                with pytest.raises(LysError, match="USER_NOT_FOUND"):
                    await UserService.anonymize_user("user-123", "gdpr", "admin-1", mock_session)

    @pytest.mark.asyncio
    async def test_already_anonymized_raises(self):
        from lys.apps.user_auth.modules.user.services import UserService
        from lys.core.errors import LysError
        from datetime import datetime

        mock_session = AsyncMock()
        mock_private_data = Mock()
        mock_private_data.anonymized_at = datetime(2024, 1, 1)
        mock_user = Mock()
        mock_user.private_data = mock_private_data

        with patch.object(UserService, "get_by_id", new_callable=AsyncMock, return_value=mock_user):
            with patch.object(UserService, "app_manager", create=True):
                with pytest.raises(LysError, match="USER_ALREADY_ANONYMIZED"):
                    await UserService.anonymize_user("user-123", "gdpr", "admin-1", mock_session)

    @pytest.mark.asyncio
    async def test_success_anonymizes_data(self):
        from lys.apps.user_auth.modules.user.services import UserService

        mock_session = AsyncMock()
        mock_private_data = Mock()
        mock_private_data.anonymized_at = None
        mock_private_data.first_name = "Alice"
        mock_private_data.last_name = "Smith"
        mock_private_data.gender_id = "F"

        mock_user = Mock()
        mock_user.id = "user-123"
        mock_user.private_data = mock_private_data
        mock_user.status_id = "ENABLED"

        mock_audit_service = AsyncMock()
        mock_audit_service.create_audit_log = AsyncMock()

        with patch.object(UserService, "get_by_id", new_callable=AsyncMock, return_value=mock_user):
            with patch.object(UserService, "app_manager", create=True) as mock_am:
                mock_am.get_service.return_value = mock_audit_service
                await UserService.anonymize_user("user-123", "gdpr", "admin-1", mock_session)

        assert mock_user.status_id == "DELETED"
        assert mock_private_data.first_name is None
        assert mock_private_data.last_name is None
        assert mock_private_data.gender_id is None
        assert mock_private_data.anonymized_at is not None
