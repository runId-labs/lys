import strawberry
from starlette.responses import Response

from lys.apps.user_auth.consts import REFRESH_COOKIE_KEY
from lys.apps.user_auth.errors import INVALID_REFRESH_TOKEN_ERROR, BLOCKED_USER_ERROR
from lys.apps.user_auth.modules.auth.inputs import LoginInput
from lys.apps.user_auth.modules.auth.nodes import LoginNode, LogoutNode
from lys.apps.user_auth.modules.auth.services import AuthService
from lys.apps.user_auth.modules.user.consts import ENABLED_USER_STATUS
from lys.apps.user_auth.modules.user.models import GetUserRefreshTokenInputModel
from lys.apps.user_auth.modules.user.nodes import UserNode
from lys.apps.user_auth.modules.user.services import UserRefreshTokenService
from lys.apps.user_auth.utils import AuthUtils
from lys.core.contexts import Info
from lys.core.errors import LysError
from lys.core.graphql.fields import lys_field
from lys.core.graphql.registers import register_mutation
from lys.core.graphql.types import Mutation


@register_mutation("auth")
@strawberry.type
class AuthTokenMutation(Mutation):
    @lys_field(
        ensure_type=LoginNode,
        is_public="disconnected",
        is_licenced=False,
        description="Log user via password and return some information about him/her."
    )
    async def login(self, inputs: LoginInput, info: Info) -> LoginNode:
        node: type[LoginNode] = LoginNode.get_effective_node()
        auth_service: type[AuthService] | None = node.service_class

        response: Response = info.context.response
        session = info.context.session

        user, claims = await auth_service.login(inputs.to_pydantic(), response, session)

        user_node_class: type[UserNode] = node.get_node_by_name("UserNode")

        return node(
            access_token_expire_in=claims["exp"],
            xsrf_token=claims["xsrf_token"],
            user=user_node_class.from_obj(user)
        )

    @lys_field(
        ensure_type=LoginNode,
        is_public=True,
        is_licenced=False,
        description="Create a new access token based on the refresh one in request header."
    )
    async def refresh_access_token(self, info: Info) -> LoginNode:
        node = LoginNode.get_effective_node()
        auth_utils = AuthUtils()
        auth_service: type[AuthService] = node.service_class
        refresh_token_service: type[UserRefreshTokenService] = auth_service.app_manager.get_service("user_refresh_token")

        request = info.context.request
        response: Response = info.context.response
        session = info.context.session

        # get refresh token from cookie
        refresh_token_id = request.cookies.get(REFRESH_COOKIE_KEY)

        # validate refresh token exists
        if not refresh_token_id:
            await auth_service.clear_auth_cookies(response)
            raise LysError(
                INVALID_REFRESH_TOKEN_ERROR,
                "Missing refresh token in cookie"
            )

        try:
            refresh_token_used_once = auth_utils.config.get("refresh_token_used_once", False)
            if refresh_token_used_once:
                refresh_token = await refresh_token_service.refresh(
                    GetUserRefreshTokenInputModel(refresh_token_id=refresh_token_id),
                    session=session
                )
            else:
                refresh_token = await refresh_token_service.get(
                    GetUserRefreshTokenInputModel(refresh_token_id=refresh_token_id),
                    session=session
                )

            # validate user status before generating new access token
            if refresh_token.user.status_id != ENABLED_USER_STATUS:
                raise LysError(
                    BLOCKED_USER_ERROR,
                    "User account has been blocked"
                )

        except LysError:
            # Clear cookies only for known authentication errors
            await auth_service.clear_auth_cookies(response)
            raise
        # System errors are NOT caught - they will be logged by the middleware

        # generate the user access token
        access_token, claims = await auth_service.generate_access_token(refresh_token.user)

        # set authentication cookies
        await auth_service.set_auth_cookies(response, refresh_token.id, access_token)

        user_node_class: type[UserNode] = node.get_node_by_name("UserNode")

        return node(
            access_token_expire_in=claims["exp"],
            xsrf_token=claims["xsrf_token"],
            user=user_node_class.from_obj(refresh_token.user)
        )

    @lys_field(
        ensure_type=LogoutNode,
        is_public=True,
        is_licenced=False,
        description="Disconnect user by removing his/her refresh token."
    )
    async def logout(self, info: Info) -> LogoutNode:
        node = LogoutNode.get_effective_node()
        auth_service: type[AuthService] = node.service_class

        session = info.context.session

        await auth_service.logout(info.context.request, info.context.response, session)

        # success result
        return node(
            succeed=True
        )