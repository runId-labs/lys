from lys.apps.base.modules.access_level.entities import AccessLevel
from lys.core.registries import register_service
from lys.core.services import EntityService


@register_service()
class AccessLevelService(EntityService[AccessLevel]):
    pass
