import strawberry

from lys.apps.user_role.modules.user.models import CreateUserWithRolesInputModel


@strawberry.experimental.pydantic.input(model=CreateUserWithRolesInputModel)
class CreateUserWithRolesInput:
    email: strawberry.auto = strawberry.field(
        description="Email address for the new user (will be normalized to lowercase)"
    )
    password: strawberry.auto = strawberry.field(
        description="Password (min 8 chars, must contain at least one letter and one digit)"
    )
    language_id: strawberry.auto = strawberry.field(
        description="Language ID in format 'en' or 'en-US'"
    )
    first_name: strawberry.auto = strawberry.field(
        description="Optional first name (GDPR-protected)"
    )
    last_name: strawberry.auto = strawberry.field(
        description="Optional last name (GDPR-protected)"
    )
    gender_id: strawberry.auto = strawberry.field(
        description="Optional gender ID (MALE, FEMALE, OTHER)"
    )
    roles: strawberry.auto = strawberry.field(
        description="List of role IDs to assign to the new user"
    )