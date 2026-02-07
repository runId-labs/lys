"""
Unit tests for user_auth emailing module constants.

Tests emailing type constants and their alignment with event type constants.
"""

import pytest


class TestEmailingTypeConstants:
    """Tests for emailing type constants."""

    def test_user_password_reset_emailing_type(self):
        """Test USER_PASSWORD_RESET_EMAILING_TYPE constant matches event type."""
        from lys.apps.user_auth.modules.emailing.consts import USER_PASSWORD_RESET_EMAILING_TYPE
        from lys.apps.user_auth.modules.event.consts import USER_PASSWORD_RESET_REQUESTED
        assert USER_PASSWORD_RESET_EMAILING_TYPE == "USER_PASSWORD_RESET_REQUESTED"
        assert USER_PASSWORD_RESET_EMAILING_TYPE == USER_PASSWORD_RESET_REQUESTED

    def test_user_email_verification_emailing_type(self):
        """Test USER_EMAIL_VERIFICATION_EMAILING_TYPE constant matches event type."""
        from lys.apps.user_auth.modules.emailing.consts import USER_EMAIL_VERIFICATION_EMAILING_TYPE
        from lys.apps.user_auth.modules.event.consts import USER_EMAIL_VERIFICATION_REQUESTED
        assert USER_EMAIL_VERIFICATION_EMAILING_TYPE == "USER_EMAIL_VERIFICATION_REQUESTED"
        assert USER_EMAIL_VERIFICATION_EMAILING_TYPE == USER_EMAIL_VERIFICATION_REQUESTED

    def test_user_invitation_emailing_type(self):
        """Test USER_INVITATION_EMAILING_TYPE constant matches event type."""
        from lys.apps.user_auth.modules.emailing.consts import USER_INVITATION_EMAILING_TYPE
        from lys.apps.user_auth.modules.event.consts import USER_INVITED
        assert USER_INVITATION_EMAILING_TYPE == "USER_INVITED"
        assert USER_INVITATION_EMAILING_TYPE == USER_INVITED
