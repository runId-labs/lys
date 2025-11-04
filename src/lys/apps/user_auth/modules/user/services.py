import logging
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
from sqlalchemy import update, select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from lys.apps.user_auth.modules.emailing.consts import (
    USER_PASSWORD_RESET_EMAILING_TYPE,
    USER_EMAIL_VERIFICATION_EMAILING_TYPE
)
from lys.apps.base.modules.one_time_token.consts import PASSWORD_RESET_TOKEN_TYPE, EMAIL_VERIFICATION_TOKEN_TYPE
from lys.apps.base.modules.one_time_token.services import OneTimeTokenService
from lys.apps.base.tasks import send_pending_email
from lys.apps.user_auth.errors import (
    INVALID_REFRESH_TOKEN_ERROR,
    INVALID_GENDER,
    INVALID_RESET_TOKEN_ERROR,
    EXPIRED_RESET_TOKEN_ERROR,
    EMAIL_ALREADY_VALIDATED_ERROR,
    USER_ALREADY_EXISTS,
    INVALID_USER_STATUS,
    INVALID_STATUS_CHANGE,
    USER_ALREADY_ANONYMIZED,
    WRONG_CREDENTIALS_ERROR
)
from lys.apps.user_auth.modules.user.entities import (
    UserStatus,
    User,
    UserEmailAddress,
    UserRefreshToken,
    UserEmailing,
    UserOneTimeToken,
    Gender,
    UserPrivateData,
    UserAuditLogType,
    UserAuditLog
)
from lys.apps.user_auth.modules.user.models import GetUserRefreshTokenInputModel
from lys.apps.user_auth.modules.user.consts import (
    OBSERVATION_LOG_TYPE,
    STATUS_CHANGE_LOG_TYPE,
    ANONYMIZATION_LOG_TYPE
)
from lys.apps.user_auth.utils import AuthUtils
from lys.core.errors import LysError
from lys.core.registers import register_service
from lys.core.services import EntityService
from lys.core.utils.datetime import now_utc

logger = logging.getLogger(__name__)


@register_service()
class UserStatusService(EntityService[UserStatus]):
    pass


@register_service()
class GenderService(EntityService[Gender]):
    @classmethod
    async def validate_gender_exists(cls, gender_id: str | None, session: AsyncSession) -> None:
        """
        Validate that a gender ID exists in the database.

        Args:
            gender_id: The gender ID to validate
            session: Database session

        Raises:
            LysError: If gender_id doesn't exist in the database
        """
        if gender_id is None:
            return

        gender = await cls.get_by_id(gender_id, session)
        if not gender:
            raise LysError(
                INVALID_GENDER,
                f"Gender with id '{gender_id}' does not exist"
            )


@register_service()
class UserEmailAddressService(EntityService[UserEmailAddress]):
    pass


@register_service()
class UserPrivateDataService(EntityService[UserPrivateData]):
    """
    Service for managing user private data (GDPR-protected).

    Provides operations for:
    - Creating/updating private data
    - Anonymizing private data (right to be forgotten)
    - Checking if data is anonymized
    """

    @classmethod
    async def anonymize(cls, user_id: str, session: AsyncSession) -> UserPrivateData | None:
        """
        Anonymize user private data (GDPR right to be forgotten).

        Args:
            user_id: ID of the user whose data should be anonymized
            session: Database session

        Returns:
            UserPrivateData: The anonymized entity, or None if not found
        """
        # Find the private data
        stmt = select(cls.entity_class).where(cls.entity_class.user_id == user_id)
        result = await session.execute(stmt)
        private_data = result.scalar_one_or_none()

        if not private_data:
            return None

        # Anonymize the data
        private_data.first_name = None
        private_data.last_name = None
        private_data.gender_id = None
        private_data.anonymized_at = now_utc()

        return private_data


@register_service()
class UserService(EntityService[User]):
    @staticmethod
    def check_password(user: User, plain_text_password: str):
        bytes_ = plain_text_password.encode('utf-8')
        return bcrypt.checkpw(bytes_, user.password.encode('utf-8'))

    @classmethod
    async def get_by_email(cls, email: str, session: AsyncSession) -> User | None:
        """
        Get user by email address.

        Args:
            email: The email address to search for
            session: Database session

        Returns:
            User entity if found, None otherwise
        """
        # Get UserEmailAddress service
        email_address_service = cls.app_manager.get_service("user_email_address")

        # Query user by email address - join on user_id = User.id
        stmt = (
            select(cls.entity_class)
            .join(email_address_service.entity_class)
            .where(email_address_service.entity_class.id == email)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @classmethod
    async def _validate_and_prepare_user_data(
        cls,
        session: AsyncSession,
        email: str,
        password: str,
        language_id: str,
        first_name: str | None = None,
        last_name: str | None = None,
        gender_id: str | None = None
    ) -> tuple:
        """
        Validate user data and prepare entities for user creation.

        Returns:
            Tuple of (email_address_entity, hashed_password, private_data_entity)
        """
        # Get services
        user_email_address_service = cls.app_manager.get_service("user_email_address")
        user_private_data_service = cls.app_manager.get_service("user_private_data")
        language_service = cls.app_manager.get_service("language")
        gender_service = cls.app_manager.get_service("gender")

        # 1. Check if user with this email already exists
        existing_user = await cls.get_by_email(email, session)
        if existing_user:
            raise LysError(
                USER_ALREADY_EXISTS,
                f"User with email {email} already exists"
            )

        # 2. Validate language exists in database
        await language_service.validate_language_exists(language_id, session)

        # 3. Validate gender exists in database (if provided)
        await gender_service.validate_gender_exists(gender_id, session)

        # 4. Create email address entity
        email_address = user_email_address_service.entity_class(id=email)

        # 5. Hash the password
        hashed_password = AuthUtils.hash_password(password)

        # 6. Create private data entity
        private_data = user_private_data_service.entity_class(
            id=str(uuid.uuid4()),
            first_name=first_name,
            last_name=last_name,
            gender_id=gender_id
        )

        return email_address, hashed_password, private_data

    @classmethod
    async def _create_user_internal(
        cls,
        session: AsyncSession,
        email: str,
        password: str,
        language_id: str,
        is_super_user: bool = False,
        send_verification_email: bool = True,
        background_tasks=None,
        first_name: str | None = None,
        last_name: str | None = None,
        gender_id: str | None = None,
        **kwargs
    ) -> User:
        """
        Internal method to create a user with full validation.

        This method performs all necessary validations and creates the user with:
        - Email address entity
        - Hashed password
        - Configurable super user privileges
        - Optional private data (GDPR-protected)
        - Email verification email (if send_verification_email=True and background_tasks provided)
        - Additional attributes via kwargs (e.g., roles for user_role app)

        Args:
            email: Email address (will be normalized)
            password: Plain text password (will be hashed)
            language_id: Language ID (format validated)
            is_super_user: Whether to create a super user or regular user
            send_verification_email: Whether to send email verification email (default: True)
            background_tasks: FastAPI BackgroundTasks for scheduling email (optional)
            session: Database session
            first_name: Optional first name
            last_name: Optional last name
            gender_id: Optional gender ID
            **kwargs: Additional attributes for subclass-specific fields (e.g., roles)

        Returns:
            User: The created user entity

        Raises:
            LysError: If email already exists, language doesn't exist, or gender doesn't exist
        """
        # Validate and prepare user data
        email_address, hashed_password, private_data = await cls._validate_and_prepare_user_data(
            session=session,
            email=email,
            password=password,
            language_id=language_id,
            first_name=first_name,
            last_name=last_name,
            gender_id=gender_id
        )

        # Create user with specified privileges and additional kwargs
        user = await cls.create(
            session,
            email_address=email_address,
            password=hashed_password,
            is_super_user=is_super_user,
            language_id=language_id,
            private_data=private_data,
            **kwargs
        )

        # Send email verification if requested and background_tasks provided
        if send_verification_email and background_tasks is not None:
            user_emailing_service = cls.app_manager.get_service("user_emailing")

            # Create email verification emailing
            user_emailing = await user_emailing_service.create_email_verification_emailing(
                user, session
            )

            # Schedule email sending via Celery after commit
            user_emailing_service.schedule_send_emailing(user_emailing, background_tasks)

        return user

    @classmethod
    async def create_super_user(
        cls,
        session: AsyncSession,
        email: str,
        password: str,
        language_id: str,
        send_verification_email: bool = True,
        background_tasks=None,
        first_name: str | None = None,
        last_name: str | None = None,
        gender_id: str | None = None
    ) -> User:
        """
        Create a new super user with full validation.

        Wrapper around _create_user_internal with is_super_user=True.

        Args:
            email: Email address (will be normalized)
            password: Plain text password (will be hashed)
            language_id: Language ID (format validated)
            send_verification_email: Whether to send email verification email (default: True)
            background_tasks: FastAPI BackgroundTasks for scheduling email (optional)
            session: Database session
            first_name: Optional first name
            last_name: Optional last name
            gender_id: Optional gender ID

        Returns:
            User: The created super user entity

        Raises:
            LysError: If email already exists, language doesn't exist, or gender doesn't exist
        """
        return await cls._create_user_internal(
            session=session,
            email=email,
            password=password,
            language_id=language_id,
            is_super_user=True,
            send_verification_email=send_verification_email,
            background_tasks=background_tasks,
            first_name=first_name,
            last_name=last_name,
            gender_id=gender_id
        )

    @classmethod
    async def create_user(
        cls,
        session: AsyncSession,
        email: str,
        password: str,
        language_id: str,
        send_verification_email: bool = True,
        background_tasks=None,
        first_name: str | None = None,
        last_name: str | None = None,
        gender_id: str | None = None
    ) -> User:
        """
        Create a new regular user with full validation.

        Wrapper around _create_user_internal with is_super_user=False.

        Args:
            email: Email address (will be normalized)
            password: Plain text password (will be hashed)
            language_id: Language ID (format validated)
            send_verification_email: Whether to send email verification email (default: True)
            background_tasks: FastAPI BackgroundTasks for scheduling email (optional)
            session: Database session
            first_name: Optional first name
            last_name: Optional last name
            gender_id: Optional gender ID

        Returns:
            User: The created regular user entity

        Raises:
            LysError: If email already exists, language doesn't exist, or gender doesn't exist
        """
        return await cls._create_user_internal(
            session=session,
            email=email,
            password=password,
            language_id=language_id,
            is_super_user=False,
            send_verification_email=send_verification_email,
            background_tasks=background_tasks,
            first_name=first_name,
            last_name=last_name,
            gender_id=gender_id
        )

    @classmethod
    async def request_password_reset(
        cls,
        email: str,
        session: AsyncSession,
        background_tasks=None
    ) -> bool:
        """
        Request a password reset for a user.

        This method:
        1. Finds the user by email
        2. Creates a forgotten password emailing (if user exists)
        3. Schedules the email to be sent (if background_tasks provided)

        For security reasons, this method always returns True even if the email
        doesn't exist, to avoid revealing which emails are registered.

        Args:
            email: User's email address
            session: Database session
            background_tasks: FastAPI BackgroundTasks for scheduling email (optional)

        Returns:
            bool: Always True (for security)
        """
        # Find user by email
        user = await cls.get_by_email(email, session)

        # Don't reveal if email exists or not (security)
        if not user:
            return True

        # Get user emailing service
        user_emailing_service = cls.app_manager.get_service("user_emailing")

        # Create password reset emailing
        user_emailing = await user_emailing_service.create_password_reset_emailing(
            user, session
        )

        # Schedule email sending via Celery after commit (if background_tasks provided)
        if background_tasks is not None:
            user_emailing_service.schedule_send_emailing(user_emailing, background_tasks)

        return True

    @classmethod
    async def reset_password(
        cls,
        token: str,
        new_password: str,
        session: AsyncSession
    ) -> User:
        """
        Reset user password using a one-time token.

        This method:
        1. Validates the token exists and is not expired
        2. Validates the token has not been used
        3. Updates the user password
        4. Marks the token as used

        Args:
            token: The one-time reset token from email
            new_password: The new password (will be hashed)
            session: Database session

        Returns:
            User: The user with updated password

        Raises:
            LysError: If token is invalid, expired, or already used
        """
        # Get token service
        token_service = cls.app_manager.get_service("user_one_time_token")

        # 1. Find the token
        token_entity = await token_service.get_by_id(token, session)

        if not token_entity:
            raise LysError(
                INVALID_RESET_TOKEN_ERROR,
                "Invalid reset token"
            )

        # 2. Check token type
        if token_entity.type_id != PASSWORD_RESET_TOKEN_TYPE:
            raise LysError(
                INVALID_RESET_TOKEN_ERROR,
                "Token is not a password reset token"
            )

        # 3. Check if token is expired
        if token_entity.is_expired:
            raise LysError(
                EXPIRED_RESET_TOKEN_ERROR,
                "Reset token has expired"
            )

        # 4. Check if token has already been used
        if token_entity.is_used:
            raise LysError(
                INVALID_RESET_TOKEN_ERROR,
                "Reset token has already been used"
            )

        # 5. Get the user
        user = await cls.get_by_id(token_entity.user_id, session)

        if not user:
            raise LysError(
                INVALID_RESET_TOKEN_ERROR,
                "User not found for this token"
            )

        # 6. Hash the new password
        hashed_password = AuthUtils.hash_password(new_password)

        # 7. Update user password
        user.password = hashed_password

        # 8. Mark token as used
        await token_service.mark_as_used(token_entity, session)

        return user

    @classmethod
    async def verify_email(
        cls,
        token: str,
        session: AsyncSession
    ) -> User:
        """
        Verify user email address using a one-time token.

        This method:
        1. Validates the token exists and is not expired
        2. Validates the token has not been used
        3. Validates the email is not already verified
        4. Updates the email address validated_at timestamp
        5. Marks the token as used

        Args:
            token: The one-time verification token from email
            session: Database session

        Returns:
            User: The user with verified email

        Raises:
            LysError: If token is invalid, expired, already used, or email already validated
        """
        # Get token service
        token_service = cls.app_manager.get_service("user_one_time_token")

        # 1. Find the token
        token_entity = await token_service.get_by_id(token, session)

        if not token_entity:
            raise LysError(
                INVALID_RESET_TOKEN_ERROR,
                "Invalid verification token"
            )

        # 2. Check token type
        if token_entity.type_id != EMAIL_VERIFICATION_TOKEN_TYPE:
            raise LysError(
                INVALID_RESET_TOKEN_ERROR,
                "Token is not an email verification token"
            )

        # 3. Check if token is expired
        if token_entity.is_expired:
            raise LysError(
                EXPIRED_RESET_TOKEN_ERROR,
                "Verification token has expired"
            )

        # 4. Check if token has already been used
        if token_entity.is_used:
            raise LysError(
                INVALID_RESET_TOKEN_ERROR,
                "Verification token has already been used"
            )

        # 5. Get the user
        user = await cls.get_by_id(token_entity.user_id, session)

        if not user:
            raise LysError(
                INVALID_RESET_TOKEN_ERROR,
                "User not found for this token"
            )

        # 6. Check if email is already validated
        if user.email_address.validated_at is not None:
            raise LysError(
                EMAIL_ALREADY_VALIDATED_ERROR,
                f"Email address {user.email_address.id} is already validated"
            )

        # 7. Update email address validated_at
        user.email_address.validated_at = now_utc()

        # 8. Mark token as used
        await token_service.mark_as_used(token_entity, session)

        return user

    @classmethod
    async def update_email(
        cls,
        user: User,
        new_email: str,
        session: AsyncSession,
        background_tasks=None
    ) -> User:
        """
        Update user email address and send verification email to new address.

        This method is called by lys_edition which already fetched and validated
        permissions on the user entity.

        This method:
        1. Validates the new email is not already taken
        2. Deletes the old email address entity
        3. Creates a new email address entity (unverified, validated_at=None)
        4. Sends verification email to the new address

        Args:
            user: The user entity (fetched and validated by lys_edition)
            new_email: New email address (will be normalized)
            session: Database session
            background_tasks: FastAPI BackgroundTasks for scheduling email (optional)

        Returns:
            User: The updated user with new email address

        Raises:
            LysError: If new email is already taken
        """
        # Get services
        user_email_address_service = cls.app_manager.get_service("user_email_address")

        # 1. Check if new email is already taken
        existing_user = await cls.get_by_email(new_email, session)
        if existing_user and existing_user.id != user.id:
            raise LysError(
                USER_ALREADY_EXISTS,
                f"Email {new_email} is already in use"
            )

        # 2. Delete old email address entity
        old_email = user.email_address
        await session.delete(old_email)

        # 3. Create new email address entity (validated_at will be None by default)
        await user_email_address_service.create(
            session,
            id=new_email,
            user_id=user.id
        )

        # 4. Flush to update the relationship
        await session.flush()

        # 5. Send verification email to new address (if background_tasks provided)
        if background_tasks is not None:
            user_emailing_service = cls.app_manager.get_service("user_emailing")

            # Create email verification emailing
            user_emailing = await user_emailing_service.create_email_verification_emailing(
                user, session
            )

            # Schedule email sending via Celery after commit
            user_emailing_service.schedule_send_emailing(user_emailing, background_tasks)

        return user

    @classmethod
    async def update_password(
        cls,
        user: User,
        current_password: str,
        new_password: str,
        session: AsyncSession
    ) -> User:
        """
        Update user password after verifying current password.

        This method is called by lys_edition which already fetched and validated
        permissions on the user entity.

        This method:
        1. Verifies the current password is correct
        2. Hashes the new password
        3. Updates the user's password

        Args:
            user: The user entity (fetched and validated by lys_edition)
            current_password: Current password for verification
            new_password: New password to set (will be hashed)
            session: Database session

        Returns:
            User: The user with updated password

        Raises:
            LysError: If current password is incorrect
        """
        # 1. Verify current password
        if not bcrypt.checkpw(current_password.encode('utf-8'), user.password.encode('utf-8')):
            raise LysError(
                WRONG_CREDENTIALS_ERROR,
                "Current password is incorrect"
            )

        # 2. Hash new password
        salt = bcrypt.gensalt()
        hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), salt)

        # 3. Update password
        user.password = hashed_password.decode('utf-8')

        return user

    @classmethod
    async def update_user(
        cls,
        user: User,
        first_name: str | None = None,
        last_name: str | None = None,
        gender_id: str | None = None,
        session: AsyncSession = None
    ) -> User:
        """
        Update user private data (GDPR-protected fields).

        This method is called by lys_edition which already fetched and validated
        permissions on the user entity.

        This method:
        1. Validates gender_id exists if provided
        2. Updates private data fields (only non-None values are updated)

        Args:
            user: The user entity (fetched and validated by lys_edition)
            first_name: Optional first name to update
            last_name: Optional last name to update
            gender_id: Optional gender ID to update
            session: Database session

        Returns:
            User: The user with updated private data

        Raises:
            LysError: If gender_id doesn't exist in database
        """
        # Get gender service for validation
        gender_service = cls.app_manager.get_service("gender")

        # 1. Validate gender exists if provided
        if gender_id is not None:
            await gender_service.validate_gender_exists(gender_id, session)

        # 2. Update private data fields (only update non-None values)
        if first_name is not None:
            user.private_data.first_name = first_name

        if last_name is not None:
            user.private_data.last_name = last_name

        if gender_id is not None:
            user.private_data.gender_id = gender_id

        return user

    @classmethod
    async def update_status(
        cls,
        user: User,
        status_id: str,
        reason: str,
        author_user_id: str,
        session: AsyncSession
    ) -> User:
        """
        Update user status and create audit log.

        Args:
            user: User entity to update
            status_id: New status ID (e.g., ACTIVE, INACTIVE, SUSPENDED)
            reason: Reason for status change (for audit log)
            author_user_id: ID of user performing the status change
            session: Database session

        Returns:
            User: Updated user entity

        Raises:
            LysError: If status_id is invalid or is DELETED
        """
        # Prevent setting DELETED status via this method
        if status_id == "DELETED":
            raise LysError(
                INVALID_STATUS_CHANGE,
                "Cannot set status to DELETED. Use anonymize_user instead."
            )

        # Validate status exists
        user_status_service = cls.app_manager.get_service("user_status")
        status = await user_status_service.get_by_id(status_id, session)

        if not status:
            raise LysError(
                INVALID_USER_STATUS,
                f"Invalid status_id: {status_id}"
            )

        # Store old status for audit log
        old_status_id = user.status_id

        # Update status
        user.status_id = status_id
        await session.flush()

        # Create audit log with "OLD → NEW" prefix
        audit_log_service = cls.app_manager.get_service("user_audit_log")
        audit_message = f"{old_status_id} → {status_id}\n\n{reason}"

        await audit_log_service.create_audit_log(
            target_user_id=user.id,
            author_user_id=author_user_id,
            log_type_id=STATUS_CHANGE_LOG_TYPE,
            message=audit_message,
            session=session
        )

        return user

    @classmethod
    async def anonymize_user(
        cls,
        user_id: str,
        reason: str,
        anonymized_by: str,
        session: AsyncSession
    ) -> None:
        """
        Anonymize user data for GDPR compliance and create audit log.

        This is an IRREVERSIBLE operation that:
        - Sets user status to DELETED
        - Removes all private data (first_name, last_name, gender)
        - Sets anonymized_at timestamp
        - Creates audit log entry
        - Keeps user_id and email for audit/legal purposes

        Args:
            user_id: ID of user to anonymize
            reason: Reason for anonymization (for audit log)
            anonymized_by: ID of user performing the anonymization
            session: Database session

        Raises:
            LysError: If user is already anonymized or not found
        """
        # Fetch user with private_data
        user = await cls.get_by_id(user_id, session)

        if not user:
            raise LysError((404, "USER_NOT_FOUND"), f"User {user_id} not found")

        # Check if already anonymized
        if user.private_data and user.private_data.anonymized_at is not None:
            raise LysError(
                USER_ALREADY_ANONYMIZED,
                f"User {user_id} is already anonymized"
            )

        # Store old status for audit log
        old_status_id = user.status_id

        # Set status to DELETED
        user.status_id = "DELETED"

        # Anonymize private data
        if user.private_data:
            user.private_data.first_name = None
            user.private_data.last_name = None
            user.private_data.gender_id = None
            user.private_data.anonymized_at = datetime.now(timezone.utc)

        await session.flush()

        # Create audit log with "OLD → DELETED (anonymized)" prefix
        audit_log_service = cls.app_manager.get_service("user_audit_log")
        audit_message = f"{old_status_id} → DELETED (anonymized)\n\n{reason}"

        await audit_log_service.create_audit_log(
            target_user_id=user_id,
            author_user_id=anonymized_by,
            log_type_id=ANONYMIZATION_LOG_TYPE,
            message=audit_message,
            session=session
        )

        # Log anonymization for audit
        logger.info(
            f"User {user_id} anonymized. Reason: {reason}. Anonymized by: {anonymized_by}"
        )


@register_service()
class UserRefreshTokenService(EntityService[UserRefreshToken]):

    @classmethod
    async def generate(cls, user: User, session: AsyncSession) -> UserRefreshToken:
        auth_utils = AuthUtils()
        once_refresh_token_expire_minutes = auth_utils.config.get("once_refresh_token_expire_minutes")
        connection_expire_minutes = auth_utils.config.get("connection_expire_minutes")

        new_token: UserRefreshToken = await cls.create(
            session,
            id=str(uuid.uuid4()),
            user_id=user.id,
            once_expire_at=now_utc() + timedelta(minutes=once_refresh_token_expire_minutes)
            if once_refresh_token_expire_minutes else None,
            connection_expire_at=now_utc() + timedelta(minutes=connection_expire_minutes),

        )

        return new_token

    @classmethod
    async def get(
        cls,
        data: GetUserRefreshTokenInputModel,
        session: AsyncSession
    ) -> UserRefreshToken:
        """
            get enabled refresh token from id
        :param data:
        :param session:
        :return:
        """

        # get token to refresh
        refresh_token = await cls.get_by_id(data.refresh_token_id, session)
        debug_message = None

        if not refresh_token:
            debug_message = "Unknown refresh token with id '%s'" % data.refresh_token_id
        elif not refresh_token.enabled:
            debug_message = "Refresh token with id '%s' is revoked " % data.refresh_token_id

        if debug_message is not None:
            raise LysError(
                INVALID_REFRESH_TOKEN_ERROR,
                debug_message
            )

        return refresh_token

    @classmethod
    async def revoke(cls, data: GetUserRefreshTokenInputModel, session: AsyncSession) -> UserRefreshToken:
        """
            find refresh token and revoke if
        :param data:
        :param session:
        :return:
        """

        refresh_token = await cls.get(data, session=session)
        now = now_utc()

        # revoke all refresh token not revoked
        stmt = update(cls.entity_class).where(
            cls.entity_class.user_id == refresh_token.user_id,
            cls.entity_class.revoked_at == None
        ).values(
            revoked_at=now
        )

        await session.execute(stmt)

        return refresh_token

    @classmethod
    async def refresh(
            cls,
            data: GetUserRefreshTokenInputModel,
            session: AsyncSession = None
    ) -> UserRefreshToken:
        """
            replace current refresh token by a new one
        :param data:
        :param session:
        :return:
        """
        # get token to refresh
        refresh_token = await cls.revoke(data, session=session)
        new_token: UserRefreshToken = await cls.generate(refresh_token.user, session=session)

        return new_token

@register_service()
class UserOneTimeTokenService(EntityService[UserOneTimeToken], OneTimeTokenService):
    """
    Service for managing user one-time tokens.

    Provides user-specific token operations like password reset tokens,
    email verification tokens, etc.
    """
    pass


@register_service()
class UserEmailingService(EntityService[UserEmailing]):

    @classmethod
    async def create_password_reset_emailing(
        cls,
        user: User,
        session: AsyncSession
    ) -> UserEmailing:
        """
        Create the emailing for password reset.

        This method:
        1. Creates a one-time token for password reset
        2. Creates an emailing with the token link
        3. Links the emailing to the user

        The email will be sent via Celery task (call send_pending_email.delay in BackgroundTask)

        Args:
            user: User to send the email to
            session: Database session

        Returns:
            UserEmailing: The created user emailing entity
        """
        # Get services
        token_service = cls.app_manager.get_service("user_one_time_token")
        emailing_service = cls.app_manager.get_service("emailing")

        # 1. Create one-time token for password reset
        token = await token_service.create(
            session,
            user_id=user.id,
            type_id=PASSWORD_RESET_TOKEN_TYPE
        )

        # 2. Create emailing with token
        emailing = await emailing_service.generate_emailing(
            type_id=USER_PASSWORD_RESET_EMAILING_TYPE,
            email_address=user.email_address.id,
            language_id=user.language_id,
            session=session,
            user=user,
            token=str(token.id),
            front_url=cls.app_manager.settings.front_url,
            lang=user.language_id
        )

        # 3. Link emailing to user
        user_emailing = await cls.create(
            session,
            user_id=user.id,
            emailing_id=emailing.id
        )

        return user_emailing

    @classmethod
    async def create_email_verification_emailing(
        cls,
        user: User,
        session: AsyncSession
    ) -> UserEmailing:
        """
        Create the emailing to verify user email address.

        This method:
        1. Validates that the email is not already verified
        2. Updates last_validation_request_at on the email address
        3. Creates a one-time token for email verification (valid 24 hours)
        4. Creates an emailing with the token link
        5. Links the emailing to the user

        The email will be sent via Celery task (call send_pending_email.delay in BackgroundTask)

        Args:
            user: User to send the email to
            session: Database session

        Returns:
            UserEmailing: The created user emailing entity

        Raises:
            LysError: If email address is already validated
        """
        # 1. Check if email is already validated
        if user.email_address.validated_at is not None:
            raise LysError(
                EMAIL_ALREADY_VALIDATED_ERROR,
                f"Email address {user.email_address.id} is already validated"
            )

        # Get services
        token_service = cls.app_manager.get_service("user_one_time_token")
        emailing_service = cls.app_manager.get_service("emailing")

        # 2. Update last validation request timestamp
        user.email_address.last_validation_request_at = now_utc()

        # 3. Create one-time token for email verification (24 hours validity)
        token = await token_service.create(
            session,
            user_id=user.id,
            type_id=EMAIL_VERIFICATION_TOKEN_TYPE
        )

        # 4. Create emailing with token and user data
        emailing = await emailing_service.generate_emailing(
            type_id=USER_EMAIL_VERIFICATION_EMAILING_TYPE,
            email_address=user.email_address.id,
            language_id=user.language_id,
            session=session,
            user=user,
            token=str(token.id),
            front_url=cls.app_manager.settings.front_url
        )

        # 5. Link emailing to user
        user_emailing = await cls.create(
            session,
            user_id=user.id,
            emailing_id=emailing.id
        )

        return user_emailing

    @classmethod
    def schedule_send_emailing(cls, user_emailing: UserEmailing, background_tasks) -> None:
        """
        Schedule the emailing to be sent via Celery.

        This method should be called after the database session commits
        to ensure the emailing entity is persisted.

        Args:
            user_emailing: The user emailing entity to send
            background_tasks: FastAPI/Starlette background tasks manager
        """
        background_tasks.add_task(
            lambda: send_pending_email.delay(user_emailing.emailing_id)
        )


@register_service()
class UserAuditLogTypeService(EntityService[UserAuditLogType]):
    pass


@register_service()
class UserAuditLogService(EntityService[UserAuditLog]):
    """
    Service for managing user audit logs.

    Provides operations for:
    - Creating audit logs for status changes and anonymization (automatic)
    - Creating manual observations by administrators
    - Updating observations (owner only)
    - Soft deleting observations (owner only)
    - Listing and searching audit logs with filters
    """

    @classmethod
    async def create_audit_log(
        cls,
        target_user_id: str,
        author_user_id: str,
        log_type_id: str,
        message: str,
        session: AsyncSession
    ) -> UserAuditLog:
        """
        Create a new audit log entry.

        Args:
            target_user_id: ID of user being logged about
            author_user_id: ID of user creating the log
            log_type_id: Type of log (STATUS_CHANGE, ANONYMIZATION, OBSERVATION)
            message: Log message
            session: Database session

        Returns:
            UserAuditLog: Created audit log entity
        """
        audit_log = await cls.create(
            session,
            target_user_id=target_user_id,
            author_user_id=author_user_id,
            log_type_id=log_type_id,
            message=message
        )

        return audit_log

    @classmethod
    async def update_observation(
        cls,
        log: UserAuditLog,
        new_message: str,
        session: AsyncSession
    ) -> UserAuditLog:
        """
        Update an observation log message.

        Only OBSERVATION type logs can be updated.
        Permission check (OWNER) must be done at webservice level via lys_edition.

        Args:
            log: UserAuditLog entity to update (fetched by lys_edition)
            new_message: New message content
            session: Database session

        Returns:
            UserAuditLog: Updated audit log entity

        Raises:
            LysError: If log is not OBSERVATION type or already deleted
        """
        # Only OBSERVATION logs can be updated
        if log.log_type_id != OBSERVATION_LOG_TYPE:
            raise LysError(
                (403, "CANNOT_EDIT_SYSTEM_LOG"),
                "Only OBSERVATION logs can be edited. System logs (STATUS_CHANGE, ANONYMIZATION) are immutable."
            )

        # Check if already deleted
        if log.deleted_at is not None:
            raise LysError(
                (403, "CANNOT_EDIT_DELETED_LOG"),
                "Cannot edit a deleted observation"
            )

        # Update message
        log.message = new_message
        await session.flush()

        return log

    @classmethod
    async def delete_observation(
        cls,
        log: UserAuditLog,
        session: AsyncSession
    ) -> UserAuditLog:
        """
        Soft delete an observation log.

        Only OBSERVATION type logs can be deleted.
        Permission check (OWNER) must be done at webservice level via lys_edition.

        Args:
            log: UserAuditLog entity to delete (fetched by lys_edition)
            session: Database session

        Returns:
            UserAuditLog: Deleted audit log entity

        Raises:
            LysError: If log is not OBSERVATION type or already deleted
        """
        # Only OBSERVATION logs can be deleted
        if log.log_type_id != OBSERVATION_LOG_TYPE:
            raise LysError(
                (403, "CANNOT_DELETE_SYSTEM_LOG"),
                "Only OBSERVATION logs can be deleted. System logs (STATUS_CHANGE, ANONYMIZATION) are immutable."
            )

        # Check if already deleted
        if log.deleted_at is not None:
            raise LysError(
                (403, "ALREADY_DELETED"),
                "This observation is already deleted"
            )

        # Soft delete
        log.deleted_at = now_utc()
        await session.flush()

        return log

    @classmethod
    def list_audit_logs(
        cls,
        log_type_id: str | None = None,
        email_search: str | None = None,
        user_filter: str | None = None,
        include_deleted: bool = False
    ):
        """
        Build query to list audit logs with optional filters.

        This method returns a statement for lys_connection to execute.

        Args:
            log_type_id: Filter by log type (optional)
            email_search: Search in target or author email addresses (optional)
            user_filter: Filter by user role - "author", "target", or None (both) (optional)
            include_deleted: Include soft-deleted observations (default: False)

        Returns:
            SQLAlchemy select statement
        """
        # Get user email address entity
        user_email_address_entity = cls.app_manager.get_entity("user_email_address")

        # Build base query
        stmt = select(cls.entity_class)

        # Filter by log type
        if log_type_id:
            stmt = stmt.where(cls.entity_class.log_type_id == log_type_id)

        # Filter deleted observations
        if not include_deleted:
            stmt = stmt.where(cls.entity_class.deleted_at == None)

        # Email search (search in both target and author emails)
        if email_search:
            # Join with user_email_address for target_user
            target_email_alias = user_email_address_entity.__table__.alias("target_email")
            author_email_alias = user_email_address_entity.__table__.alias("author_email")

            stmt = stmt.join(
                target_email_alias,
                cls.entity_class.target_user_id == target_email_alias.c.user_id
            ).join(
                author_email_alias,
                cls.entity_class.author_user_id == author_email_alias.c.user_id
            )

            # Apply email filter based on user_filter
            if user_filter == "author":
                stmt = stmt.where(author_email_alias.c.id.ilike(f"%{email_search}%"))
            elif user_filter == "target":
                stmt = stmt.where(target_email_alias.c.id.ilike(f"%{email_search}%"))
            else:  # None - search in both
                stmt = stmt.where(
                    or_(
                        target_email_alias.c.id.ilike(f"%{email_search}%"),
                        author_email_alias.c.id.ilike(f"%{email_search}%")
                    )
                )

        # Order by created_at desc (most recent first)
        stmt = stmt.order_by(cls.entity_class.created_at.desc())

        return stmt
