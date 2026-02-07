"""
Unit tests for user_auth user services structure (method signatures, inheritance).
"""
import inspect


class TestUserStatusServiceStructure:
    """Tests for UserStatusService class structure."""

    def test_service_exists(self):
        from lys.apps.user_auth.modules.user.services import UserStatusService
        assert UserStatusService is not None

    def test_inherits_from_entity_service(self):
        from lys.apps.user_auth.modules.user.services import UserStatusService
        from lys.core.services import EntityService
        assert issubclass(UserStatusService, EntityService)


class TestGenderServiceStructure:
    """Tests for GenderService class structure."""

    def test_service_exists(self):
        from lys.apps.user_auth.modules.user.services import GenderService
        assert GenderService is not None

    def test_inherits_from_entity_service(self):
        from lys.apps.user_auth.modules.user.services import GenderService
        from lys.core.services import EntityService
        assert issubclass(GenderService, EntityService)


class TestUserEmailAddressServiceStructure:
    """Tests for UserEmailAddressService class structure."""

    def test_service_exists(self):
        from lys.apps.user_auth.modules.user.services import UserEmailAddressService
        assert UserEmailAddressService is not None

    def test_inherits_from_entity_service(self):
        from lys.apps.user_auth.modules.user.services import UserEmailAddressService
        from lys.core.services import EntityService
        assert issubclass(UserEmailAddressService, EntityService)


class TestUserPrivateDataServiceStructure:
    """Tests for UserPrivateDataService class structure."""

    def test_service_exists(self):
        from lys.apps.user_auth.modules.user.services import UserPrivateDataService
        assert UserPrivateDataService is not None

    def test_inherits_from_entity_service(self):
        from lys.apps.user_auth.modules.user.services import UserPrivateDataService
        from lys.core.services import EntityService
        assert issubclass(UserPrivateDataService, EntityService)


class TestUserServiceStructure:
    """Tests for UserService class structure."""

    def test_service_exists(self):
        from lys.apps.user_auth.modules.user.services import UserService
        assert UserService is not None

    def test_has_check_password(self):
        from lys.apps.user_auth.modules.user.services import UserService
        assert hasattr(UserService, "check_password")

    def test_has_get_by_email(self):
        from lys.apps.user_auth.modules.user.services import UserService
        assert hasattr(UserService, "get_by_email")
        assert inspect.iscoroutinefunction(UserService.get_by_email)

    def test_has_create_user(self):
        from lys.apps.user_auth.modules.user.services import UserService
        assert hasattr(UserService, "create_user")
        assert inspect.iscoroutinefunction(UserService.create_user)

    def test_has_create_super_user(self):
        from lys.apps.user_auth.modules.user.services import UserService
        assert hasattr(UserService, "create_super_user")
        assert inspect.iscoroutinefunction(UserService.create_super_user)

    def test_has_send_email_verification(self):
        from lys.apps.user_auth.modules.user.services import UserService
        assert hasattr(UserService, "send_email_verification")
        assert inspect.iscoroutinefunction(UserService.send_email_verification)

    def test_has_request_password_reset(self):
        from lys.apps.user_auth.modules.user.services import UserService
        assert hasattr(UserService, "request_password_reset")
        assert inspect.iscoroutinefunction(UserService.request_password_reset)

    def test_has_reset_password(self):
        from lys.apps.user_auth.modules.user.services import UserService
        assert hasattr(UserService, "reset_password")
        assert inspect.iscoroutinefunction(UserService.reset_password)

    def test_has_verify_email(self):
        from lys.apps.user_auth.modules.user.services import UserService
        assert hasattr(UserService, "verify_email")
        assert inspect.iscoroutinefunction(UserService.verify_email)

    def test_has_activate_user(self):
        from lys.apps.user_auth.modules.user.services import UserService
        assert hasattr(UserService, "activate_user")
        assert inspect.iscoroutinefunction(UserService.activate_user)

    def test_has_send_invitation_email(self):
        from lys.apps.user_auth.modules.user.services import UserService
        assert hasattr(UserService, "send_invitation_email")
        assert inspect.iscoroutinefunction(UserService.send_invitation_email)

    def test_has_update_email(self):
        from lys.apps.user_auth.modules.user.services import UserService
        assert hasattr(UserService, "update_email")
        assert inspect.iscoroutinefunction(UserService.update_email)

    def test_has_update_password(self):
        from lys.apps.user_auth.modules.user.services import UserService
        assert hasattr(UserService, "update_password")
        assert inspect.iscoroutinefunction(UserService.update_password)

    def test_has_update_user(self):
        from lys.apps.user_auth.modules.user.services import UserService
        assert hasattr(UserService, "update_user")
        assert inspect.iscoroutinefunction(UserService.update_user)

    def test_has_update_status(self):
        from lys.apps.user_auth.modules.user.services import UserService
        assert hasattr(UserService, "update_status")
        assert inspect.iscoroutinefunction(UserService.update_status)

    def test_has_anonymize_user(self):
        from lys.apps.user_auth.modules.user.services import UserService
        assert hasattr(UserService, "anonymize_user")
        assert inspect.iscoroutinefunction(UserService.anonymize_user)


class TestUserRefreshTokenServiceStructure:
    """Tests for UserRefreshTokenService class structure."""

    def test_service_exists(self):
        from lys.apps.user_auth.modules.user.services import UserRefreshTokenService
        assert UserRefreshTokenService is not None

    def test_has_generate_method(self):
        from lys.apps.user_auth.modules.user.services import UserRefreshTokenService
        assert hasattr(UserRefreshTokenService, "generate")
        assert inspect.iscoroutinefunction(UserRefreshTokenService.generate)

    def test_has_get_method(self):
        from lys.apps.user_auth.modules.user.services import UserRefreshTokenService
        assert hasattr(UserRefreshTokenService, "get")
        assert inspect.iscoroutinefunction(UserRefreshTokenService.get)

    def test_has_revoke_method(self):
        from lys.apps.user_auth.modules.user.services import UserRefreshTokenService
        assert hasattr(UserRefreshTokenService, "revoke")
        assert inspect.iscoroutinefunction(UserRefreshTokenService.revoke)

    def test_has_refresh_method(self):
        from lys.apps.user_auth.modules.user.services import UserRefreshTokenService
        assert hasattr(UserRefreshTokenService, "refresh")
        assert inspect.iscoroutinefunction(UserRefreshTokenService.refresh)


class TestUserOneTimeTokenServiceStructure:
    """Tests for UserOneTimeTokenService class structure."""

    def test_service_exists(self):
        from lys.apps.user_auth.modules.user.services import UserOneTimeTokenService
        assert UserOneTimeTokenService is not None


class TestUserEmailingServiceStructure:
    """Tests for UserEmailingService class structure."""

    def test_service_exists(self):
        from lys.apps.user_auth.modules.user.services import UserEmailingService
        assert UserEmailingService is not None

    def test_has_create_password_reset_emailing(self):
        from lys.apps.user_auth.modules.user.services import UserEmailingService
        assert hasattr(UserEmailingService, "create_password_reset_emailing")
        assert inspect.iscoroutinefunction(UserEmailingService.create_password_reset_emailing)

    def test_has_create_email_verification_emailing(self):
        from lys.apps.user_auth.modules.user.services import UserEmailingService
        assert hasattr(UserEmailingService, "create_email_verification_emailing")
        assert inspect.iscoroutinefunction(UserEmailingService.create_email_verification_emailing)

    def test_has_create_invitation_emailing(self):
        from lys.apps.user_auth.modules.user.services import UserEmailingService
        assert hasattr(UserEmailingService, "create_invitation_emailing")
        assert inspect.iscoroutinefunction(UserEmailingService.create_invitation_emailing)

    def test_has_schedule_send_emailing(self):
        from lys.apps.user_auth.modules.user.services import UserEmailingService
        assert hasattr(UserEmailingService, "schedule_send_emailing")
        assert callable(UserEmailingService.schedule_send_emailing)


class TestUserAuditLogTypeServiceStructure:
    """Tests for UserAuditLogTypeService class structure."""

    def test_service_exists(self):
        from lys.apps.user_auth.modules.user.services import UserAuditLogTypeService
        assert UserAuditLogTypeService is not None


class TestUserAuditLogServiceStructure:
    """Tests for UserAuditLogService class structure."""

    def test_service_exists(self):
        from lys.apps.user_auth.modules.user.services import UserAuditLogService
        assert UserAuditLogService is not None

    def test_has_create_audit_log(self):
        from lys.apps.user_auth.modules.user.services import UserAuditLogService
        assert hasattr(UserAuditLogService, "create_audit_log")
        assert inspect.iscoroutinefunction(UserAuditLogService.create_audit_log)

    def test_has_list_audit_logs(self):
        from lys.apps.user_auth.modules.user.services import UserAuditLogService
        assert hasattr(UserAuditLogService, "list_audit_logs")
        assert callable(UserAuditLogService.list_audit_logs)
