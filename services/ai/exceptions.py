"""
services/ai/exceptions.py — Custom exception hierarchy for the AI layer.

All AI-layer errors derive from AIError so callers can catch broadly
or narrowly as needed.
"""


class AIError(Exception):
    """Base class for all AI-layer errors."""


class ProviderError(AIError):
    """
    Raised when all configured providers fail after failover.

    Attributes
    ----------
    provider:  Which provider was last attempted.
    cause:     The underlying exception from the provider.
    """

    def __init__(self, message: str, provider: str = "unknown", cause: Exception | None = None) -> None:
        super().__init__(message)
        self.provider = provider
        self.cause = cause


class PromptError(AIError):
    """Raised when a prompt template cannot be loaded or rendered."""


class ValidationError(AIError):
    """
    Raised when the AI response cannot be parsed / validated against
    the expected Pydantic schema.
    """

    def __init__(self, message: str, raw: str = "") -> None:
        super().__init__(message)
        self.raw = raw


class AIResponseError(AIError):
    """
    Raised when the provider returns an unexpected response structure
    (e.g. empty content, missing fields).
    """
