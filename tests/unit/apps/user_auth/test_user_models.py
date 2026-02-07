"""
Unit tests for user_auth user module Pydantic models.

Tests input validation, field constraints, and model structure.
"""

import pytest
from pydantic import ValidationError


class TestUserPrivateDataInputModel:
    """Tests for UserPrivateDataInputModel."""

    def test_model_exists(self):
        """Test UserPrivateDataInputModel exists."""
        from lys.apps.user_auth.modules.user.models import UserPrivateDataInputModel
        assert UserPrivateDataInputModel is not None

    def test_model_accepts_valid_data(self):
        """Test model accepts valid data."""
        from lys.apps.user_auth.modules.user.models import UserPrivateDataInputModel

        model = UserPrivateDataInputModel(
            first_name="John",
            last_name="Doe",
            gender_code="MALE"
        )
        assert model.first_name == "John"
        assert model.last_name == "Doe"
        assert model.gender_code == "MALE"

    def test_model_accepts_optional_fields(self):
        """Test model accepts empty data (all fields optional)."""
        from lys.apps.user_auth.modules.user.models import UserPrivateDataInputModel

        model = UserPrivateDataInputModel()
        assert model.first_name is None
        assert model.last_name is None
        assert model.gender_code is None

    def test_model_has_first_name_field(self):
        """Test model has first_name field."""
        from lys.apps.user_auth.modules.user.models import UserPrivateDataInputModel
        assert "first_name" in UserPrivateDataInputModel.model_fields

    def test_model_has_last_name_field(self):
        """Test model has last_name field."""
        from lys.apps.user_auth.modules.user.models import UserPrivateDataInputModel
        assert "last_name" in UserPrivateDataInputModel.model_fields

    def test_model_has_gender_code_field(self):
        """Test model has gender_code field."""
        from lys.apps.user_auth.modules.user.models import UserPrivateDataInputModel
        assert "gender_code" in UserPrivateDataInputModel.model_fields


class TestCreateUserInputModel:
    """Tests for CreateUserInputModel."""

    def test_model_exists(self):
        """Test CreateUserInputModel exists."""
        from lys.apps.user_auth.modules.user.models import CreateUserInputModel
        assert CreateUserInputModel is not None

    def test_model_inherits_from_user_private_data(self):
        """Test CreateUserInputModel inherits from UserPrivateDataInputModel."""
        from lys.apps.user_auth.modules.user.models import CreateUserInputModel, UserPrivateDataInputModel
        assert issubclass(CreateUserInputModel, UserPrivateDataInputModel)

    def test_model_accepts_valid_data(self):
        """Test model accepts valid data."""
        from lys.apps.user_auth.modules.user.models import CreateUserInputModel

        model = CreateUserInputModel(
            email="test@example.com",
            password="password123",
            language_code="en"
        )
        assert model.email == "test@example.com"
        assert model.password == "password123"
        assert model.language_code == "en"

    def test_model_has_email_field(self):
        """Test model has email field."""
        from lys.apps.user_auth.modules.user.models import CreateUserInputModel
        assert "email" in CreateUserInputModel.model_fields

    def test_model_has_password_field(self):
        """Test model has password field."""
        from lys.apps.user_auth.modules.user.models import CreateUserInputModel
        assert "password" in CreateUserInputModel.model_fields

    def test_model_has_language_code_field(self):
        """Test model has language_code field."""
        from lys.apps.user_auth.modules.user.models import CreateUserInputModel
        assert "language_code" in CreateUserInputModel.model_fields

    def test_password_min_length_validation(self):
        """Test password minimum length validation."""
        from lys.apps.user_auth.modules.user.models import CreateUserInputModel

        with pytest.raises(ValidationError):
            CreateUserInputModel(
                email="test@example.com",
                password="short",  # Less than 8 chars
                language_code="en"
            )


class TestUpdateUserEmailInputModel:
    """Tests for UpdateUserEmailInputModel."""

    def test_model_exists(self):
        """Test UpdateUserEmailInputModel exists."""
        from lys.apps.user_auth.modules.user.models import UpdateUserEmailInputModel
        assert UpdateUserEmailInputModel is not None

    def test_model_has_new_email_field(self):
        """Test model has new_email field."""
        from lys.apps.user_auth.modules.user.models import UpdateUserEmailInputModel
        assert "new_email" in UpdateUserEmailInputModel.model_fields

    def test_model_accepts_valid_email(self):
        """Test model accepts valid email."""
        from lys.apps.user_auth.modules.user.models import UpdateUserEmailInputModel

        model = UpdateUserEmailInputModel(new_email="newemail@example.com")
        assert model.new_email == "newemail@example.com"


class TestUpdateUserPrivateDataInputModel:
    """Tests for UpdateUserPrivateDataInputModel."""

    def test_model_exists(self):
        """Test UpdateUserPrivateDataInputModel exists."""
        from lys.apps.user_auth.modules.user.models import UpdateUserPrivateDataInputModel
        assert UpdateUserPrivateDataInputModel is not None

    def test_model_inherits_from_user_private_data(self):
        """Test model inherits from UserPrivateDataInputModel."""
        from lys.apps.user_auth.modules.user.models import UpdateUserPrivateDataInputModel, UserPrivateDataInputModel
        assert issubclass(UpdateUserPrivateDataInputModel, UserPrivateDataInputModel)

    def test_model_has_language_code_field(self):
        """Test model has language_code field."""
        from lys.apps.user_auth.modules.user.models import UpdateUserPrivateDataInputModel
        assert "language_code" in UpdateUserPrivateDataInputModel.model_fields


class TestUpdatePasswordInputModel:
    """Tests for UpdatePasswordInputModel."""

    def test_model_exists(self):
        """Test UpdatePasswordInputModel exists."""
        from lys.apps.user_auth.modules.user.models import UpdatePasswordInputModel
        assert UpdatePasswordInputModel is not None

    def test_model_has_new_password_field(self):
        """Test model has new_password field."""
        from lys.apps.user_auth.modules.user.models import UpdatePasswordInputModel
        assert "new_password" in UpdatePasswordInputModel.model_fields

    def test_model_has_current_password_field(self):
        """Test model has current_password field."""
        from lys.apps.user_auth.modules.user.models import UpdatePasswordInputModel
        assert "current_password" in UpdatePasswordInputModel.model_fields

    def test_model_accepts_valid_passwords(self):
        """Test model accepts valid passwords."""
        from lys.apps.user_auth.modules.user.models import UpdatePasswordInputModel

        model = UpdatePasswordInputModel(
            current_password="oldpassword123",
            new_password="newpassword123"
        )
        assert model.current_password == "oldpassword123"
        assert model.new_password == "newpassword123"


class TestUpdateUserStatusInputModel:
    """Tests for UpdateUserStatusInputModel."""

    def test_model_exists(self):
        """Test UpdateUserStatusInputModel exists."""
        from lys.apps.user_auth.modules.user.models import UpdateUserStatusInputModel
        assert UpdateUserStatusInputModel is not None

    def test_model_has_status_code_field(self):
        """Test model has status_code field."""
        from lys.apps.user_auth.modules.user.models import UpdateUserStatusInputModel
        assert "status_code" in UpdateUserStatusInputModel.model_fields


class TestUserFixturesModel:
    """Tests for UserFixturesModel."""

    def test_model_exists(self):
        """Test UserFixturesModel exists."""
        from lys.apps.user_auth.modules.user.models import UserFixturesModel
        assert UserFixturesModel is not None

    def test_model_inherits_from_entity_fixtures_model(self):
        """Test UserFixturesModel inherits from EntityFixturesModel."""
        from lys.apps.user_auth.modules.user.models import UserFixturesModel
        from lys.core.models.fixtures import EntityFixturesModel
        assert issubclass(UserFixturesModel, EntityFixturesModel)

    def test_attributes_model_has_email_address(self):
        """Test AttributesModel has email_address field."""
        from lys.apps.user_auth.modules.user.models import UserFixturesModel
        assert "email_address" in UserFixturesModel.AttributesModel.model_fields

    def test_attributes_model_has_password(self):
        """Test AttributesModel has password field."""
        from lys.apps.user_auth.modules.user.models import UserFixturesModel
        assert "password" in UserFixturesModel.AttributesModel.model_fields


class TestResetPasswordInputModel:
    """Tests for ResetPasswordInputModel."""

    def test_model_exists(self):
        from lys.apps.user_auth.modules.user.models import ResetPasswordInputModel
        assert ResetPasswordInputModel is not None

    def test_has_token_field(self):
        from lys.apps.user_auth.modules.user.models import ResetPasswordInputModel
        assert "token" in ResetPasswordInputModel.model_fields

    def test_has_new_password_field(self):
        from lys.apps.user_auth.modules.user.models import ResetPasswordInputModel
        assert "new_password" in ResetPasswordInputModel.model_fields

    def test_valid_input(self):
        import uuid
        from lys.apps.user_auth.modules.user.models import ResetPasswordInputModel
        token = str(uuid.uuid4())
        model = ResetPasswordInputModel(token=token, new_password="newSecurePass1!")
        assert model.token == token


class TestVerifyEmailInputModel:
    """Tests for VerifyEmailInputModel."""

    def test_model_exists(self):
        from lys.apps.user_auth.modules.user.models import VerifyEmailInputModel
        assert VerifyEmailInputModel is not None

    def test_has_token_field(self):
        from lys.apps.user_auth.modules.user.models import VerifyEmailInputModel
        assert "token" in VerifyEmailInputModel.model_fields


class TestActivateUserInputModel:
    """Tests for ActivateUserInputModel."""

    def test_model_exists(self):
        from lys.apps.user_auth.modules.user.models import ActivateUserInputModel
        assert ActivateUserInputModel is not None

    def test_has_token_field(self):
        from lys.apps.user_auth.modules.user.models import ActivateUserInputModel
        assert "token" in ActivateUserInputModel.model_fields

    def test_has_new_password_field(self):
        from lys.apps.user_auth.modules.user.models import ActivateUserInputModel
        assert "new_password" in ActivateUserInputModel.model_fields


class TestAnonymizeUserInputModel:
    """Tests for AnonymizeUserInputModel."""

    def test_model_exists(self):
        from lys.apps.user_auth.modules.user.models import AnonymizeUserInputModel
        assert AnonymizeUserInputModel is not None


class TestListUserAuditLogsInputModel:
    """Tests for ListUserAuditLogsInputModel."""

    def test_model_exists(self):
        from lys.apps.user_auth.modules.user.models import ListUserAuditLogsInputModel
        assert ListUserAuditLogsInputModel is not None


class TestChangePasswordInputModel:
    """Tests for ChangePasswordInputModel."""

    def test_model_exists(self):
        from lys.apps.user_auth.modules.user.models import ChangePasswordInputModel
        assert ChangePasswordInputModel is not None

    def test_has_new_password_field(self):
        from lys.apps.user_auth.modules.user.models import ChangePasswordInputModel
        assert "new_password" in ChangePasswordInputModel.model_fields


class TestCreateSuperUserInputModel:
    """Tests for CreateSuperUserInputModel."""

    def test_model_exists(self):
        from lys.apps.user_auth.modules.user.models import CreateSuperUserInputModel
        assert CreateSuperUserInputModel is not None

    def test_has_email_field(self):
        from lys.apps.user_auth.modules.user.models import CreateSuperUserInputModel
        assert "email" in CreateSuperUserInputModel.model_fields

    def test_has_password_field(self):
        from lys.apps.user_auth.modules.user.models import CreateSuperUserInputModel
        assert "password" in CreateSuperUserInputModel.model_fields
