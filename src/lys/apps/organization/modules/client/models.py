from typing import Optional

from pydantic import BaseModel, Field, field_validator
from pydantic_core.core_schema import ValidationInfo

from lys.apps.user_auth.modules.user.models import CreateUserInputModel, UserPrivateDataInputModel
from lys.core.utils.validators import validate_language_format


class CreateClientInputModel(CreateUserInputModel):
    """
    Input model for creating a new client with an owner user.

    This model extends CreateUserInputModel to include client information.
    The user will be automatically set as the client owner and will have
    full administrative access to the client without requiring explicit roles.
    """
    client_name: str = Field(..., min_length=1, max_length=255, description="Name of the client organization")

    @field_validator("client_name")
    @classmethod
    def validate_client_name(cls, value: str, info: ValidationInfo) -> str:
        """Validate and normalize client name."""
        if not value or not value.strip():
            raise ValueError("Client name cannot be empty")
        return value.strip()


class CreateClientWithSSOInputModel(UserPrivateDataInputModel):
    """
    Input model for creating a new client via SSO (no password).

    Uses sso_token from the SSO signup flow to retrieve provider-verified user info.
    """
    sso_token: str = Field(..., min_length=1, description="SSO session token from signup flow")
    client_name: str = Field(..., min_length=1, max_length=255, description="Name of the client organization")
    language_code: str = Field(
        min_length=2,
        max_length=5,
        description="Language code in format 'en' or 'en-US'"
    )

    @field_validator("client_name")
    @classmethod
    def validate_client_name(cls, value: str, info: ValidationInfo) -> str:
        if not value or not value.strip():
            raise ValueError("Client name cannot be empty")
        return value.strip()

    @field_validator("language_code")
    @classmethod
    def validate_language_code(cls, value: str | None, info: ValidationInfo) -> str | None:
        return validate_language_format(value)


class UpdateClientInputModel(BaseModel):
    """
    Input model for updating a client.
    """
    name: str = Field(..., min_length=1, max_length=255, description="New name of the client organization")

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str, info: ValidationInfo) -> str:
        """Validate and normalize client name."""
        if not value or not value.strip():
            raise ValueError("Client name cannot be empty")
        return value.strip()