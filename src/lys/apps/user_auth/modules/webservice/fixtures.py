from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.util import classproperty

from lys.apps.base.modules.access_level.entities import AccessLevel
from lys.apps.base.modules.access_level.services import AccessLevelService
from lys.apps.user_auth.modules.webservice.entities import WebservicePublicType
from lys.apps.user_auth.modules.webservice.services import WebservicePublicTypeService, AuthWebserviceService
from lys.core.consts.webservices import NO_LIMITATION_WEBSERVICE_PUBLIC_TYPE, DISCONNECTED_WEBSERVICE_PUBLIC_TYPE
from lys.core.fixtures import EntityFixtures
from lys.core.models.fixtures import ParametricEntityFixturesModel
from lys.core.models.webservices import WebserviceFixturesModel
from lys.core.registers import register_fixture


@register_fixture()
class WebservicePublicTypeFixtures(EntityFixtures[WebservicePublicTypeService]):
    model = ParametricEntityFixturesModel
    data_list = [
        {
            "id": NO_LIMITATION_WEBSERVICE_PUBLIC_TYPE,
            "attributes": {
                "enabled": True
            }
        },
        {
            "id": DISCONNECTED_WEBSERVICE_PUBLIC_TYPE,
            "attributes": {
                "enabled": True
            }
        },
    ]

@register_fixture(depends_on=["WebservicePublicTypeFixtures"])
class WebserviceFixtures(EntityFixtures[AuthWebserviceService]):
    model = WebserviceFixturesModel

    @classproperty
    def data_list(self):
        return self.app_manager.register.webservices.values()

    @classmethod
    async def format_public_type(cls, public_type_id: str | None, session:AsyncSession) -> WebservicePublicType | None:
        webservice_public_type_service: type[WebservicePublicTypeService] = \
            cls.app_manager.get_service("webservice_public_type")

        public_type: WebservicePublicType | None = None

        if public_type_id is not None:
            public_type = await webservice_public_type_service.get_by_id(public_type_id, session)

        return public_type

    @classmethod
    async def format_access_levels(cls, access_levels: list[str], session:AsyncSession) -> list[AccessLevel]:
        access_level_service: type[AccessLevelService] = \
            cls.app_manager.get_service("access_level")

        access_level_objs: list[AccessLevel] = []

        for access_level_id in access_levels:
            access_level_obj = await access_level_service.get_by_id(access_level_id, session)
            if access_level_obj is not None:
                access_level_objs.append(access_level_obj)
        return access_level_objs