import strawberry

from lys.apps.user_auth.modules.user.models import (
    CreateUserInputModel,
    CreateSuperUserInputModel,
    UpdateUserInputModel,
    UpdateUserPrivateDataInputModel,
    UpdateEmailInputModel,
    UpdatePasswordInputModel,
    ChangePasswordInputModel,
    ResetPasswordInputModel,
    VerifyEmailInputModel,
    UpdateUserStatusInputModel,
    AnonymizeUserInputModel,
    CreateUserObservationInputModel,
    UpdateUserAuditLogInputModel
)


@strawberry.experimental.pydantic.input(model=CreateUserInputModel)
class CreateUserInput:
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


@strawberry.experimental.pydantic.input(model=CreateSuperUserInputModel)
class CreateSuperUserInput:
    email: strawberry.auto = strawberry.field(
        description="Email address for the new super user (will be normalized to lowercase)"
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


@strawberry.experimental.pydantic.input(model=UpdateUserInputModel)
class UpdateUserInput:
    language_code: strawberry.auto = strawberry.field(
        description="Optional language code to update in format 'en' or 'en-US'"
    )


@strawberry.experimental.pydantic.input(model=UpdateUserPrivateDataInputModel)
class UpdateUserPrivateDataInput:
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
        description="Optional language code to update in format 'en' or 'en-US'"
    )


@strawberry.experimental.pydantic.input(model=UpdateEmailInputModel)
class UpdateEmailInput:
    new_email: strawberry.auto = strawberry.field(
        description="New email address (will be set to unverified state)"
    )


@strawberry.experimental.pydantic.input(model=UpdatePasswordInputModel)
class UpdatePasswordInput:
    current_password: strawberry.auto = strawberry.field(
        description="Current password for verification"
    )
    new_password: strawberry.auto = strawberry.field(
        description="New password (min 8 chars, must contain at least one letter and one digit)"
    )


@strawberry.experimental.pydantic.input(model=ChangePasswordInputModel)
class ChangePasswordInput:
    current_password: strawberry.auto = strawberry.field(
        description="Current password for verification"
    )
    new_password: strawberry.auto = strawberry.field(
        description="New password (min 8 chars, must contain at least one letter and one digit)"
    )


@strawberry.experimental.pydantic.input(model=ResetPasswordInputModel)
class ResetPasswordInput:
    token: strawberry.auto = strawberry.field(
        description="One-time reset token from email"
    )
    new_password: strawberry.auto = strawberry.field(
        description="New password (min 8 chars, must contain at least one letter and one digit)"
    )


@strawberry.experimental.pydantic.input(model=VerifyEmailInputModel)
class VerifyEmailInput:
    token: strawberry.auto = strawberry.field(
        description="One-time verification token from email"
    )


@strawberry.experimental.pydantic.input(model=UpdateUserStatusInputModel)
class UpdateUserStatusInput:
    status_code: strawberry.auto = strawberry.field(
        description="New status code (e.g., ACTIVE, INACTIVE, SUSPENDED). Cannot be DELETED - use anonymizeUser instead."
    )
    reason: strawberry.auto = strawberry.field(
        description="Reason for status change (min 10 characters, required for audit trail)"
    )


@strawberry.experimental.pydantic.input(model=AnonymizeUserInputModel)
class AnonymizeUserInput:
    reason: strawberry.auto = strawberry.field(
        description="Reason for anonymization (min 10 chars, required for audit). IRREVERSIBLE operation."
    )


@strawberry.experimental.pydantic.input(model=CreateUserObservationInputModel)
class CreateUserObservationInput:
    target_user_id: strawberry.auto = strawberry.field(
        description="ID of user to create observation for"
    )
    message: strawberry.auto = strawberry.field(
        description="Observation message (min 10 characters)"
    )


@strawberry.experimental.pydantic.input(model=UpdateUserAuditLogInputModel)
class UpdateUserAuditLogInput:
    message: strawberry.auto = strawberry.field(
        description="Updated observation message (min 10 characters)"
    )
