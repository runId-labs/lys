"""
Unit tests for user_auth auth module Pydantic models.

Tests input validation and model structure.
"""

import pytest
from pydantic import ValidationError


class TestLoginInputModel:
    """Tests for LoginInputModel."""

    def test_model_exists(self):
        """Test LoginInputModel exists."""
        from lys.apps.user_auth.modules.auth.models import LoginInputModel
        assert LoginInputModel is not None

    def test_model_has_login_field(self):
        """Test model has login field."""
        from lys.apps.user_auth.modules.auth.models import LoginInputModel
        assert "login" in LoginInputModel.model_fields

    def test_model_has_password_field(self):
        """Test model has password field."""
        from lys.apps.user_auth.modules.auth.models import LoginInputModel
        assert "password" in LoginInputModel.model_fields

    def test_model_accepts_valid_data(self):
        """Test model accepts valid data."""
        from lys.apps.user_auth.modules.auth.models import LoginInputModel

        model = LoginInputModel(
            login="test@example.com",
            password="password123"
        )
        assert model.login == "test@example.com"
        assert model.password == "password123"

    def test_login_field_is_required(self):
        """Test login field is required."""
        from lys.apps.user_auth.modules.auth.models import LoginInputModel

        with pytest.raises(ValidationError):
            LoginInputModel(password="password123")

    def test_password_field_is_required(self):
        """Test password field is required."""
        from lys.apps.user_auth.modules.auth.models import LoginInputModel

        with pytest.raises(ValidationError):
            LoginInputModel(login="test@example.com")

    def test_login_strips_whitespace(self):
        """Test login field strips whitespace."""
        from lys.apps.user_auth.modules.auth.models import LoginInputModel

        model = LoginInputModel(
            login="  test@example.com  ",
            password="password123"
        )
        assert model.login == "test@example.com"
