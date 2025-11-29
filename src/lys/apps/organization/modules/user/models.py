from pydantic import Field, field_validator
from pydantic_core.core_schema import ValidationInfo
from strawberry import relay

from lys.apps.organization.consts import INVALID_CLIENT_ID
from lys.apps.user_role.modules.user.models import CreateUserWithRolesInputModel
from lys.core.utils.validators import validate_uuid


class CreateClientUserInputModel(CreateUserWithRolesInputModel):
    """
    Input model for creating a client user with organization role assignments.

    Extends CreateUserWithRolesInputModel with client_id.
    Used by organization app's create_client_user webservice.
    """
    client_id: str = Field(..., description="Client ID to associate the user with")

    @field_validator('client_id', mode='before')
    @classmethod
    def validate_client_id(cls, value: relay.GlobalID | dict, info: ValidationInfo) -> str:
        if isinstance(value, dict):
            client_id = value.get('node_id')
        else:
            client_id = value.node_id
        validate_uuid(client_id, INVALID_CLIENT_ID)
        return client_id