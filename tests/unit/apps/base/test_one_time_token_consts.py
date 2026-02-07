"""
Unit tests for one-time token constants.

Tests that all token type and status constants are properly defined.
"""

import pytest


class TestTokenTypeConstants:
    """Tests for token type constants."""

    def test_password_reset_token_type(self):
        """Test PASSWORD_RESET_TOKEN_TYPE is defined."""
        from lys.apps.base.modules.one_time_token.consts import PASSWORD_RESET_TOKEN_TYPE

        assert PASSWORD_RESET_TOKEN_TYPE == "password_reset"

    def test_email_verification_token_type(self):
        """Test EMAIL_VERIFICATION_TOKEN_TYPE is defined."""
        from lys.apps.base.modules.one_time_token.consts import EMAIL_VERIFICATION_TOKEN_TYPE

        assert EMAIL_VERIFICATION_TOKEN_TYPE == "email_verification"

    def test_activation_token_type(self):
        """Test ACTIVATION_TOKEN_TYPE is defined."""
        from lys.apps.base.modules.one_time_token.consts import ACTIVATION_TOKEN_TYPE

        assert ACTIVATION_TOKEN_TYPE == "activation"


class TestTokenStatusConstants:
    """Tests for token status constants."""

    def test_pending_token_status(self):
        """Test PENDING_TOKEN_STATUS is defined."""
        from lys.apps.base.modules.one_time_token.consts import PENDING_TOKEN_STATUS

        assert PENDING_TOKEN_STATUS == "pending"

    def test_used_token_status(self):
        """Test USED_TOKEN_STATUS is defined."""
        from lys.apps.base.modules.one_time_token.consts import USED_TOKEN_STATUS

        assert USED_TOKEN_STATUS == "used"

    def test_revoked_token_status(self):
        """Test REVOKED_TOKEN_STATUS is defined."""
        from lys.apps.base.modules.one_time_token.consts import REVOKED_TOKEN_STATUS

        assert REVOKED_TOKEN_STATUS == "revoked"


class TestTokenConstantsConsistency:
    """Tests for token constants consistency."""

    def test_all_token_types_are_strings(self):
        """Test that all token types are strings."""
        from lys.apps.base.modules.one_time_token.consts import (
            PASSWORD_RESET_TOKEN_TYPE,
            EMAIL_VERIFICATION_TOKEN_TYPE,
            ACTIVATION_TOKEN_TYPE,
        )

        assert isinstance(PASSWORD_RESET_TOKEN_TYPE, str)
        assert isinstance(EMAIL_VERIFICATION_TOKEN_TYPE, str)
        assert isinstance(ACTIVATION_TOKEN_TYPE, str)

    def test_all_token_statuses_are_strings(self):
        """Test that all token statuses are strings."""
        from lys.apps.base.modules.one_time_token.consts import (
            PENDING_TOKEN_STATUS,
            USED_TOKEN_STATUS,
            REVOKED_TOKEN_STATUS,
        )

        assert isinstance(PENDING_TOKEN_STATUS, str)
        assert isinstance(USED_TOKEN_STATUS, str)
        assert isinstance(REVOKED_TOKEN_STATUS, str)

    def test_token_types_are_unique(self):
        """Test that all token types have unique values."""
        from lys.apps.base.modules.one_time_token.consts import (
            PASSWORD_RESET_TOKEN_TYPE,
            EMAIL_VERIFICATION_TOKEN_TYPE,
            ACTIVATION_TOKEN_TYPE,
        )

        token_types = [PASSWORD_RESET_TOKEN_TYPE, EMAIL_VERIFICATION_TOKEN_TYPE, ACTIVATION_TOKEN_TYPE]
        assert len(token_types) == len(set(token_types))

    def test_token_statuses_are_unique(self):
        """Test that all token statuses have unique values."""
        from lys.apps.base.modules.one_time_token.consts import (
            PENDING_TOKEN_STATUS,
            USED_TOKEN_STATUS,
            REVOKED_TOKEN_STATUS,
        )

        token_statuses = [PENDING_TOKEN_STATUS, USED_TOKEN_STATUS, REVOKED_TOKEN_STATUS]
        assert len(token_statuses) == len(set(token_statuses))
