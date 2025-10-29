"""
Utility module for extracting type information from generic classes.

This module provides utilities to automatically resolve service names and related
metadata from generic type parameters, eliminating code duplication across
EntityService, EntityFixtures, and EntityNode classes.
"""
from typing import Optional


def resolve_service_name_from_generic(cls) -> Optional[str]:
    """
    Extract service_name from the generic type parameter.

    This function inspects the class's __orig_bases__ to find generic parameters
    and extracts the service name from the first type argument.

    Resolution logic:
    1. If parameter has __tablename__ attribute (Entity class) -> use it
    2. If parameter has service_name attribute (Service class) -> use it
    3. Otherwise -> return None

    Args:
        cls: The class to extract service_name from

    Returns:
        The resolved service name, or None if it cannot be determined

    Example:
        # In EntityService subclass
        class UserService(EntityService[User]):
            def __init_subclass__(cls, **kwargs):
                super().__init_subclass__(**kwargs)
                service_name = resolve_service_name_from_generic(cls)
                if service_name:
                    cls.service_name = service_name
    """
    for base in cls.__orig_bases__:
        if hasattr(base, '__args__') and base.__args__:
            param_class = base.__args__[0]

            # Try to get service_name from entity's __tablename__
            if hasattr(param_class, '__tablename__'):
                return param_class.__tablename__

            # Try to get service_name from service class
            if hasattr(param_class, 'service_name'):
                return param_class.service_name

    return None