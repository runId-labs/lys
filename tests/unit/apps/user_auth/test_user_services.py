"""
Unit tests for user_auth user module services.

Tests service structure and method signatures.
"""

import pytest
import inspect


class TestUserServiceStructure:
    """Tests for UserService class structure."""

    def test_service_exists(self):
        """Test UserService class exists."""
        from lys.apps.user_auth.modules.user.services import UserService
        assert UserService is not None

    def test_service_inherits_from_entity_service(self):
        """Test UserService inherits from EntityService."""
        from lys.apps.user_auth.modules.user.services import UserService
        from lys.core.services import EntityService
        assert issubclass(UserService, EntityService)


class TestUserServiceMethods:
    """Tests for UserService methods."""

    def test_get_by_email_exists(self):
        """Test get_by_email method exists."""
        from lys.apps.user_auth.modules.user.services import UserService
        assert hasattr(UserService, "get_by_email")

    def test_get_by_email_is_async(self):
        """Test get_by_email is async."""
        from lys.apps.user_auth.modules.user.services import UserService
        assert inspect.iscoroutinefunction(UserService.get_by_email)

    def test_get_by_email_signature(self):
        """Test get_by_email method signature."""
        from lys.apps.user_auth.modules.user.services import UserService

        sig = inspect.signature(UserService.get_by_email)
        assert "email" in sig.parameters
        assert "session" in sig.parameters

    def test_create_user_exists(self):
        """Test create_user method exists."""
        from lys.apps.user_auth.modules.user.services import UserService
        assert hasattr(UserService, "create_user")

    def test_create_user_is_async(self):
        """Test create_user is async."""
        from lys.apps.user_auth.modules.user.services import UserService
        assert inspect.iscoroutinefunction(UserService.create_user)

    def test_create_user_signature(self):
        """Test create_user method signature."""
        from lys.apps.user_auth.modules.user.services import UserService

        sig = inspect.signature(UserService.create_user)
        assert "session" in sig.parameters
        assert "email" in sig.parameters
        assert "password" in sig.parameters
        assert "language_id" in sig.parameters

    def test_update_user_exists(self):
        """Test update_user method exists."""
        from lys.apps.user_auth.modules.user.services import UserService
        assert hasattr(UserService, "update_user")

    def test_update_user_is_async(self):
        """Test update_user is async."""
        from lys.apps.user_auth.modules.user.services import UserService
        assert inspect.iscoroutinefunction(UserService.update_user)

    def test_update_email_exists(self):
        """Test update_email method exists."""
        from lys.apps.user_auth.modules.user.services import UserService
        assert hasattr(UserService, "update_email")

    def test_update_email_is_async(self):
        """Test update_email is async."""
        from lys.apps.user_auth.modules.user.services import UserService
        assert inspect.iscoroutinefunction(UserService.update_email)

    def test_update_password_exists(self):
        """Test update_password method exists."""
        from lys.apps.user_auth.modules.user.services import UserService
        assert hasattr(UserService, "update_password")

    def test_update_password_is_async(self):
        """Test update_password is async."""
        from lys.apps.user_auth.modules.user.services import UserService
        assert inspect.iscoroutinefunction(UserService.update_password)

    def test_update_status_exists(self):
        """Test update_status method exists."""
        from lys.apps.user_auth.modules.user.services import UserService
        assert hasattr(UserService, "update_status")

    def test_update_status_is_async(self):
        """Test update_status is async."""
        from lys.apps.user_auth.modules.user.services import UserService
        assert inspect.iscoroutinefunction(UserService.update_status)

    def test_send_email_verification_exists(self):
        """Test send_email_verification method exists."""
        from lys.apps.user_auth.modules.user.services import UserService
        assert hasattr(UserService, "send_email_verification")

    def test_send_email_verification_is_async(self):
        """Test send_email_verification is async."""
        from lys.apps.user_auth.modules.user.services import UserService
        assert inspect.iscoroutinefunction(UserService.send_email_verification)

    def test_anonymize_user_exists(self):
        """Test anonymize_user method exists."""
        from lys.apps.user_auth.modules.user.services import UserService
        assert hasattr(UserService, "anonymize_user")

    def test_anonymize_user_is_async(self):
        """Test anonymize_user is async."""
        from lys.apps.user_auth.modules.user.services import UserService
        assert inspect.iscoroutinefunction(UserService.anonymize_user)
