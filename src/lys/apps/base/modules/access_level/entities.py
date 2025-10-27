from lys.core.consts.tablenames import ACCESS_LEVEL_TABLENAME
from lys.core.entities import ParametricEntity
from lys.core.registers import register_entity


@register_entity()
class AccessLevel(ParametricEntity):
    __tablename__ = ACCESS_LEVEL_TABLENAME