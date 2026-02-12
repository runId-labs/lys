import bcrypt
import bcrypt
import logging
import os
from datetime import datetime, timedelta
from typing import Optional, Type

from sqlalchemy import select, ColumnElement, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Relationship, ColumnProperty, InstrumentedAttribute
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)

from lys.apps.user_auth.consts import REFRESH_COOKIE_KEY, ACCESS_COOKIE_KEY, XSRF_COOKIE_KEY
from lys.apps.user_auth.errors import INVALID_CREDENTIALS_ERROR, RATE_LIMIT_ERROR
from lys.core.consts.webservices import (
    NO_LIMITATION_WEBSERVICE_PUBLIC_TYPE,
    CONNECTED_ACCESS_LEVEL,
    OWNER_ACCESS_LEVEL,
)
from lys.apps.user_auth.modules.auth.consts import FAILED_LOGIN_ATTEMPT_STATUS, SUCCEED_LOGIN_ATTEMPT_STATUS
from lys.apps.user_auth.modules.auth.entities import UserLoginAttempt, LoginAttemptStatus
from lys.apps.user_auth.modules.auth.models import LoginInputModel
from lys.apps.user_auth.modules.user.consts import ENABLED_USER_STATUS
from lys.apps.user_auth.modules.user.entities import User
from lys.apps.user_auth.modules.user.models import GetUserRefreshTokenInputModel
from lys.apps.user_auth.modules.user.services import UserService, UserRefreshTokenService
from lys.apps.user_auth.utils import AuthUtils
from lys.core.errors import LysError
from lys.core.registries import register_service
from lys.core.services import Service, EntityService
from lys.core.utils.datetime import now_utc

# Pre-computed bcrypt hash of a dummy password, used when user doesn't exist.
# This ensures bcrypt runs even for non-existent users, equalizing response time
# and preventing user enumeration via timing side-channel.
_DUMMY_HASH = bcrypt.hashpw(b"dummy-password-for-timing", bcrypt.gensalt()).decode("utf-8")


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
        user_class: Type[User] = cls.app_manager.get_entity("user")

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
    async def get_user_last_login_attempt(cls, user: User, session: AsyncSession) \
            -> Optional[UserLoginAttempt]:
        """
        Get the last login attempt for a user (any status).

        :param user: User entity
        :param session: Database session
        :return: Last login attempt or None
        """
        user_login_attempt_entity: Type[UserLoginAttempt] = cls.app_manager.get_entity("user_login_attempt")

        stmt = select(user_login_attempt_entity).where(
            user_login_attempt_entity.user == user,
        ).order_by(user_login_attempt_entity.created_at.desc()).limit(1)
        result = await session.execute(stmt)
        user_login_attempt_obj: Optional[UserLoginAttempt] = result.scalars().one_or_none()

        return user_login_attempt_obj

    @classmethod
    def _get_lockout_duration(cls, attempt_count: int) -> int:
        """
        Get lockout duration in seconds based on attempt count.
        Uses progressive lockout strategy from configuration.

        :param attempt_count: Number of failed attempts
        :return: Lockout duration in seconds
        """
        lockout_durations = cls.auth_utils.config.get("login_lockout_durations", {3: 60, 5: 900})

        # Find the appropriate lockout duration
        for threshold in sorted(lockout_durations.keys(), reverse=True):
            if attempt_count >= threshold:
                return lockout_durations[threshold]

        return 0

    @classmethod
    async def authenticate_user(
            cls,
            login: str,
            password: str,
            session: AsyncSession
    ) -> User:
        """
        User authentication process via login and password with rate limiting.

        Security design:
        - All failure paths raise INVALID_CREDENTIALS_ERROR (prevents user enumeration)
        - When user doesn't exist, a dummy bcrypt hash is checked (equalizes timing)
        - Rate limiting is checked before user status (prevents disabled user enumeration)
        - User status is checked after password validation

        Login attempt tracking logic:
        - Failed after success: Create new line with status=failed, attempt_count=1
        - Failed after failed: Increment attempt_count on existing line
        - Success after failed: Create new line with status=success, attempt_count=1
        - Success after success: Create new line with status=success, attempt_count=1

        This maintains complete history while keeping the database optimized.

        :param login: User login identifier
        :param password: User password
        :param session: Database session
        :return: Authenticated user or None
        :raises LysError: If credentials are invalid or rate limited
        """
        user_login_attempt_entity: Type[UserLoginAttempt] = cls.app_manager.get_entity("user_login_attempt")
        user_service: Type[UserService] = cls.app_manager.get_service("user")

        # get user from login identifier
        user = await cls.get_user_from_login(login, session)

        if user is None:
            # User not found: run dummy bcrypt to equalize timing with real password check
            bcrypt.checkpw(password.encode("utf-8"), _DUMMY_HASH.encode("utf-8"))
            raise LysError(INVALID_CREDENTIALS_ERROR, f"unknown user with login '{login}'")

        # get user last login attempt (any status)
        last_login_attempt = await cls.get_user_last_login_attempt(user, session)

        # check rate limiting BEFORE revealing user status
        rate_limit_enabled = cls.auth_utils.config.get("login_rate_limit_enabled", True)

        if rate_limit_enabled and last_login_attempt and \
           last_login_attempt.status_id == FAILED_LOGIN_ATTEMPT_STATUS and \
           last_login_attempt.blocked_until:
            now = now_utc()
            if now < last_login_attempt.blocked_until:
                remaining_seconds = int((last_login_attempt.blocked_until - now).total_seconds())
                raise LysError(
                    RATE_LIMIT_ERROR,
                    f"Too many failed login attempts for user '{login}'. Try again in {remaining_seconds} seconds.",
                    extensions={
                        "remaining_seconds": remaining_seconds,
                        "attempt_count": last_login_attempt.attempt_count
                    }
                )

        # verify password (bcrypt runs here for real users)
        if user.password is None:
            # SSO-only user — run dummy hash to equalize timing, then fail
            bcrypt.checkpw(password.encode("utf-8"), _DUMMY_HASH.encode("utf-8"))
            raise LysError(INVALID_CREDENTIALS_ERROR, f"unknown user with login '{login}'")

        password_valid = user_service.check_password(user, password)

        # handle failed login attempt
        if not password_valid:
            # check if we should reuse existing failed line or create new one
            if last_login_attempt and last_login_attempt.status_id == FAILED_LOGIN_ATTEMPT_STATUS:
                # failed after failed: increment attempt count on existing line
                last_login_attempt.attempt_count += 1
                attempt_count = last_login_attempt.attempt_count
                user_login_attempt_obj = last_login_attempt
            else:
                # failed after success (or no previous attempt): create new failed line
                user_login_attempt_obj = user_login_attempt_entity(
                    status_id=FAILED_LOGIN_ATTEMPT_STATUS,
                    user_id=user.id,
                    attempt_count=1,
                    blocked_until=None
                )
                session.add(user_login_attempt_obj)
                attempt_count = 1

            # calculate lockout duration based on attempt count
            lockout_duration = 0
            if rate_limit_enabled:
                lockout_duration = cls._get_lockout_duration(attempt_count)
                if lockout_duration > 0:
                    user_login_attempt_obj.blocked_until = now_utc() + timedelta(seconds=lockout_duration)

            # log failed login attempt
            logger.warning(
                f"Failed login attempt for user '{login}' - "
                f"Attempt #{attempt_count}"
                + (f" - Blocked for {lockout_duration} seconds" if lockout_duration > 0 else "")
            )

            user = None
        else:
            # check user status AFTER password validation (prevents blocked user enumeration)
            if user.status_id != ENABLED_USER_STATUS:
                raise LysError(INVALID_CREDENTIALS_ERROR, f"user '{login}' is blocked")

            # successful login: always create new success line
            user_login_attempt_obj = user_login_attempt_entity(
                status_id=SUCCEED_LOGIN_ATTEMPT_STATUS,
                user_id=user.id,
                attempt_count=1,
                blocked_until=None
            )
            session.add(user_login_attempt_obj)

            # log successful login
            logger.info(f"Successful login for user '{login}'")

        return user

    @classmethod
    async def login(cls, data: LoginInputModel, response: Response, session: AsyncSession):
        refresh_token_service: Type[UserRefreshTokenService] = cls.app_manager.get_service("user_refresh_token")

        # find out the user based on his email address and his password
        try:
            user = await cls.authenticate_user(data.login, data.password, session)
        except LysError:
            # commit login attempt state before raising exception
            await session.commit()
            raise

        if not user:
            # commit failed login attempt to database before raising exception
            await session.commit()

            raise LysError(
                INVALID_CREDENTIALS_ERROR,
                "wrong password for user '%s'" % data.login
            )

        # generate the user refresh token
        refresh_token = await refresh_token_service.generate(user, session=session)
        # generate the user access token
        access_token, claims = await cls.generate_access_token(user, session)

        # set authentication cookies
        await cls.set_auth_cookies(response, refresh_token.id, access_token, claims.get("xsrf_token"))

        # success result
        return user, claims

    @classmethod
    async def logout(cls, request: Request, response: Response, session: AsyncSession):
        refresh_token_service: Type[UserRefreshTokenService] = cls.app_manager.get_service("user_refresh_token")

        refresh_token_id = request.cookies.get(REFRESH_COOKIE_KEY)

        # only revoke if refresh token exists
        if refresh_token_id:
            await refresh_token_service.revoke(
                GetUserRefreshTokenInputModel(refresh_token_id=refresh_token_id),
                session=session
            )

        # delete refresh and access cookie
        await cls.clear_auth_cookies(response)

    @staticmethod
    async def generate_xsrf_token():
        return os.urandom(64).hex().encode("ascii")

    @classmethod
    async def generate_access_claims(cls, user: User, session: AsyncSession) -> dict:
        """
        Generate JWT claims for access token.

        This method builds the claims dictionary for the access token.
        It is designed to be overridden by subclasses to add additional claims.

        =======================================================================
        OVERRIDE CHAIN - DO NOT MODIFY WITHOUT UNDERSTANDING THE FULL CHAIN
        =======================================================================

        This method is part of an inheritance chain:

            AuthService.generate_access_claims()  [THIS METHOD]
                → Handles: PUBLIC, CONNECTED, OWNER access levels
                → Returns: {"sub", "is_super_user", "webservices"}

                    ↓ super()

            RoleAuthService.generate_access_claims()  [lys.apps.user_role]
                → Adds: ROLE access level webservices
                → Merges into: webservices dict

                    ↓ super()

            OrganizationAuthService.generate_access_claims()  [lys.apps.organization]
                → Adds: ORGANIZATION_ROLE access level
                → Adds: "organizations" claim

        Each subclass MUST call super() first, then extend the claims.

        NOTE: For super_users, subclasses skip adding webservices because:
        - The permission layer grants super_users access to everything
        - AI tool filtering (AIToolService) bypasses JWT filtering for super_users
        =======================================================================

        Base claims include:
        - sub: user ID (standard JWT claim for subject)
        - is_super_user: boolean indicating super user status
        - webservices: dict mapping webservice names to access type ("full" or "owner")

        The webservices claim includes:
        - Public webservices with NO_LIMITATION type (accessible when connected)
        - Webservices with CONNECTED_ACCESS_LEVEL
        - Webservices with OWNER_ACCESS_LEVEL

        Args:
            user: The authenticated user entity
            session: Database session for additional queries

        Returns:
            Dictionary of claims to include in the JWT
        """
        # Get base webservices accessible to any connected user
        webservices = await cls._get_base_webservices(session)

        return {
            "sub": str(user.id),
            "is_super_user": user.is_super_user,
            "webservices": webservices,
        }

    @classmethod
    async def _get_base_webservices(cls, session: AsyncSession) -> dict[str, str]:
        """
        Get webservices accessible to any connected user with their access type.

        Includes:
        - Public webservices with NO_LIMITATION type -> "full"
        - Webservices with CONNECTED_ACCESS_LEVEL enabled -> "full"
        - Webservices with OWNER_ACCESS_LEVEL enabled -> "owner" (unless also has CONNECTED)

        Args:
            session: Database session

        Returns:
            Dict mapping webservice name to access type ("full" or "owner")
        """
        webservice_entity = cls.app_manager.get_entity("webservice")
        access_level_entity = cls.app_manager.get_entity("access_level")

        # Query webservices that are:
        # 1. Public with NO_LIMITATION type, OR
        # 2. Have CONNECTED_ACCESS_LEVEL enabled, OR
        # 3. Have OWNER_ACCESS_LEVEL enabled
        stmt = (
            select(webservice_entity)
            .where(
                or_(
                    # Public NO_LIMITATION webservices (public_type_id is not null means is_public)
                    webservice_entity.public_type_id == NO_LIMITATION_WEBSERVICE_PUBLIC_TYPE,
                    # CONNECTED access level
                    webservice_entity.access_levels.any(
                        access_level_entity.id == CONNECTED_ACCESS_LEVEL,
                        enabled=True
                    ),
                    # OWNER access level
                    webservice_entity.access_levels.any(
                        access_level_entity.id == OWNER_ACCESS_LEVEL,
                        enabled=True
                    )
                )
            )
        )
        result = await session.execute(stmt)
        webservices = list(result.scalars().all())

        # Determine access type for each webservice
        webservice_access = {}
        for ws in webservices:
            # Load access_levels if needed
            await session.refresh(ws, ["access_levels"])

            enabled_access_levels = [al.id for al in ws.access_levels if al.enabled]

            # Public NO_LIMITATION or CONNECTED = full access
            # Note: ws.id is the webservice name (ParametricEntity uses id as business key)
            if ws.is_public and ws.public_type_id == NO_LIMITATION_WEBSERVICE_PUBLIC_TYPE:
                webservice_access[ws.id] = "full"
            elif CONNECTED_ACCESS_LEVEL in enabled_access_levels:
                webservice_access[ws.id] = "full"
            elif OWNER_ACCESS_LEVEL in enabled_access_levels:
                # OWNER only = filtered access
                webservice_access[ws.id] = "owner"

        return webservice_access

    @classmethod
    async def generate_access_token(cls, user: User, session: AsyncSession = None) -> tuple[str, dict]:
        """
        Generate a JWT access token for the user.

        Args:
            user: The authenticated user entity
            session: Database session for additional queries (optional for backward compatibility)

        Returns:
            Tuple of (encoded_token, claims_dict)
        """
        access_token_expire_minutes = cls.auth_utils.config.get("access_token_expire_minutes")

        # Build claims from generate_access_claims (can be overridden by subclasses)
        claims = await cls.generate_access_claims(user, session)

        # Add standard JWT claims
        claims["exp"] = int(round((now_utc() + timedelta(minutes=access_token_expire_minutes)).timestamp()))
        claims["xsrf_token"] = str(await cls.generate_xsrf_token())

        # Debug: log generated claims
        logger.debug(f"Generated JWT claims: {claims}")

        return await cls.auth_utils.encode(claims), claims

    @classmethod
    async def clear_auth_cookies(cls, response: Response) -> None:
        """
        Clear authentication cookies (refresh and access tokens).

        Both cookies use path="/" (industry standard).
        Security is enforced by server-side validation:
        - UserAuthMiddleware extracts and validates ONLY the access token
        - Refresh token is explicitly extracted only in auth operations (login, logout, refresh)

        Args:
            response: Starlette response object
        """
        response.delete_cookie(REFRESH_COOKIE_KEY, path="/")
        response.delete_cookie(ACCESS_COOKIE_KEY, path="/")
        response.delete_cookie(XSRF_COOKIE_KEY, path="/")

    @classmethod
    async def set_auth_cookies(
        cls,
        response: Response,
        refresh_token_id: str,
        access_token: str,
        xsrf_token: str = None
    ) -> None:
        """
        Set refresh, access, and XSRF token cookies.

        All cookies use path="/" (industry standard).
        Security is enforced by server-side validation:
        - UserAuthMiddleware extracts and validates ONLY the access token
        - Refresh token is explicitly extracted only in auth operations (login, logout, refresh)
        - XSRF cookie is non-httpOnly (readable by JS) for the Double Submit Cookie pattern

        This provides defense-in-depth: even if both cookies are sent to all endpoints,
        only the appropriate token is used based on server-side logic.

        Args:
            response: Starlette response object
            refresh_token_id: Refresh token ID to store in cookie
            access_token: Access token to store in cookie
            xsrf_token: XSRF token to store in a JS-readable cookie
        """
        await cls.set_cookie(response, REFRESH_COOKIE_KEY, refresh_token_id, "/")
        await cls.set_cookie(response, ACCESS_COOKIE_KEY, access_token, "/")

        if xsrf_token:
            # XSRF cookie: same settings but NOT httpOnly (must be readable by JavaScript)
            response.set_cookie(
                key=XSRF_COOKIE_KEY,
                value=xsrf_token,
                secure=cls.auth_utils.config.get("cookie_secure", True),
                httponly=False,
                samesite=cls.auth_utils.config.get("cookie_same_site", "Lax"),
                expires=(now_utc() + timedelta(weeks=1)).strftime("%a, %d %b %Y %H:%M:%S GMT"),
                domain=cls.auth_utils.config.get("cookie_domain"),
                path="/"
            )

    @classmethod
    async def set_cookie(cls, response: Response, key: str, value: str, path: str):
        response.set_cookie(
            key=key,
            value=value,
            secure=cls.auth_utils.config.get("cookie_secure", True),
            httponly=cls.auth_utils.config.get("cookie_http_only", True),
            samesite=cls.auth_utils.config.get("cookie_same_site", "Lax"),
            expires=(now_utc() + timedelta(weeks=1)).strftime("%a, %d %b %Y %H:%M:%S GMT"),
            domain=cls.auth_utils.config.get("cookie_domain"),
            path=path
        )

