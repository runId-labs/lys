"""
AI provider exceptions.

This module defines the exception hierarchy for AI operations,
allowing precise error handling and retry/fallback logic.
"""


class AIError(Exception):
    """Base exception for AI operations."""
    pass


class AIAuthError(AIError):
    """Authentication failed (invalid API key)."""
    pass


class AIRateLimitError(AIError):
    """Rate limit exceeded (429). May trigger fallback."""
    pass


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
    """Response was cut off by the output token limit before it could be validated.

    Unlike a plain schema mismatch, this is deterministic: the same request on the
    same endpoint truncates again. Callers must fall back instead of retrying.
    """
    pass