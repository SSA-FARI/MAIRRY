class AiError(Exception):
    """Base exception for failures at an AI boundary."""


class AiOutputError(AiError, ValueError):
    """Raised when a model response cannot be validated against the contract."""


class AiProviderError(AiError):
    """Raised when an AI provider is unavailable or its request fails."""


class DemoFallbackError(AiError):
    """Raised when a registered demo fallback cannot be loaded safely."""
