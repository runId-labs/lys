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


def ensure_utc(value: datetime) -> datetime:
    """
    Assume UTC for a naive datetime, leave an aware one untouched.

    Some backends round-trip a DateTime column as naive regardless of what was
    stored (SQLite has no native timezone-aware type, unlike Postgres) - a value
    read back from one of those needs this before it can be compared against an
    aware datetime (e.g. now_utc()), which otherwise raises TypeError.

    Args:
        value: A datetime that may or may not carry timezone info

    Returns:
        datetime: The same instant, guaranteed to carry timezone info
    """
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
