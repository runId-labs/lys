from typing import Optional

from pydantic import EmailStr, BaseModel, field_validator
from pydantic_core.core_schema import ValidationInfo

from lys.apps.user_auth.errors import WRONG_REFRESH_TOKEN_ERROR
from lys.core.models.fixtures import EntityFixturesModel
from lys.core.utils.models import validate_uuid


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


class GetUserRefreshTokenInputModel(BaseModel):
    refresh_token_id: str | None

    @field_validator('refresh_token_id')
    @classmethod
    def validate_refresh_token_id(cls, refresh_token_id: str | None, info: ValidationInfo) -> str | None:

        validate_uuid(refresh_token_id, WRONG_REFRESH_TOKEN_ERROR)
        return refresh_token_id