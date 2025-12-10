from abc import abstractmethod
from typing import Tuple, List, Dict, Union, Any

from sqlalchemy import Select, BinaryExpression


class EntityInterface:

    @classmethod
    @abstractmethod
    def get_tablename(cls):
        raise NotImplementedError

    @abstractmethod
    def accessing_users(self) -> List[str]:
        """Returns a list of user IDs who can access this entity."""
        raise NotImplementedError

    @abstractmethod
    def accessing_organizations(self) -> Dict[str, List[str]]:
        """Returns a dictionary of organization table names to lists of organization IDs who can access this entity."""
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def user_accessing_filters(cls, stmt: Select, user_id: str) \
            -> Tuple[Select, List[BinaryExpression]]:
        """
        filters which define list of users who can access to the entity in a query
        :param stmt:
        :param user_id: user id who wants access to the entity
        :return:
        """
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def organization_accessing_filters(cls, stmt: Select, accessing_organization_id_dict: Dict) \
            -> Tuple[Select, List[BinaryExpression]]:
        """
        filters which define list of organization which can access to the entity in a query
        :param stmt:
        :param accessing_organization_id_dict: dictionary of organization ids which want access to the entity
        :return:
        """
        raise NotImplementedError

    @abstractmethod
    def check_permission(self, user_id: str | None, access_type: Union[dict[str, Any], bool]):
        """
        Check user permission on the entity
        :param user_id: id of the user who requires access.
        :param access_type: access type dictionary
        :return:
        """
        raise NotImplementedError