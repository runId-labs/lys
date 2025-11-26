from lys.apps.base.modules.access_level.services import AccessLevelService
from lys.core.graphql.nodes import parametric_node
from lys.core.registries import register_node


@register_node()
@parametric_node(AccessLevelService)
class AccessLevelNode:
    pass