from typing import List

import strawberry
from strawberry.types import Info

from lys.apps.user_auth.modules.user.nodes import UserNode as UserAuthUserNode
from lys.apps.user_role.modules.role.nodes import RoleNode
from lys.apps.user_role.modules.user.entities import User
from lys.core.registries import register_node


@register_node()
class UserNode(UserAuthUserNode):
    """
    Extended user node with role information.

    Adds the list of roles assigned to the user on top of the base UserNode from
    user_auth. It overrides the user_auth UserNode when the user_role app is enabled.
    """
    _entity: strawberry.Private[User]

    @strawberry.field(description="Roles assigned to this user")
    async def roles(self, info: Info) -> List[RoleNode]:
        """Get the list of roles assigned to this user."""
        return await self._lazy_load_relation_list('roles', RoleNode, info)
