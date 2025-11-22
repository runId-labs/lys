from typing import Optional

from pydantic import EmailStr, BaseModel, field_validator, Field
from pydantic_core.core_schema import ValidationInfo
from strawberry import relay

from lys.apps.user_auth.errors import (
    WRONG_REFRESH_TOKEN_ERROR,
    INVALID_RESET_TOKEN_ERROR,
    INVALID_STATUS_CHANGE,
    INVALID_USER_ID
)
from lys.core.models.fixtures import EntityFixturesModel
from lys.core.errors import LysError
from lys.core.utils.validators import (
    validate_name,
    validate_language_format,
    validate_password_for_creation,
    validate_password_for_login,
    validate_uuid,
    validate_gender_code
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
    first_name: Optional[str] = Field(
        None,
        min_length=1,
        max_length=100,
        description="First name (GDPR-protected)"
    )
    last_name: Optional[str] = Field(
        None,
        min_length=1,
        max_length=100,
        description="Last name (GDPR-protected)"
    )
    gender_code: Optional[str] = Field(
        None,
        description="Gender code (MALE, FEMALE, OTHER)"
    )

    @field_validator('first_name', 'last_name')
    @classmethod
    def validate_name_field(cls, value: str | None, info: ValidationInfo) -> str | None:
        return validate_name(value, info.field_name)

    @field_validator('gender_code')
    @classmethod
    def validate_gender_code_field(cls, value: str | None, info: ValidationInfo) -> str | None:
        return validate_gender_code(value)


class CreateUserInputModel(UserPrivateDataInputModel):
    """
    Input model for creating a regular user.

    Includes both authentication data and optional private GDPR-protected data.
    Inherits from UserPrivateDataInputModel for consistent validation.
    Used by both user_auth and user_role create_user webservices.
    """
    email: EmailStr = Field(
        description="Email address for the new user (will be normalized to lowercase)"
    )
    password: str = Field(
        min_length=8,
        max_length=128,
        description="Password (min 8 chars, must contain at least one letter and one digit)"
    )
    language_code: str = Field(
        min_length=2,
        max_length=5,
        description="Language code in format 'en' or 'en-US'"
    )

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

    @field_validator('language_code')
    @classmethod
    def validate_language_code(cls, value: str | None, info: ValidationInfo) -> str | None:
        return validate_language_format(value)


class CreateSuperUserInputModel(CreateUserInputModel):
    """
    Input model for creating a super user.

    Inherits from CreateUserInputModel with identical validation.
    Separated for semantic clarity (super user vs regular user creation).
    """
    pass


class UpdateUserPrivateDataInputModel(UserPrivateDataInputModel):
    """
    Input model for updating user private data.

    All fields are optional to allow partial updates.
    Inherits validation from UserPrivateDataInputModel.
    """
    language_code: Optional[str] = Field(
        None,
        min_length=2,
        max_length=5,
        description="Language code to update in format 'en' or 'en-US'"
    )

    @field_validator('language_code')
    @classmethod
    def validate_language_code(cls, value: str | None, info: ValidationInfo) -> str | None:
        if value is None:
            return value
        return validate_language_format(value)


class UpdateUserInputModel(BaseModel):
    """
    Input model for updating user account information.

    All fields are optional to allow partial updates.
    """
    language_code: Optional[str] = Field(
        None,
        min_length=2,
        max_length=5,
        description="Language code to update in format 'en' or 'en-US'"
    )

    @field_validator('language_code')
    @classmethod
    def validate_language_code(cls, value: str | None, info: ValidationInfo) -> str | None:
        if value is None:
            return value
        return validate_language_format(value)


class UpdateEmailInputModel(BaseModel):
    """
    Input model for updating user email address.

    Requires new email address. The email will be set to unverified state
    and a verification email will be sent to the new address.
    """
    new_email: EmailStr = Field(
        description="New email address (will be set to unverified state)"
    )

    @field_validator('new_email')
    @classmethod
    def validate_email(cls, email: str | None, info: ValidationInfo) -> str | None:
        if email:
            return email.strip().lower()
        return email


class UpdatePasswordInputModel(BaseModel):
    """
    Input model for updating user password (OWNER access).

    Requires current password for security and validates new password strength.
    Used with lys_edition and OWNER access level.
    """
    current_password: str = Field(
        min_length=1,
        description="Current password for verification"
    )
    new_password: str = Field(
        min_length=8,
        max_length=128,
        description="New password (min 8 chars, must contain at least one letter and one digit)"
    )

    @field_validator('current_password')
    @classmethod
    def validate_current_password(cls, password: str | None, info: ValidationInfo) -> str | None:
        return validate_password_for_login(password)

    @field_validator('new_password')
    @classmethod
    def validate_new_password(cls, password: str | None, info: ValidationInfo) -> str | None:
        return validate_password_for_creation(password)


class ChangePasswordInputModel(BaseModel):
    """
    Input model for changing user password.

    Requires current password for security and validates new password strength.
    """
    current_password: str = Field(
        min_length=1,
        description="Current password for verification"
    )
    new_password: str = Field(
        min_length=8,
        max_length=128,
        description="New password (min 8 chars, must contain at least one letter and one digit)"
    )

    @field_validator('current_password')
    @classmethod
    def validate_current_password(cls, password: str | None, info: ValidationInfo) -> str | None:
        return validate_password_for_login(password)

    @field_validator('new_password')
    @classmethod
    def validate_new_password(cls, password: str | None, info: ValidationInfo) -> str | None:
        return validate_password_for_creation(password)


class ResetPasswordInputModel(BaseModel):
    """
    Input model for resetting password using one-time token.

    Used when user forgot password and received reset link via email.
    """
    token: str = Field(
        min_length=1,
        description="One-time reset token from email"
    )
    new_password: str = Field(
        min_length=8,
        max_length=128,
        description="New password (min 8 chars, must contain at least one letter and one digit)"
    )

    @field_validator('token')
    @classmethod
    def validate_token(cls, token: str | None, info: ValidationInfo) -> str | None:
        validate_uuid(token, INVALID_RESET_TOKEN_ERROR)
        return token

    @field_validator('new_password')
    @classmethod
    def validate_new_password(cls, password: str | None, info: ValidationInfo) -> str | None:
        return validate_password_for_creation(password)


class VerifyEmailInputModel(BaseModel):
    """
    Input model for verifying email using one-time token.

    Used when user clicks verification link in email.
    """
    token: str = Field(
        min_length=1,
        description="One-time verification token from email"
    )

    @field_validator('token')
    @classmethod
    def validate_token(cls, token: str | None, info: ValidationInfo) -> str | None:
        validate_uuid(token, INVALID_RESET_TOKEN_ERROR)
        return token


class GetUserRefreshTokenInputModel(BaseModel):
    refresh_token_id: str | None

    @field_validator('refresh_token_id')
    @classmethod
    def validate_refresh_token_id(cls, refresh_token_id: str | None, info: ValidationInfo) -> str | None:

        validate_uuid(refresh_token_id, WRONG_REFRESH_TOKEN_ERROR)
        return refresh_token_id


class UpdateUserStatusInputModel(BaseModel):
    """
    Input model for updating user status.

    Used to change user status (e.g., ACTIVE, INACTIVE, SUSPENDED).
    Cannot be used to set status to DELETED - use anonymize_user instead.
    Requires a reason for audit trail purposes.
    """
    status_code: str = Field(
        min_length=1,
        max_length=50,
        description="New status code (ACTIVE, INACTIVE, SUSPENDED). Cannot be DELETED - use anonymizeUser instead."
    )
    reason: str = Field(
        min_length=10,
        description="Reason for status change (min 10 characters, required for audit trail)"
    )

    @field_validator('status_code')
    @classmethod
    def validate_status_code(cls, value: str | None, info: ValidationInfo) -> str | None:
        if value is None:
            return value

        # Prevent setting DELETED status via this input
        if value == "DELETED":
            raise LysError(
                INVALID_STATUS_CHANGE,
                "Cannot set status to DELETED. Use anonymize_user webservice instead."
            )

        return value


class AnonymizeUserInputModel(BaseModel):
    """
    Input model for anonymizing user data (GDPR compliance).

    This is an irreversible operation that removes all personal data
    and sets the user status to DELETED.
    """
    reason: str = Field(
        min_length=10,
        max_length=500,
        description="Reason for anonymization (min 10 chars, required for audit). IRREVERSIBLE operation."
    )

    @field_validator('reason')
    @classmethod
    def validate_reason(cls, value: str | None, info: ValidationInfo) -> str | None:
        if value:
            return value.strip()
        return value


class CreateUserObservationInputModel(BaseModel):
    """
    Input model for creating a user observation (manual audit log).

    Used by administrators to add notes/observations about users.
    """
    target_user_id: relay.GlobalID = Field(
        description="ID of the user to create observation for"
    )
    message: str = Field(
        min_length=10,
        description="Observation message (min 10 characters)"
    )

    @field_validator('target_user_id')
    @classmethod
    def validate_target_user_id(cls, value: relay.GlobalID | None, info: ValidationInfo) -> str | None:
        target_user_id = value.node_id
        validate_uuid(target_user_id, INVALID_USER_ID)
        return target_user_id

    @field_validator('message')
    @classmethod
    def validate_message(cls, value: str | None, info: ValidationInfo) -> str | None:
        if value:
            return value.strip()
        return value


class UpdateUserAuditLogInputModel(BaseModel):
    """
    Input model for updating a user audit log (OBSERVATION type only).

    Only the author can update their own observations.
    System logs (STATUS_CHANGE, ANONYMIZATION) cannot be updated.
    """
    message: str = Field(min_length=10, description="Updated observation message (min 10 characters)")

    @field_validator('message')
    @classmethod
    def validate_message(cls, value: str | None, info: ValidationInfo) -> str | None:
        if value:
            return value.strip()
        return value


class ListUserAuditLogsInputModel(BaseModel):
    """
    Input model for listing user audit logs with filters.

    All fields are optional for flexible filtering.
    """
    log_type_code: Optional[str] = Field(None, description="Filter by log type (STATUS_CHANGE, ANONYMIZATION, OBSERVATION)")
    email_search: Optional[str] = Field(None, min_length=1, description="Search in target or author email addresses")
    user_filter: Optional[str] = Field(None, description="Filter by user role: 'author', 'target', or None (both)")
    include_deleted: Optional[bool] = Field(False, description="Include soft-deleted observations (default: False)")

    @field_validator('user_filter')
    @classmethod
    def validate_user_filter(cls, value: str | None, info: ValidationInfo) -> str | None:
        if value is not None and value not in ["author", "target"]:
            raise LysError(
                (400, "INVALID_USER_FILTER"),
                "user_filter must be 'author', 'target', or None"
            )
        return value