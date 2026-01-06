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
    """Response validation failed (e.g., JSON schema mismatch)."""
    pass