"""
Rule validators for license quota enforcement.

Validators are registered using @register_validator("RULE_ID") and are called
by LicenseCheckerService to check if a quota rule is satisfied.

Validator signature:
    async def validate_xxx(
        session: AsyncSession,
        client_id: str,
        app_id: str,
        limit_value: int | None
    ) -> tuple[bool, int, int]:
        # Returns: (is_valid, current_count, limit)

Return values:
    - is_valid: True if current usage is within the limit
    - current_count: Current usage count
    - limit: The limit value (-1 means unlimited)

Note:
    The app_id parameter supports multi-app subscriptions where a client
    can have separate subscriptions for different applications.
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from lys.apps.licensing.consts import MAX_USERS, MAX_PROJECTS_PER_MONTH
from lys.apps.licensing.modules.subscription.entities import subscription_user
from lys.apps.licensing.registries import register_validator
from lys.core.managers.app import LysAppManager


@register_validator(MAX_USERS)
async def validate_max_users(
    session: AsyncSession,
    client_id: str,
    app_id: str,
    limit_value: int | None
) -> tuple[bool, int, int]:
    """
    Validate the maximum number of licensed users (seats) for a subscription.

    Counts subscription_user entries for the client's subscription.
    This represents how many users are consuming license seats.

    Args:
        session: Database session
        client_id: Client ID
        app_id: Application ID (for multi-app support)
        limit_value: Maximum allowed licensed users (None = unlimited)

    Returns:
        Tuple of (is_valid, current_count, limit)
    """
    app_manager = LysAppManager()
    subscription_service = app_manager.get_service("subscription")

    # Get client's subscription
    client_subscription = await subscription_service.get_client_subscription(
        client_id, session
    )

    if not client_subscription:
        # No subscription = no users allowed (except for validation before first add)
        if limit_value is None:
            return (True, 0, -1)
        return (True, 0, limit_value)

    # Count subscription_user entries for this subscription
    stmt = select(func.count()).select_from(subscription_user).where(
        subscription_user.c.subscription_id == client_subscription.id
    )
    result = await session.execute(stmt)
    current_count = result.scalar() or 0

    # None = unlimited
    if limit_value is None:
        return (True, current_count, -1)

    is_valid = current_count < limit_value
    return (is_valid, current_count, limit_value)


@register_validator(MAX_PROJECTS_PER_MONTH)
async def validate_max_projects_per_month(
    session: AsyncSession,
    client_id: str,
    app_id: str,
    limit_value: int | None
) -> tuple[bool, int, int]:
    """
    Validate the maximum number of projects per month for a client.

    This is a placeholder validator. The actual implementation depends on
    the application's project entity, which is not part of lys core.

    Applications should override this validator with their own implementation
    by registering a new validator with the same rule_id.

    Args:
        session: Database session
        client_id: Client ID
        app_id: Application ID (for multi-app support)
        limit_value: Maximum allowed projects per month (None = unlimited)

    Returns:
        Tuple of (is_valid, current_count, limit)
        Default: Always returns valid since project counting is app-specific
    """
    # Placeholder: return valid with 0 count
    # Applications should implement their own validator
    _ = (session, client_id, app_id)  # Unused in placeholder
    if limit_value is None:
        return True, 0, -1

    return True, 0, limit_value