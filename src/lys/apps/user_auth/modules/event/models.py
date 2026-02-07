"""
Pydantic models for event preferences input validation.
"""
from pydantic import BaseModel, field_validator


class SetEventPreferenceInputModel(BaseModel):
    """Input model for setting user event preferences."""

    event_type: str
    channel: str
    enabled: bool

    @field_validator("channel")
    @classmethod
    def validate_channel(cls, v: str) -> str:
        """Validate channel is either 'email' or 'notification'."""
        if v not in ("email", "notification"):
            raise ValueError("Channel must be 'email' or 'notification'")
        return v