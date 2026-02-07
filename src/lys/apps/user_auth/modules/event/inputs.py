"""
Strawberry GraphQL input types for event preferences.
"""
import strawberry

from lys.apps.user_auth.modules.event.models import SetEventPreferenceInputModel


@strawberry.experimental.pydantic.input(model=SetEventPreferenceInputModel)
class SetEventPreferenceInput:
    """GraphQL input for setting an event preference."""

    event_type: strawberry.auto = strawberry.field(
        description="Event type key (e.g., 'FINANCIAL_IMPORT_COMPLETED')"
    )
    channel: strawberry.auto = strawberry.field(
        description="Channel type: 'email' or 'notification'"
    )
    enabled: strawberry.auto = strawberry.field(
        description="Whether to enable this notification channel"
    )