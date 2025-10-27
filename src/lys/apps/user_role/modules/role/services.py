from lys.apps.user_role.modules.role.entities import Role
from lys.core.registers import register_service
from lys.core.services import EntityService


@register_service()
class RoleService(EntityService[Role]):
    pass