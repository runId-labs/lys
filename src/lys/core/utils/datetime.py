from datetime import datetime, timezone


def now_utc() -> datetime:
    """
    Get current UTC datetime with timezone info.

    Use this function instead of datetime.now() to ensure consistent
    timezone-aware datetime objects across the application.

    Returns:
        datetime: Current UTC time with timezone information

    Example:
        >>> from lys.core.utils.datetime import now_utc
        >>> current_time = now_utc()
        >>> expires_at = now_utc() + timedelta(hours=1)
    """
    return datetime.now(timezone.utc)
