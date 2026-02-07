"""
Unit tests for licensing rule validators.

Tests validator function existence, signatures, and behavior.
"""

import inspect

import pytest

pytest.importorskip("mollie", reason="mollie package not installed")

from lys.apps.licensing.modules.rule.validators import (
    validate_max_users,
    validate_max_projects_per_month,
)
from lys.apps.licensing.consts import MAX_USERS, MAX_PROJECTS_PER_MONTH


class TestValidatorsExist:
    """Tests that validator functions exist and are callable."""

    def test_validate_max_users_exists(self):
        assert validate_max_users is not None

    def test_validate_max_users_is_callable(self):
        assert callable(validate_max_users)

    def test_validate_max_projects_per_month_exists(self):
        assert validate_max_projects_per_month is not None

    def test_validate_max_projects_per_month_is_callable(self):
        assert callable(validate_max_projects_per_month)


class TestValidatorsAreAsync:
    """Tests that validators are async functions."""

    def test_validate_max_users_is_async(self):
        assert inspect.iscoroutinefunction(validate_max_users)

    def test_validate_max_projects_per_month_is_async(self):
        assert inspect.iscoroutinefunction(validate_max_projects_per_month)


class TestValidatorSignatures:
    """Tests for validator function parameter signatures."""

    def test_validate_max_users_params(self):
        sig = inspect.signature(validate_max_users)
        params = list(sig.parameters.keys())
        assert "session" in params
        assert "client_id" in params
        assert "app_id" in params
        assert "limit_value" in params

    def test_validate_max_projects_per_month_params(self):
        sig = inspect.signature(validate_max_projects_per_month)
        params = list(sig.parameters.keys())
        assert "session" in params
        assert "client_id" in params
        assert "app_id" in params
        assert "limit_value" in params


class TestValidateMaxProjectsPerMonth:
    """Tests for validate_max_projects_per_month placeholder behavior."""

    @pytest.mark.asyncio
    async def test_unlimited_returns_minus_one(self):
        result = await validate_max_projects_per_month(
            session=None, client_id="c1", app_id="app1", limit_value=None
        )
        assert result == (True, 0, -1)

    @pytest.mark.asyncio
    async def test_with_limit_returns_valid(self):
        result = await validate_max_projects_per_month(
            session=None, client_id="c1", app_id="app1", limit_value=10
        )
        assert result == (True, 0, 10)

    @pytest.mark.asyncio
    async def test_returns_tuple_of_three(self):
        result = await validate_max_projects_per_month(
            session=None, client_id="c1", app_id="app1", limit_value=5
        )
        assert isinstance(result, tuple)
        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_first_element_is_bool(self):
        result = await validate_max_projects_per_month(
            session=None, client_id="c1", app_id="app1", limit_value=5
        )
        assert isinstance(result[0], bool)

    @pytest.mark.asyncio
    async def test_second_element_is_int(self):
        result = await validate_max_projects_per_month(
            session=None, client_id="c1", app_id="app1", limit_value=5
        )
        assert isinstance(result[1], int)


class TestRuleConstants:
    """Tests for rule constant values used by validators."""

    def test_max_users_is_string(self):
        assert isinstance(MAX_USERS, str)

    def test_max_projects_per_month_is_string(self):
        assert isinstance(MAX_PROJECTS_PER_MONTH, str)
