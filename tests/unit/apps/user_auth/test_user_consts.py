"""
Unit tests for user_auth user module constants.

Tests user status, gender, and log type constants.
"""

import pytest


class TestUserStatusConstants:
    """Tests for user status constants."""

    def test_enabled_user_status(self):
        """Test ENABLED_USER_STATUS constant."""
        from lys.apps.user_auth.modules.user.consts import ENABLED_USER_STATUS
        assert ENABLED_USER_STATUS == "ENABLED"

    def test_disabled_user_status(self):
        """Test DISABLED_USER_STATUS constant."""
        from lys.apps.user_auth.modules.user.consts import DISABLED_USER_STATUS
        assert DISABLED_USER_STATUS == "DISABLED"

    def test_revoked_user_status(self):
        """Test REVOKED_USER_STATUS constant."""
        from lys.apps.user_auth.modules.user.consts import REVOKED_USER_STATUS
        assert REVOKED_USER_STATUS == "REVOKED"

    def test_deleted_user_status(self):
        """Test DELETED_USER_STATUS constant."""
        from lys.apps.user_auth.modules.user.consts import DELETED_USER_STATUS
        assert DELETED_USER_STATUS == "DELETED"


class TestGenderConstants:
    """Tests for gender constants."""

    def test_male_gender(self):
        """Test MALE_GENDER constant."""
        from lys.apps.user_auth.modules.user.consts import MALE_GENDER
        assert MALE_GENDER == "MALE"

    def test_female_gender(self):
        """Test FEMALE_GENDER constant."""
        from lys.apps.user_auth.modules.user.consts import FEMALE_GENDER
        assert FEMALE_GENDER == "FEMALE"

    def test_other_gender(self):
        """Test OTHER_GENDER constant."""
        from lys.apps.user_auth.modules.user.consts import OTHER_GENDER
        assert OTHER_GENDER == "OTHER"


class TestLogTypeConstants:
    """Tests for log type constants."""

    def test_status_change_log_type(self):
        """Test STATUS_CHANGE_LOG_TYPE constant."""
        from lys.apps.user_auth.modules.user.consts import STATUS_CHANGE_LOG_TYPE
        assert STATUS_CHANGE_LOG_TYPE == "STATUS_CHANGE"

    def test_anonymization_log_type(self):
        """Test ANONYMIZATION_LOG_TYPE constant."""
        from lys.apps.user_auth.modules.user.consts import ANONYMIZATION_LOG_TYPE
        assert ANONYMIZATION_LOG_TYPE == "ANONYMIZATION"

    def test_observation_log_type(self):
        """Test OBSERVATION_LOG_TYPE constant."""
        from lys.apps.user_auth.modules.user.consts import OBSERVATION_LOG_TYPE
        assert OBSERVATION_LOG_TYPE == "OBSERVATION"


class TestErrorConstants:
    """Tests for error constants."""

    def test_not_super_user_error(self):
        """Test NOT_SUPER_USER error constant."""
        from lys.apps.user_auth.modules.user.consts import NOT_SUPER_USER

        assert isinstance(NOT_SUPER_USER, tuple)
        assert NOT_SUPER_USER[0] == 403
        assert NOT_SUPER_USER[1] == "NOT_SUPER_USER"
