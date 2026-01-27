"""
Unit tests for emailing constants.

Tests that all emailing status constants are properly defined.
"""

import pytest


class TestEmailingStatusConstants:
    """Tests for emailing status constants."""

    def test_waiting_emailing_status(self):
        """Test WAITING_EMAILING_STATUS is defined."""
        from lys.apps.base.modules.emailing.consts import WAITING_EMAILING_STATUS

        assert WAITING_EMAILING_STATUS == "WAITING"

    def test_sent_emailing_status(self):
        """Test SENT_EMAILING_STATUS is defined."""
        from lys.apps.base.modules.emailing.consts import SENT_EMAILING_STATUS

        assert SENT_EMAILING_STATUS == "SENT"

    def test_error_emailing_status(self):
        """Test ERROR_EMAILING_STATUS is defined."""
        from lys.apps.base.modules.emailing.consts import ERROR_EMAILING_STATUS

        assert ERROR_EMAILING_STATUS == "ERROR"


class TestEmailingConstantsConsistency:
    """Tests for emailing constants consistency."""

    def test_all_statuses_are_strings(self):
        """Test that all emailing statuses are strings."""
        from lys.apps.base.modules.emailing.consts import (
            WAITING_EMAILING_STATUS,
            SENT_EMAILING_STATUS,
            ERROR_EMAILING_STATUS,
        )

        assert isinstance(WAITING_EMAILING_STATUS, str)
        assert isinstance(SENT_EMAILING_STATUS, str)
        assert isinstance(ERROR_EMAILING_STATUS, str)

    def test_all_statuses_are_uppercase(self):
        """Test that all emailing statuses are uppercase."""
        from lys.apps.base.modules.emailing.consts import (
            WAITING_EMAILING_STATUS,
            SENT_EMAILING_STATUS,
            ERROR_EMAILING_STATUS,
        )

        assert WAITING_EMAILING_STATUS == WAITING_EMAILING_STATUS.upper()
        assert SENT_EMAILING_STATUS == SENT_EMAILING_STATUS.upper()
        assert ERROR_EMAILING_STATUS == ERROR_EMAILING_STATUS.upper()

    def test_all_statuses_are_unique(self):
        """Test that all emailing statuses have unique values."""
        from lys.apps.base.modules.emailing.consts import (
            WAITING_EMAILING_STATUS,
            SENT_EMAILING_STATUS,
            ERROR_EMAILING_STATUS,
        )

        statuses = [WAITING_EMAILING_STATUS, SENT_EMAILING_STATUS, ERROR_EMAILING_STATUS]
        assert len(statuses) == len(set(statuses))
