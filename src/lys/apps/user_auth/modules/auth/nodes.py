import strawberry

from lys.apps.user_auth.modules.auth.services import AuthService
from lys.apps.user_auth.modules.user.nodes import UserNode
from lys.core.graphql.nodes import ServiceNode
from lys.core.registers import register_node


@register_node()
class LoginNode(ServiceNode[AuthService]):
    success: bool
    message: str = "Successfully authenticated"
    access_token_expire_in: int
    xsrf_token: str


@register_node()
class RefreshTokenNode(ServiceNode[AuthService]):
    message: str = "Token refreshed successfully"
    access_token_expire_in: int
    xsrf_token: str


@register_node()
class LogoutNode(ServiceNode[AuthService]):
    succeed: bool
    message: str = "Successfully logged out"