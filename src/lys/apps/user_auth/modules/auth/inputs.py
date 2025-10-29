import strawberry

from lys.apps.user_auth.modules.auth.models import LoginInputModel


@strawberry.experimental.pydantic.input(model=LoginInputModel)
class LoginInput:
    login: strawberry.auto = strawberry.field(
        description="User login (email address or username)"
    )
    password: strawberry.auto = strawberry.field(
        description="User password"
    )
