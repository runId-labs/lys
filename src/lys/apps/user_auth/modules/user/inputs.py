import strawberry

from lys.apps.user_auth.modules.user.models import (
    CreateUserInputModel,
    CreateSuperUserInputModel,
    UpdateUserInputModel,
    UpdateUserPrivateDataInputModel,
    ChangePasswordInputModel
)


@strawberry.experimental.pydantic.input(model=CreateUserInputModel)
class CreateUserInput:
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


@strawberry.experimental.pydantic.input(model=CreateSuperUserInputModel)
class CreateSuperUserInput:
    email: strawberry.auto = strawberry.field(
        description="Email address for the new super user (will be normalized to lowercase)"
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


@strawberry.experimental.pydantic.input(model=UpdateUserInputModel)
class UpdateUserInput:
    language_id: strawberry.auto = strawberry.field(
        description="Optional language ID to update in format 'en' or 'en-US'"
    )


@strawberry.experimental.pydantic.input(model=UpdateUserPrivateDataInputModel)
class UpdateUserPrivateDataInput:
    first_name: strawberry.auto = strawberry.field(
        description="Optional first name to update (GDPR-protected)"
    )
    last_name: strawberry.auto = strawberry.field(
        description="Optional last name to update (GDPR-protected)"
    )
    gender_id: strawberry.auto = strawberry.field(
        description="Optional gender ID to update (MALE, FEMALE, OTHER)"
    )


@strawberry.experimental.pydantic.input(model=ChangePasswordInputModel)
class ChangePasswordInput:
    current_password: strawberry.auto = strawberry.field(
        description="Current password for verification"
    )
    new_password: strawberry.auto = strawberry.field(
        description="New password (min 8 chars, must contain at least one letter and one digit)"
    )