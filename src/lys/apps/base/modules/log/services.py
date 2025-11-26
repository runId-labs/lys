from lys.apps.base.modules.log.entities import Log
from lys.core.registries import register_service
from lys.core.services import EntityService


@register_service()
class LogService(EntityService[Log]):
    pass
