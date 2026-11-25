"""
AI provider exceptions.

This module defines the exception hierarchy for AI operations,
allowing precise error handling and retry/fallback logic.
"""
from typing import Optional


class AIError(Exception):
    """Base exception for AI operations."""
    pass


class AIAuthError(AIError):
    """Authentication failed (invalid API key)."""
    pass


class AIRateLimitError(AIError):
    """
    Rate limit exceeded (429). May trigger a retry, then a fallback.

    ``retry_after``: the seconds the provider asked to wait (its Retry-After
    header), None when it said nothing.
    """

    def __init__(self, message: str = "", retry_after: Optional[float] = None):
        super().__init__(message)
        self.retry_after = retry_after


class AIModelNotFoundError(AIError):
    """Requested model does not exist."""
    pass


class AIProviderError(AIError):
    """Provider-side error (5xx). May trigger retry."""
    pass


class AITimeoutError(AIError):
    """Request timed out."""
    pass


class AIPurposeNotFoundError(AIError):
    """Requested purpose not configured."""
    pass


class AIValidationError(AIError):
    """Response validation failed (e.g., JSON schema mismatch). May trigger retry."""
    pass


class AIResponseTruncatedError(AIValidationError):
    """Response was cut off: by the output token limit before it could be validated, or
    by a schema ``maxLength`` that stopped a text field mid-word.

    Unlike a plain schema mismatch, the same request on the same endpoint truncates again.
    Callers must fall back instead of retrying.
    """
    pass


def retry_after_seconds(value: Optional[str]) -> Optional[float]:
    """
    The seconds a Retry-After header asks to wait; None when absent or not a number
    of seconds (its HTTP-date form is not read: the caller's own backoff applies).
    """
    if not value:
        return None
    try:
        seconds = float(value)
    except ValueError:
        return None
    return seconds if seconds >= 0 else None
