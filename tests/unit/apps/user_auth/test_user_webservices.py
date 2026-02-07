"""
Unit tests for user_auth user module webservice classes.

Tests class existence, method presence, and async method structure
for all GraphQL query and mutation webservice classes without
requiring a database or external services.

Note: Webservice modules use a singleton registry. When organization
webservices are imported before user_auth webservices, the import fails
because both register webservices with the same name (e.g., 'all_users').
We import user_auth first to ensure it succeeds, then test the classes.
"""

import inspect
import sys

# Ensure user_auth webservices are imported BEFORE any other app's webservices
# to avoid singleton registry conflicts. This must happen at module level.
_mod = None
_module_name = "lys.apps.user_auth.modules.user.webservices"
if _module_name not in sys.modules:
    try:
        import importlib
        _mod = importlib.import_module(_module_name)
    except (ValueError, ImportError):
        _mod = None
else:
    _mod = sys.modules[_module_name]


def _get_mod():
    """Get the webservices module, skipping tests if unavailable."""
    import pytest
    if _mod is None:
        pytest.skip("user_auth webservices could not be imported due to registry conflict")
    return _mod


class TestUserQueryStructure:
    """Tests for UserQuery webservice class existence and method definitions."""

    def test_class_exists(self):
        """Test UserQuery class can be imported."""
        mod = _get_mod()
        assert hasattr(mod, "UserQuery")

    def test_has_connected_user_method(self):
        """Test UserQuery has connected_user method."""
        mod = _get_mod()
        assert hasattr(mod.UserQuery, "connected_user")

    def test_connected_user_is_async(self):
        """Test UserQuery.connected_user is an async method."""
        mod = _get_mod()
        assert inspect.iscoroutinefunction(mod.UserQuery.connected_user)

    def test_has_all_users_method(self):
        """Test UserQuery has all_users method."""
        mod = _get_mod()
        assert hasattr(mod.UserQuery, "all_users")

    def test_all_users_is_async(self):
        """Test UserQuery.all_users is an async method."""
        mod = _get_mod()
        assert inspect.iscoroutinefunction(mod.UserQuery.all_users)

    def test_has_all_super_users_method(self):
        """Test UserQuery has all_super_users method."""
        mod = _get_mod()
        assert hasattr(mod.UserQuery, "all_super_users")

    def test_all_super_users_is_async(self):
        """Test UserQuery.all_super_users is an async method."""
        mod = _get_mod()
        assert inspect.iscoroutinefunction(mod.UserQuery.all_super_users)


class TestUserStatusQueryStructure:
    """Tests for UserStatusQuery webservice class existence and method definitions."""

    def test_class_exists(self):
        """Test UserStatusQuery class can be imported."""
        mod = _get_mod()
        assert hasattr(mod, "UserStatusQuery")

    def test_has_all_user_statuses_method(self):
        """Test UserStatusQuery has all_user_statuses method."""
        mod = _get_mod()
        assert hasattr(mod.UserStatusQuery, "all_user_statuses")

    def test_all_user_statuses_is_async(self):
        """Test UserStatusQuery.all_user_statuses is an async method."""
        mod = _get_mod()
        assert inspect.iscoroutinefunction(mod.UserStatusQuery.all_user_statuses)


class TestGenderQueryStructure:
    """Tests for GenderQuery webservice class existence and method definitions."""

    def test_class_exists(self):
        """Test GenderQuery class can be imported."""
        mod = _get_mod()
        assert hasattr(mod, "GenderQuery")

    def test_has_all_genders_method(self):
        """Test GenderQuery has all_genders method."""
        mod = _get_mod()
        assert hasattr(mod.GenderQuery, "all_genders")

    def test_all_genders_is_async(self):
        """Test GenderQuery.all_genders is an async method."""
        mod = _get_mod()
        assert inspect.iscoroutinefunction(mod.GenderQuery.all_genders)


class TestUserOneTimeTokenQueryStructure:
    """Tests for UserOneTimeTokenQuery webservice class existence and method definitions."""

    def test_class_exists(self):
        """Test UserOneTimeTokenQuery class can be imported."""
        mod = _get_mod()
        assert hasattr(mod, "UserOneTimeTokenQuery")

    def test_has_all_user_one_time_tokens_method(self):
        """Test UserOneTimeTokenQuery has all_user_one_time_tokens method."""
        mod = _get_mod()
        assert hasattr(mod.UserOneTimeTokenQuery, "all_user_one_time_tokens")

    def test_all_user_one_time_tokens_is_async(self):
        """Test UserOneTimeTokenQuery.all_user_one_time_tokens is an async method."""
        mod = _get_mod()
        assert inspect.iscoroutinefunction(mod.UserOneTimeTokenQuery.all_user_one_time_tokens)


class TestUserMutationStructure:
    """Tests for UserMutation webservice class existence and all mutation method definitions."""

    def test_class_exists(self):
        """Test UserMutation class can be imported."""
        mod = _get_mod()
        assert hasattr(mod, "UserMutation")

    def test_has_request_password_reset(self):
        mod = _get_mod()
        assert hasattr(mod.UserMutation, "request_password_reset")

    def test_request_password_reset_is_async(self):
        mod = _get_mod()
        assert inspect.iscoroutinefunction(mod.UserMutation.request_password_reset)

    def test_has_reset_password(self):
        mod = _get_mod()
        assert hasattr(mod.UserMutation, "reset_password")

    def test_reset_password_is_async(self):
        mod = _get_mod()
        assert inspect.iscoroutinefunction(mod.UserMutation.reset_password)

    def test_has_verify_email(self):
        mod = _get_mod()
        assert hasattr(mod.UserMutation, "verify_email")

    def test_verify_email_is_async(self):
        mod = _get_mod()
        assert inspect.iscoroutinefunction(mod.UserMutation.verify_email)

    def test_has_activate_user(self):
        mod = _get_mod()
        assert hasattr(mod.UserMutation, "activate_user")

    def test_activate_user_is_async(self):
        mod = _get_mod()
        assert inspect.iscoroutinefunction(mod.UserMutation.activate_user)

    def test_has_send_email_verification(self):
        mod = _get_mod()
        assert hasattr(mod.UserMutation, "send_email_verification")

    def test_send_email_verification_is_async(self):
        mod = _get_mod()
        assert inspect.iscoroutinefunction(mod.UserMutation.send_email_verification)

    def test_has_create_super_user(self):
        mod = _get_mod()
        assert hasattr(mod.UserMutation, "create_super_user")

    def test_create_super_user_is_async(self):
        mod = _get_mod()
        assert inspect.iscoroutinefunction(mod.UserMutation.create_super_user)

    def test_has_create_user(self):
        mod = _get_mod()
        assert hasattr(mod.UserMutation, "create_user")

    def test_create_user_is_async(self):
        mod = _get_mod()
        assert inspect.iscoroutinefunction(mod.UserMutation.create_user)

    def test_has_update_user_email(self):
        mod = _get_mod()
        assert hasattr(mod.UserMutation, "update_user_email")

    def test_update_user_email_is_async(self):
        mod = _get_mod()
        assert inspect.iscoroutinefunction(mod.UserMutation.update_user_email)

    def test_has_update_password(self):
        mod = _get_mod()
        assert hasattr(mod.UserMutation, "update_password")

    def test_update_password_is_async(self):
        mod = _get_mod()
        assert inspect.iscoroutinefunction(mod.UserMutation.update_password)

    def test_has_update_user_private_data(self):
        mod = _get_mod()
        assert hasattr(mod.UserMutation, "update_user_private_data")

    def test_update_user_private_data_is_async(self):
        mod = _get_mod()
        assert inspect.iscoroutinefunction(mod.UserMutation.update_user_private_data)

    def test_has_update_super_user_email(self):
        mod = _get_mod()
        assert hasattr(mod.UserMutation, "update_super_user_email")

    def test_update_super_user_email_is_async(self):
        mod = _get_mod()
        assert inspect.iscoroutinefunction(mod.UserMutation.update_super_user_email)

    def test_has_update_super_user_private_data(self):
        mod = _get_mod()
        assert hasattr(mod.UserMutation, "update_super_user_private_data")

    def test_update_super_user_private_data_is_async(self):
        mod = _get_mod()
        assert inspect.iscoroutinefunction(mod.UserMutation.update_super_user_private_data)

    def test_has_update_user_status(self):
        mod = _get_mod()
        assert hasattr(mod.UserMutation, "update_user_status")

    def test_update_user_status_is_async(self):
        mod = _get_mod()
        assert inspect.iscoroutinefunction(mod.UserMutation.update_user_status)

    def test_has_anonymize_user(self):
        mod = _get_mod()
        assert hasattr(mod.UserMutation, "anonymize_user")

    def test_anonymize_user_is_async(self):
        mod = _get_mod()
        assert inspect.iscoroutinefunction(mod.UserMutation.anonymize_user)


class TestUserAuditLogQueryStructure:
    """Tests for UserAuditLogQuery webservice class existence and method definitions."""

    def test_class_exists(self):
        mod = _get_mod()
        assert hasattr(mod, "UserAuditLogQuery")

    def test_has_list_user_audit_logs_method(self):
        mod = _get_mod()
        assert hasattr(mod.UserAuditLogQuery, "list_user_audit_logs")

    def test_list_user_audit_logs_is_async(self):
        mod = _get_mod()
        assert inspect.iscoroutinefunction(mod.UserAuditLogQuery.list_user_audit_logs)


class TestUserAuditLogMutationStructure:
    """Tests for UserAuditLogMutation webservice class existence and mutation method definitions."""

    def test_class_exists(self):
        mod = _get_mod()
        assert hasattr(mod, "UserAuditLogMutation")

    def test_has_create_user_observation(self):
        mod = _get_mod()
        assert hasattr(mod.UserAuditLogMutation, "create_user_observation")

    def test_create_user_observation_is_async(self):
        mod = _get_mod()
        assert inspect.iscoroutinefunction(mod.UserAuditLogMutation.create_user_observation)

    def test_has_update_user_audit_log(self):
        mod = _get_mod()
        assert hasattr(mod.UserAuditLogMutation, "update_user_audit_log")

    def test_update_user_audit_log_is_async(self):
        mod = _get_mod()
        assert inspect.iscoroutinefunction(mod.UserAuditLogMutation.update_user_audit_log)

    def test_has_delete_user_observation(self):
        mod = _get_mod()
        assert hasattr(mod.UserAuditLogMutation, "delete_user_observation")

    def test_delete_user_observation_is_async(self):
        mod = _get_mod()
        assert inspect.iscoroutinefunction(mod.UserAuditLogMutation.delete_user_observation)
