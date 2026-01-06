"""
String utility functions.
"""


def to_camel_case(snake_str: str) -> str:
    """
    Convert snake_case to camelCase.

    Args:
        snake_str: String in snake_case format

    Returns:
        String in camelCase format

    Example:
        >>> to_camel_case("user_name")
        "userName"
        >>> to_camel_case("get_user_by_id")
        "getUserById"
    """
    components = snake_str.split("_")
    return components[0] + "".join(x.title() for x in components[1:])


def to_snake_case(camel_str: str) -> str:
    """
    Convert camelCase to snake_case.

    Args:
        camel_str: String in camelCase format

    Returns:
        String in snake_case format

    Example:
        >>> to_snake_case("userName")
        "user_name"
        >>> to_snake_case("getUserById")
        "get_user_by_id"
    """
    result = []
    for i, char in enumerate(camel_str):
        if char.isupper() and i > 0:
            result.append("_")
        result.append(char.lower())
    return "".join(result)