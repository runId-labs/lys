import strawberry

from lys.apps.user_auth.modules.auth.services import AuthService
from lys.apps.user_auth.modules.user.nodes import UserNode
from lys.core.graphql.nodes import ServiceNode
from lys.core.registers import register_node


@strawberry.type
@register_node()
class LoginNode(ServiceNode[AuthService]):
    access_token_expire_in: int
    xsrf_token: str
    user: UserNode


@strawberry.type
@register_node()
class RefreshTokenNode(ServiceNode[AuthService]):
    # test
    access_token_expire_in: int
    xsrf_token: str


@strawberry.type
@register_node()
class LogoutNode(ServiceNode[AuthService]):
    succeed: bool