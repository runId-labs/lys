"""
Pydantic models for validating plugin configurations.
"""
from pydantic import BaseModel


class PubSubConfig(BaseModel):
    """
    Pydantic model for validating pubsub plugin configuration.

    Usage in settings:
        settings.configure_plugin("pubsub",
            redis_url="redis://localhost:6379/0",
            channel_prefix="myapp"
        )

    Attributes:
        redis_url: Redis connection URL (required)
        channel_prefix: Prefix for all channel names (default: "signal")
    """
    redis_url: str
    channel_prefix: str = "signal"