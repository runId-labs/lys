import strawberry

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