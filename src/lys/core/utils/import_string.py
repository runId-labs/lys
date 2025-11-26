"""
Utility for importing classes from dotted string paths.
"""
import importlib


def import_string(dotted_path: str):
    """
    Import a class or function from a dotted path string.

    Args:
        dotted_path: Full path to the class (e.g., "lys.apps.licensing.registries.ValidatorRegistry")

    Returns:
        The imported class or function

    Raises:
        ImportError: If the module cannot be found
        AttributeError: If the attribute doesn't exist in the module

    Example:
        >>> cls = import_string("lys.apps.licensing.registries.ValidatorRegistry")
        >>> instance = cls()
    """
    try:
        module_path, class_name = dotted_path.rsplit(".", 1)
    except ValueError as e:
        raise ImportError(f"'{dotted_path}' is not a valid dotted path") from e

    module = importlib.import_module(module_path)

    try:
        return getattr(module, class_name)
    except AttributeError as e:
        raise ImportError(f"Module '{module_path}' has no attribute '{class_name}'") from e
