import strawberry
from strawberry import relay

from lys.apps.organization.modules.user.models import CreateClientUserInputModel
from lys.apps.user_auth.modules.user.models import UpdateUserEmailInputModel, UpdateUserPrivateDataInputModel
from lys.apps.user_role.modules.user.models import UpdateUserRolesInputModel


@strawberry.experimental.pydantic.input(model=UpdateUserEmailInputModel)
class UpdateClientUserEmailInput:
    new_email: strawberry.auto = strawberry.field(
        description="New email address for the client user (will be set to unverified state)"
    )


@strawberry.experimental.pydantic.input(model=UpdateUserPrivateDataInputModel)
class UpdateClientUserPrivateDataInput:
    first_name: strawberry.auto = strawberry.field(
        description="Optional first name to update (GDPR-protected)"
    )
    last_name: strawberry.auto = strawberry.field(
        description="Optional last name to update (GDPR-protected)"
    )
    gender_code: strawberry.auto = strawberry.field(
        description="Optional gender code to update (MALE, FEMALE, OTHER)"
    )
    language_code: strawberry.auto = strawberry.field(
        description="Optional language code to update (e.g., 'en', 'fr')"
    )


@strawberry.experimental.pydantic.input(model=UpdateUserRolesInputModel)
class UpdateClientUserRolesInput:
    role_codes: strawberry.auto = strawberry.field(
        description="List of role codes to assign to the client user in this organization (empty list removes all roles)"
    )


@strawberry.experimental.pydantic.input(model=CreateClientUserInputModel)
class CreateClientUserInput:
    client_id: relay.GlobalID = strawberry.field(
        description="GlobalID of the client/organization to associate the user with"
    )
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
        description="Optional list of organization role codes to assign to the client user"
    )