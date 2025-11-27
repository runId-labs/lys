import strawberry

from lys.apps.organization.modules.client.models import CreateClientInputModel, UpdateClientInputModel


@strawberry.experimental.pydantic.input(model=CreateClientInputModel)
class CreateClientInput:
    client_name: strawberry.auto = strawberry.field(
        description="Name of the client organization"
    )
    email: strawberry.auto = strawberry.field(
        description="Email address for the owner user (will be normalized to lowercase)"
    )
    password: strawberry.auto = strawberry.field(
        description="Password (min 8 chars, must contain at least one letter and one digit)"
    )
    language_code: strawberry.auto = strawberry.field(
        description="Language code in format 'en' or 'en-US'"
    )
    first_name: strawberry.auto = strawberry.field(
        description="Optional first name of the owner (GDPR-protected)"
    )
    last_name: strawberry.auto = strawberry.field(
        description="Optional last name of the owner (GDPR-protected)"
    )
    gender_code: strawberry.auto = strawberry.field(
        description="Optional gender code (MALE, FEMALE, OTHER)"
    )


@strawberry.experimental.pydantic.input(model=UpdateClientInputModel)
class UpdateClientInput:
    name: strawberry.auto = strawberry.field(
        description="New name of the client organization"
    )