"""
Unit tests for licensing rule validators.

Tests validator function existence, signatures, and behavior.
"""

import inspect

import pytest

pytest.importorskip("mollie", reason="mollie package not installed")

from lys.apps.licensing.modules.rule.validators import validate_max_users
from lys.apps.licensing.consts import MAX_USERS


class TestValidatorsExist:
    """Tests that validator functions exist and are callable."""

    def test_validate_max_users_exists(self):
        assert validate_max_users is not None

    def test_validate_max_users_is_callable(self):
        assert callable(validate_max_users)


class TestValidatorsAreAsync:
    """Tests that validators are async functions."""

    def test_validate_max_users_is_async(self):
        assert inspect.iscoroutinefunction(validate_max_users)


class TestValidatorSignatures:
    """Tests for validator function parameter signatures."""

    def test_validate_max_users_params(self):
        sig = inspect.signature(validate_max_users)
        params = list(sig.parameters.keys())
        assert "session" in params
        assert "client_id" in params
        assert "app_id" in params
        assert "limit_value" in params


class TestShippedValidators:
    """The framework only ships validators it can actually implement."""

    def test_seat_counting_is_the_only_shipped_quota(self):
        """
        A quota lys cannot count belongs to the application: shipping a
        placeholder validator that always passes would silently grant it.
        """
        from lys.apps.licensing.modules.rule import validators

        shipped = [
            name for name in dir(validators)
            if name.startswith("validate_")
        ]
        assert shipped == ["validate_max_users"]


class TestRuleConstants:
    """Tests for rule constant values used by validators."""

    def test_max_users_is_string(self):
        assert isinstance(MAX_USERS, str)
