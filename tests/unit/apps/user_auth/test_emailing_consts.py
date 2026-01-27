"""
Unit tests for user_auth emailing module constants.

Tests emailing type constants.
"""

import pytest


class TestEmailingTypeConstants:
    """Tests for emailing type constants."""

    def test_user_password_reset_emailing_type(self):
        """Test USER_PASSWORD_RESET_EMAILING_TYPE constant."""
        from lys.apps.user_auth.modules.emailing.consts import USER_PASSWORD_RESET_EMAILING_TYPE
        assert USER_PASSWORD_RESET_EMAILING_TYPE == "USER_PASSWORD_RESET"

    def test_user_email_verification_emailing_type(self):
        """Test USER_EMAIL_VERIFICATION_EMAILING_TYPE constant."""
        from lys.apps.user_auth.modules.emailing.consts import USER_EMAIL_VERIFICATION_EMAILING_TYPE
        assert USER_EMAIL_VERIFICATION_EMAILING_TYPE == "USER_EMAIL_VERIFICATION"
