"""
Custom registries for the licensing app.

This module defines:
- ValidatorRegistry: Registry for rule validation functions
- DowngraderRegistry: Registry for rule downgrade functions
- Decorator factories for registering validators and downgraders
"""
from typing import Callable, Awaitable

from sqlalchemy.ext.asyncio import AsyncSession

from lys.core.registries import CustomRegistry, LysAppRegistry


# Type aliases for validator and downgrader functions
ValidatorFunc = Callable[
    [AsyncSession, str, int | None],
    Awaitable[tuple[bool, int, int]]
]
DowngraderFunc = Callable[
    [AsyncSession, str, int],
    Awaitable[bool]
]


class ValidatorRegistry(CustomRegistry):
    """
    Registry for license rule validators.

    Validators are functions that check if a rule constraint is satisfied.
    File loaded: validators.py in each module.

    Validator signature:
        async def validate_xxx(
            session: AsyncSession,
            client_id: str,
            limit_value: int | None
        ) -> tuple[bool, int, int]:
            # Returns: (is_valid, current_count, limit)
    """
    name = "validators"


class DowngraderRegistry(CustomRegistry):
    """
    Registry for license rule downgraders.

    Downgraders are functions that adjust data when a client downgrades
    to a plan with lower limits.
    File loaded: downgraders.py in each module.

    Downgrader signature:
        async def downgrade_xxx(
            session: AsyncSession,
            client_id: str,
            new_limit: int
        ) -> bool:
            # Returns: True if downgrade was successful
    """
    name = "downgraders"


def register_validator(rule_id: str):
    """
    Decorator to register a validator function for a license rule.

    Usage:
        @register_validator("MAX_USERS")
        async def validate_max_users(session, client_id, limit_value):
            ...

    Args:
        rule_id: The rule identifier (e.g., "MAX_USERS")
    """
    def decorator(func: ValidatorFunc) -> ValidatorFunc:
        app_registry = LysAppRegistry()
        registry = app_registry.get_registry("validators")
        if registry:
            registry.register(rule_id, func)
        return func
    return decorator


def register_downgrader(rule_id: str):
    """
    Decorator to register a downgrader function for a license rule.

    Usage:
        @register_downgrader("MAX_USERS")
        async def downgrade_max_users(session, client_id, new_limit):
            ...

    Args:
        rule_id: The rule identifier (e.g., "MAX_USERS")
    """
    def decorator(func: DowngraderFunc) -> DowngraderFunc:
        app_registry = LysAppRegistry()
        registry = app_registry.get_registry("downgraders")
        if registry:
            registry.register(rule_id, func)
        return func
    return decorator
