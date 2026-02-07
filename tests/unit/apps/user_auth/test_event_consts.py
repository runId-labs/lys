"""
Unit tests for user_auth event type constants.
"""


class TestUserAuthEventConstants:
    """Tests for user_auth event type constants."""

    def test_user_invited_constant(self):
        from lys.apps.user_auth.modules.event.consts import USER_INVITED
        assert USER_INVITED == "USER_INVITED"

    def test_user_email_verification_requested_constant(self):
        from lys.apps.user_auth.modules.event.consts import USER_EMAIL_VERIFICATION_REQUESTED
        assert USER_EMAIL_VERIFICATION_REQUESTED == "USER_EMAIL_VERIFICATION_REQUESTED"

    def test_user_password_reset_requested_constant(self):
        from lys.apps.user_auth.modules.event.consts import USER_PASSWORD_RESET_REQUESTED
        assert USER_PASSWORD_RESET_REQUESTED == "USER_PASSWORD_RESET_REQUESTED"

    def test_all_constants_are_strings(self):
        from lys.apps.user_auth.modules.event import consts
        for name in ["USER_INVITED", "USER_EMAIL_VERIFICATION_REQUESTED",
                     "USER_PASSWORD_RESET_REQUESTED"]:
            assert isinstance(getattr(consts, name), str)

    def test_all_constants_unique(self):
        from lys.apps.user_auth.modules.event import consts
        values = [
            consts.USER_INVITED,
            consts.USER_EMAIL_VERIFICATION_REQUESTED,
            consts.USER_PASSWORD_RESET_REQUESTED,
        ]
        assert len(values) == len(set(values))
