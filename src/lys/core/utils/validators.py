import re

from lys.apps.user_auth.errors import EMPTY_PASSWORD_ERROR, WEAK_PASSWORD, INVALID_NAME, INVALID_LANGUAGE
from lys.core.errors import LysError


# Regex patterns
NAME_PATTERN = r"^[a-zA-ZÀ-ÿ\s\-']+$"
LANGUAGE_PATTERN = r"^[a-z]{2}(-[a-z]{2})?$"

# Password constraints
PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128


def validate_name(value: str | None, field_name: str) -> str | None:
    """
    Validate name fields (first_name, last_name, etc.).

    Args:
        value: The name value to validate
        field_name: Name of the field for error messages

    Returns:
        Validated and stripped name, or None if input is None

    Raises:
        LysError: If name contains invalid characters
    """
    if value is None:
        return value

    value = value.strip()
    if not value:
        return None

    # Check for invalid characters (allow letters, spaces, hyphens, apostrophes)
    if not re.match(NAME_PATTERN, value):
        raise LysError(
            INVALID_NAME,
            f"{field_name} contains invalid characters"
        )

    return value


def validate_language_format(value: str | None) -> str | None:
    """
    Validate language ID format (e.g., 'en' or 'en-US').

    Note: This only validates format. Existence in database should be validated separately.

    Args:
        value: The language ID to validate

    Returns:
        Validated and normalized language ID

    Raises:
        LysError: If language_id format is invalid
    """
    if not value:
        raise LysError(
            INVALID_LANGUAGE,
            "language_id is required"
        )

    value = value.strip().lower()

    # Check format (2-letter or 5-letter codes like 'en' or 'en-US')
    if not re.match(LANGUAGE_PATTERN, value):
        raise LysError(
            INVALID_LANGUAGE,
            "language_id must be in format 'en' or 'en-US'"
        )

    return value


def validate_password_for_creation(password: str | None) -> str:
    """
    Validate password for user creation (strict validation).

    Requirements:
    - At least 8 characters
    - At least one letter
    - At least one digit

    Args:
        password: The password to validate

    Returns:
        Validated password

    Raises:
        LysError: If password is empty or doesn't meet requirements
    """
    if not password or not len(password.strip()):
        raise LysError(
            EMPTY_PASSWORD_ERROR,
            "password cannot be empty"
        )

    password = password.strip()

    # Check minimum length
    if len(password) < PASSWORD_MIN_LENGTH:
        raise LysError(
            WEAK_PASSWORD,
            f"password must be at least {PASSWORD_MIN_LENGTH} characters long"
        )

    # Check for at least one letter
    if not re.search(r"[a-zA-Z]", password):
        raise LysError(
            WEAK_PASSWORD,
            "password must contain at least one letter"
        )

    # Check for at least one digit
    if not re.search(r"\d", password):
        raise LysError(
            WEAK_PASSWORD,
            "password must contain at least one digit"
        )

    return password


def validate_password_for_login(password: str | None) -> str:
    """
    Validate password for login (basic validation).

    Only checks that password is not empty.

    Args:
        password: The password to validate

    Returns:
        Validated and stripped password

    Raises:
        LysError: If password is empty
    """
    if not password or not len(password.strip()):
        raise LysError(
            EMPTY_PASSWORD_ERROR,
            "password cannot be empty"
        )

    return password.strip()