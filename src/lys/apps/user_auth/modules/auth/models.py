from pydantic import BaseModel, field_validator, Field
from pydantic_core.core_schema import ValidationInfo

from lys.apps.user_auth.errors import EMPTY_LOGIN_ERROR
from lys.core.errors import LysError
from lys.core.utils.validators import validate_password_for_login


class LoginInputModel(BaseModel):
    """
    Input model for user authentication.
    """
    login: str = Field(
        description="User login (email address or username)"
    )
    password: str = Field(
        description="User password"
    )

    @field_validator('login')
    @classmethod
    def validate_login(cls, login: str | None, info: ValidationInfo) -> str | None:
        if not len(login.strip()):
            raise LysError(
                EMPTY_LOGIN_ERROR,
                "login cannot be empty"
            )

        return login.strip()

    @field_validator('password')
    @classmethod
    def validate_password(cls, password: str | None, info: ValidationInfo) -> str | None:
        return validate_password_for_login(password)