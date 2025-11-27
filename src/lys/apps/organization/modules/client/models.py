from pydantic import BaseModel, Field, field_validator
from pydantic_core.core_schema import ValidationInfo

from lys.apps.user_auth.modules.user.models import CreateUserInputModel


class CreateClientInputModel(CreateUserInputModel):
    """
    Input model for creating a new client with an owner user.

    This model extends CreateUserInputModel to include client information.
    The user will be automatically set as the client owner and will have
    full administrative access to the client without requiring explicit roles.

    Additionally, a ClientUser relationship is created to link the owner to the client.
    """
    client_name: str = Field(..., min_length=1, max_length=255, description="Name of the client organization")

    @field_validator("client_name")
    @classmethod
    def validate_client_name(cls, value: str, info: ValidationInfo) -> str:
        """Validate and normalize client name."""
        if not value or not value.strip():
            raise ValueError("Client name cannot be empty")
        return value.strip()


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