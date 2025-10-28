import uuid
from datetime import datetime, timedelta

import bcrypt
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from lys.apps.base.modules.emailing.consts import FORGOTTEN_PASSWORD_EMAILING_TYPE
from lys.apps.base.modules.emailing.services import EmailingService
from lys.apps.base.modules.one_time_token.services import OneTimeTokenService
from lys.apps.user_auth.errors import INVALID_REFRESH_TOKEN_ERROR
from lys.apps.user_auth.modules.user.entities import UserStatus, User, UserEmailAddress, UserRefreshToken, UserEmailing, UserOneTimeToken
from lys.apps.user_auth.modules.user.models import GetUserRefreshTokenInputModel
from lys.apps.user_auth.utils import AuthUtils
from lys.core.errors import LysError
from lys.core.registers import register_service
from lys.core.services import EntityService


@register_service()
class UserStatusService(EntityService[UserStatus]):
    pass


@register_service()
class UserEmailAddressService(EntityService[UserEmailAddress]):
    pass


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
        email_address_service = cls.get_service_by_name("user_email_address")

        # Query user by email address - join on user_id = User.id
        stmt = (
            select(cls.entity_class)
            .join(email_address_service.entity_class)
            .where(email_address_service.entity_class.id == email)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()


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
            once_expire_at=datetime.now() + timedelta(minutes=once_refresh_token_expire_minutes)
            if once_refresh_token_expire_minutes else None,
            connection_expire_at=datetime.now() + timedelta(minutes=connection_expire_minutes),

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
        now = datetime.now()

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
        token_service = cls.get_service_by_name("user_one_time_token")
        emailing_service = cls.get_service_by_name("emailing")

        # 1. Create one-time token for password reset
        from lys.apps.base.modules.one_time_token.consts import FORGOTTEN_PASSWORD_TOKEN_TYPE

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
