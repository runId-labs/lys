"""
Utility module for extracting type information from generic classes.

This module provides utilities to automatically resolve service names and related
metadata from generic type parameters, eliminating code duplication across
EntityService, EntityFixtures, and EntityNode classes.
"""
from typing import Optional, get_origin, get_args, Dict, Any


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


def replace_node_in_annotation(annotation: Any, nodes_registry: Dict[str, Any]) -> Any:
    """
    Replace node references in type annotations with their effective registered versions.

    This function handles node overriding in GraphQL schemas by replacing node type
    references in annotations with the latest registered version from the node registry.
    This ensures that when a node is overridden (e.g., UserNode extended with roles),
    all references to that node in other nodes' annotations point to the effective version.

    Handles:
    - Direct node references: UserNode -> registry["UserNode"]
    - String forward references: "UserNode" -> registry["UserNode"]
    - Optional types: Optional[UserNode] -> Optional[registry["UserNode"]]
    - List types: List[UserNode] -> List[registry["UserNode"]]
    - Other generic types: Union, etc.

    Args:
        annotation: The type annotation to process
        nodes_registry: Dictionary mapping node names to node classes

    Returns:
        The annotation with node references replaced, or the original annotation if no replacement needed

    Example:
        # Before finalization
        class LoginNode:
            user: UserNode  # Points to base UserNode from user_auth

        # After finalization with node registry containing extended UserNode
        class LoginNode:
            user: UserNode  # Now points to extended UserNode from user_role
    """
    # Case 1: String forward reference
    if isinstance(annotation, str):
        if annotation in nodes_registry:
            return nodes_registry[annotation]
        return annotation

    # Case 2: Simple type with __name__ (direct node class reference)
    if hasattr(annotation, '__name__') and annotation.__name__ in nodes_registry:
        return nodes_registry[annotation.__name__]

    # Case 3: Generic type (Optional, List, Union, etc.)
    origin = get_origin(annotation)
    if origin is not None:
        args = get_args(annotation)
        if args:
            # Recursively replace node references in type arguments
            new_args = tuple(
                replace_node_in_annotation(arg, nodes_registry)
                for arg in args
            )
            # Reconstruct the generic type with updated arguments
            try:
                return origin[new_args]
            except (TypeError, AttributeError):
                # Some types don't support subscripting after creation
                # Return original annotation in these cases
                return annotation

    # No replacement needed
    return annotation