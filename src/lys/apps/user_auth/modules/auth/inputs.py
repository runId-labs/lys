import strawberry

from lys.apps.user_auth.modules.auth.models import LoginInputModel


@strawberry.experimental.pydantic.input(model=LoginInputModel)
class LoginInput:
    login: strawberry.auto
    password: strawberry.auto
