from pydantic import BaseModel, field_validator
from pydantic_core.core_schema import ValidationInfo

from lys.apps.user_auth.errors import EMPTY_LOGIN_ERROR, EMPTY_PASSWORD_ERROR
from lys.core.errors import LysError


class LoginInputModel(BaseModel):
    """
    Model to create superuser
    """
    login: str
    password: str

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
        if not len(password.strip()):
            raise LysError(
                EMPTY_PASSWORD_ERROR,
                "password cannot be empty"
            )

        return password.strip()