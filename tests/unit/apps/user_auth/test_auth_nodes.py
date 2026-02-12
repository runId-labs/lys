"""
Unit tests for user_auth auth module nodes.
"""
from lys.apps.user_auth.modules.auth.nodes import LoginNode, RefreshTokenNode, LogoutNode


class TestLoginNode:
    def test_exists(self):
        assert LoginNode is not None

    def test_has_success_field(self):
        assert "success" in LoginNode.__annotations__

    def test_has_message_field(self):
        assert "message" in LoginNode.__annotations__

    def test_has_access_token_expire_in_field(self):
        assert "access_token_expire_in" in LoginNode.__annotations__

    def test_has_xsrf_token_field(self):
        assert "xsrf_token" in LoginNode.__annotations__


class TestRefreshTokenNode:
    def test_exists(self):
        assert RefreshTokenNode is not None

    def test_has_message_field(self):
        assert "message" in RefreshTokenNode.__annotations__

    def test_has_access_token_expire_in_field(self):
        assert "access_token_expire_in" in RefreshTokenNode.__annotations__

    def test_has_xsrf_token_field(self):
        assert "xsrf_token" in RefreshTokenNode.__annotations__


class TestLogoutNode:
    def test_exists(self):
        assert LogoutNode is not None

    def test_has_succeed_field(self):
        assert "succeed" in LogoutNode.__annotations__

    def test_has_message_field(self):
        assert "message" in LogoutNode.__annotations__
