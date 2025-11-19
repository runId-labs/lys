import strawberry

from lys.apps.user_role.modules.user.models import CreateUserWithRolesInputModel, UpdateUserRolesInputModel


@strawberry.experimental.pydantic.input(model=CreateUserWithRolesInputModel)
class CreateUserWithRolesInput:
    email: strawberry.auto = strawberry.field(
        description="Email address for the new user (will be normalized to lowercase)"
    )
    password: strawberry.auto = strawberry.field(
        description="Password (min 8 chars, must contain at least one letter and one digit)"
    )
    language_code: strawberry.auto = strawberry.field(
        description="Language code in format 'en' or 'en-US'"
    )
    first_name: strawberry.auto = strawberry.field(
        description="Optional first name (GDPR-protected)"
    )
    last_name: strawberry.auto = strawberry.field(
        description="Optional last name (GDPR-protected)"
    )
    gender_code: strawberry.auto = strawberry.field(
        description="Optional gender code (MALE, FEMALE, OTHER)"
    )
    role_codes: strawberry.auto = strawberry.field(
        description="List of role codes to assign to the new user"
    )


@strawberry.experimental.pydantic.input(model=UpdateUserRolesInputModel)
class UpdateUserRolesInput:
    role_codes: strawberry.auto = strawberry.field(
        description="List of role codes to assign to the user (empty list removes all roles)"
    )