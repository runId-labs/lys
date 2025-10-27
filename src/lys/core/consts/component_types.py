from enum import Enum


class AppComponentTypeEnum(str, Enum):
    ENTITIES = "entities"
    SERVICES = "services"
    FIXTURES = "fixtures"
    NODES = "nodes"
    WEBSERVICES = "webservices"
