"""
Unit tests for user_auth auth module inputs.
"""
from lys.apps.user_auth.modules.auth.inputs import LoginInput


class TestLoginInput:
    def test_exists(self):
        assert LoginInput is not None

    def test_has_login_annotation(self):
        assert "login" in LoginInput.__annotations__

    def test_has_password_annotation(self):
        assert "password" in LoginInput.__annotations__
