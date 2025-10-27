import uuid
from datetime import datetime, timedelta

import bcrypt
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from lys.apps.user_auth.errors import INVALID_REFRESH_TOKEN_ERROR
from lys.apps.user_auth.modules.user.entities import UserStatus, User, UserEmailAddress, UserRefreshToken
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