from typing import Optional

from pydantic import EmailStr, BaseModel, field_validator, Field
from pydantic_core.core_schema import ValidationInfo

from lys.apps.user_auth.errors import WRONG_REFRESH_TOKEN_ERROR, INVALID_GENDER
from lys.core.models.fixtures import EntityFixturesModel
from lys.core.utils.models import validate_uuid
from lys.core.errors import LysError
from lys.core.utils.validators import (
    validate_name,
    validate_language_format,
    validate_password_for_creation,
    validate_password_for_login
)


########################################################################################################################
#                                                  Fixtures
########################################################################################################################

class UserFixturesModel(EntityFixturesModel):
    class AttributesModel(EntityFixturesModel.AttributesModel):
        email_address: EmailStr
        password: str
        user_status_id: Optional[str] = None
        is_super_user: Optional[bool] = False

    attributes: AttributesModel = None


########################################################################################################################
#                                                  Inputs
########################################################################################################################

class UserPrivateDataInputModel(BaseModel):
    """
    Base model for GDPR-protected user private data.

    Reusable across different user creation/update operations.
    """
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    gender_id: Optional[str] = None

    @field_validator('first_name', 'last_name')
    @classmethod
    def validate_name_field(cls, value: str | None, info: ValidationInfo) -> str | None:
        return validate_name(value, info.field_name)

    @field_validator('gender_id')
    @classmethod
    def validate_gender_id(cls, value: str | None, info: ValidationInfo) -> str | None:
        if value is None:
            return value

        # List of valid gender IDs (should match Gender fixtures)
        valid_genders = ["MALE", "FEMALE", "OTHER"]
        if value not in valid_genders:
            raise LysError(
                INVALID_GENDER,
                f"gender_id must be one of: {', '.join(valid_genders)}"
            )

        return value


class CreateSuperUserInputModel(UserPrivateDataInputModel):
    """
    Input model for creating a super user.

    Includes both authentication data and optional private GDPR-protected data.
    Inherits from UserPrivateDataInputModel for consistent validation.
    """
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    language_id: str = Field(min_length=2, max_length=5)

    @field_validator('password')
    @classmethod
    def validate_password(cls, password: str | None, info: ValidationInfo) -> str | None:
        return validate_password_for_creation(password)

    @field_validator('email')
    @classmethod
    def validate_email(cls, email: str | None, info: ValidationInfo) -> str | None:
        if email:
            return email.strip().lower()
        return email

    @field_validator('language_id')
    @classmethod
    def validate_language_id(cls, value: str | None, info: ValidationInfo) -> str | None:
        return validate_language_format(value)


class UpdateUserPrivateDataInputModel(UserPrivateDataInputModel):
    """
    Input model for updating user private data.

    All fields are optional to allow partial updates.
    Inherits validation from UserPrivateDataInputModel.
    """
    pass


class UpdateUserInputModel(BaseModel):
    """
    Input model for updating user account information.

    All fields are optional to allow partial updates.
    """
    language_id: Optional[str] = Field(None, min_length=2, max_length=5)

    @field_validator('language_id')
    @classmethod
    def validate_language_id(cls, value: str | None, info: ValidationInfo) -> str | None:
        if value is None:
            return value
        return validate_language_format(value)


class ChangePasswordInputModel(BaseModel):
    """
    Input model for changing user password.

    Requires current password for security and validates new password strength.
    """
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator('current_password')
    @classmethod
    def validate_current_password(cls, password: str | None, info: ValidationInfo) -> str | None:
        return validate_password_for_login(password)

    @field_validator('new_password')
    @classmethod
    def validate_new_password(cls, password: str | None, info: ValidationInfo) -> str | None:
        return validate_password_for_creation(password)


class GetUserRefreshTokenInputModel(BaseModel):
    refresh_token_id: str | None

    @field_validator('refresh_token_id')
    @classmethod
    def validate_refresh_token_id(cls, refresh_token_id: str | None, info: ValidationInfo) -> str | None:

        validate_uuid(refresh_token_id, WRONG_REFRESH_TOKEN_ERROR)
        return refresh_token_id