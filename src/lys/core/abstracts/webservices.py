from abc import abstractmethod

from lys.core.consts.tablenames import WEBSERVICE_TABLENAME
from lys.core.entities import ParametricEntity


class AbstractWebservice(ParametricEntity):
    __tablename__ = WEBSERVICE_TABLENAME

    @property
    @abstractmethod
    def is_public(self):
        raise NotImplementedError

    @property
    @abstractmethod
    def access_levels(self):
        raise NotImplementedError
