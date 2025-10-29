from lys.apps.user_role.modules.role.services import RoleService
from lys.core.graphql.nodes import parametric_node
from lys.core.registers import register_node


@register_node()
@parametric_node(RoleService)
class RoleNode:
    pass