import os
from datetime import datetime, timedelta
from typing import Optional, Type

import jwt
from sqlalchemy import select, ColumnElement
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Relationship, ColumnProperty, InstrumentedAttribute
from starlette.requests import Request
from starlette.responses import Response

from lys.apps.user_auth.consts import REFRESH_COOKIE_KEY, ACCESS_COOKIE_KEY
from lys.apps.user_auth.errors import BLOCKED_USER_ERROR, WRONG_CREDENTIALS_ERROR
from lys.apps.user_auth.modules.auth.consts import FAILED_LOGIN_ATTEMPT_STATUS, SUCCEED_LOGIN_ATTEMPT_STATUS
from lys.apps.user_auth.modules.auth.entities import UserLoginAttempt, LoginAttemptStatus
from lys.apps.user_auth.modules.auth.models import LoginInputModel
from lys.apps.user_auth.modules.user.consts import ENABLED_USER_STATUS
from lys.apps.user_auth.modules.user.entities import User
from lys.apps.user_auth.modules.user.models import GetUserRefreshTokenInputModel
from lys.apps.user_auth.modules.user.services import UserService, UserRefreshTokenService
from lys.apps.user_auth.utils import AuthUtils
from lys.core.errors import LysError
from lys.core.registers import register_service
from lys.core.services import Service, EntityService


@register_service()
class LoginAttemptStatusService(EntityService[LoginAttemptStatus]):
    pass


@register_service()
class AuthService(Service):
    service_name = "auth"
    auth_utils = AuthUtils()

    @classmethod
    async def get_user_from_login(cls, login: str, session: AsyncSession) \
            -> Optional[User]:
        """
        Get user from login
        :param login: username or email address etc...
        :param session: database session
        :return:
        """
        user_class: Type[User] = cls.get_entity_by_name("user")

        user: User | None = None
        inner_clause: ColumnElement | None = None
        attribute: InstrumentedAttribute = getattr(user_class, user_class.login_name())

        if isinstance(attribute.property, Relationship):
            # foreign key
            inner_clause = attribute.has(id=login)

        elif isinstance(attribute, ColumnProperty):
            # entity attribute
            inner_clause = attribute == login

        if inner_clause is not None:
            stmt = select(user_class).where(inner_clause).limit(1)
            result = await session.execute(stmt)
            user: User | None = result.scalars().one_or_none()

        return user

    @classmethod
    async def get_user_last_login_attempt(cls, user: User, status_id: str, session: AsyncSession) \
            -> Optional[UserLoginAttempt]:
        user_login_attempt_entity: Type[UserLoginAttempt] = cls.get_entity_by_name("user_login_attempt")

        stmt = select(user_login_attempt_entity).where(
            user_login_attempt_entity.status_id == status_id,
            user_login_attempt_entity.user == user,
        ).order_by(user_login_attempt_entity.created_at.desc()).limit(1)
        result = await session.execute(stmt)
        user_login_attempt_obj: Optional[UserLoginAttempt] = result.scalars().one_or_none()

        return user_login_attempt_obj

    @classmethod
    async def authenticate_user(
            cls,
            login: str,
            password: str,
            session: AsyncSession
    ) -> User:
        """
        User authentication process via login and password
        :param login:
        :param password:
        :param session:
        :return:
        """
        user_login_attempt_entity: Type[UserLoginAttempt] = cls.get_entity_by_name("user_login_attempt")
        user_service: Type[UserService] = cls.get_service_by_name("user")

        # get user from email address
        user = await cls.get_user_from_login(login, session)

        if user:
            # check if the user is allowed to log in the application
            if not user.status_id == ENABLED_USER_STATUS:
                raise LysError(
                    BLOCKED_USER_ERROR,
                    "user with '%s' has been blocked" % login
                )

            # get user last failed login attempt
            user_login_attempt_obj = await cls.get_user_last_login_attempt(user, FAILED_LOGIN_ATTEMPT_STATUS,
                                                                           session)

            user_login_attempt_status_id = SUCCEED_LOGIN_ATTEMPT_STATUS

            # if it is the wrong password, it is a failed login attempt
            if not user_service.check_password(user, password):
                user_login_attempt_status_id = FAILED_LOGIN_ATTEMPT_STATUS

            # if there is no failed login attempt, create one with the right status
            if not user_login_attempt_obj:
                user_login_attempt_obj = user_login_attempt_entity(
                    status_id=user_login_attempt_status_id,
                    user_id=user.id,
                    attempt_count=1
                )
                session.add(user_login_attempt_obj)
            # else update it
            else:
                user_login_attempt_obj.status_id = user_login_attempt_status_id
                user_login_attempt_obj.attempt_count += 1

            # if the login failed, don't send the user
            if user_login_attempt_status_id == FAILED_LOGIN_ATTEMPT_STATUS:
                user = None

        return user

    @classmethod
    async def login(cls, data: LoginInputModel, response: Response, session: AsyncSession):
        refresh_token_service: Type[UserRefreshTokenService] = cls.get_service_by_name("user_refresh_token")

        # find out the user based on his email address and his password
        user = await cls.authenticate_user(data.login, data.password, session)

        if not user:
            raise LysError(
                WRONG_CREDENTIALS_ERROR,
                "unknown user with login '%s' with specified password" % data.login
            )

        # generate the user refresh token
        refresh_token = await refresh_token_service.generate(user, session=session)
        # generate the user access token
        access_token, claims = await cls.generate_access_token(user)

        await cls.set_cookie(response, REFRESH_COOKIE_KEY, refresh_token.id, "/auth")
        await cls.set_cookie(response, ACCESS_COOKIE_KEY, access_token, "/graphql")

        # success result
        return user, claims

    @classmethod
    async def logout(cls, request: Request, response: Response, session: AsyncSession):
        refresh_token_service: Type[UserRefreshTokenService] = cls.get_service_by_name("user_refresh_token")

        refresh_token_id = request.cookies.get(REFRESH_COOKIE_KEY)
        await refresh_token_service.revoke(
            GetUserRefreshTokenInputModel(refresh_token_id=refresh_token_id),
            session=session
        )

        # delete refresh and access cookie
        response.delete_cookie(REFRESH_COOKIE_KEY, path="/auth")
        response.delete_cookie(ACCESS_COOKIE_KEY, path="/graphql")

    @staticmethod
    async def generate_xsrf_token():
        return os.urandom(64).hex().encode("ascii")

    @classmethod
    async def generate_access_token(cls, user: User) -> tuple[str, dict[str, datetime | str]]:
        access_token_expire_minutes = cls.auth_utils.config.get("access_token_expire_minutes")
        claims = {
                "user": {
                    "id": str(user.id),
                    "is_super_user": user.is_super_user,
                },
                "exp": int(round((datetime.now() + timedelta(minutes=access_token_expire_minutes)).timestamp())),
                "xsrf_token": str(await cls.generate_xsrf_token())
            }
        return jwt.encode(
            claims,
            cls.auth_utils.secret_key,
            algorithm=cls.auth_utils.config.get("encryption_algorithm"),
        ), claims

    @classmethod
    async def set_cookie(cls, response: Response, key: str, value: str, path: str):
        response.set_cookie(
            key=key,
            value=value,
            secure=cls.auth_utils.config.get("cookie_secure"),
            httponly=cls.auth_utils.config.get("cookie_http_only"),
            samesite=cls.auth_utils.config.get("cookie_same_site"),
            expires=(datetime.now() + timedelta(weeks=1)).strftime("%a, %d %b %Y %H:%M:%S GMT"),
            domain=cls.auth_utils.config.get("cookie_domain"),
            path=path
        )

