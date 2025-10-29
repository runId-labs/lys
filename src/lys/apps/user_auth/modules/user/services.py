import uuid
from datetime import datetime, timedelta

import bcrypt
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from lys.apps.base.modules.emailing.consts import FORGOTTEN_PASSWORD_EMAILING_TYPE
from lys.apps.base.modules.one_time_token.consts import FORGOTTEN_PASSWORD_TOKEN_TYPE
from lys.apps.base.modules.one_time_token.services import OneTimeTokenService
from lys.apps.base.tasks import send_pending_email
from lys.apps.user_auth.errors import INVALID_REFRESH_TOKEN_ERROR, INVALID_GENDER, INVALID_LANGUAGE
from lys.apps.user_auth.modules.user.entities import (
    UserStatus,
    User,
    UserEmailAddress,
    UserRefreshToken,
    UserEmailing,
    UserOneTimeToken,
    Gender,
    UserPrivateData
)
from lys.apps.user_auth.modules.user.models import GetUserRefreshTokenInputModel
from lys.apps.user_auth.utils import AuthUtils
from lys.core.errors import LysError
from lys.core.registers import register_service
from lys.core.services import EntityService
from lys.core.utils.datetime import now_utc


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
        from sqlalchemy import select

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
        from sqlalchemy import select

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
    async def create_super_user(
        cls,
        email: str,
        password: str,
        language_id: str,
        session: AsyncSession,
        first_name: str | None = None,
        last_name: str | None = None,
        gender_id: str | None = None
    ) -> User:
        """
        Create a new super user with full validation.

        This method performs all necessary validations and creates the user with:
        - Email address entity
        - Hashed password
        - Super user privileges
        - Optional private data (GDPR-protected)

        Args:
            email: Email address (will be normalized)
            password: Plain text password (will be hashed)
            language_id: Language ID (format validated)
            session: Database session
            first_name: Optional first name
            last_name: Optional last name
            gender_id: Optional gender ID

        Returns:
            User: The created super user entity

        Raises:
            LysError: If email already exists, language doesn't exist, or gender doesn't exist
        """
        from lys.apps.user_auth.errors import USER_ALREADY_EXISTS
        from lys.apps.user_auth.utils import AuthUtils

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

        # 6. Create private data entity (even if fields are None)
        private_data = user_private_data_service.entity_class(
            id=str(uuid.uuid4()),
            first_name=first_name,
            last_name=last_name,
            gender_id=gender_id
        )

        # 7. Create user with super user privileges
        user = await cls.create(
            session,
            email_address=email_address,
            password=hashed_password,
            is_super_user=True,
            language_id=language_id,
            private_data=private_data
        )

        return user


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
class UserOneTimeTokenService(OneTimeTokenService, EntityService[UserOneTimeToken]):
    """
    Service for managing user one-time tokens.

    Provides user-specific token operations like password reset tokens,
    email verification tokens, etc.
    """
    pass


@register_service()
class UserEmailingService(EntityService[UserEmailing]):

    @classmethod
    async def create_forgotten_password_emailing(
        cls,
        user: User,
        session: AsyncSession
    ) -> UserEmailing:
        """
        Create the emailing to retrieve the user forgotten password.

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
            type_id=FORGOTTEN_PASSWORD_TOKEN_TYPE
        )

        # 2. Create emailing with token
        emailing = await emailing_service.generate_emailing(
            type_id=FORGOTTEN_PASSWORD_EMAILING_TYPE,
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
