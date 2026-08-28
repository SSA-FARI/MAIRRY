class AiError(Exception):
    """Base exception for failures at an AI boundary."""


class AiOutputError(AiError, ValueError):
    """Raised when a model response cannot be validated against the contract."""


class AiProviderError(AiError):
    """Raised when an AI provider is unavailable or its request fails."""


class AiProviderAuthenticationError(AiProviderError):
    """Raised when an AI provider rejects configured credentials."""


class AiProviderRateLimitError(AiProviderError):
    """Raised when an AI provider rate limit is reached."""


class AiProviderTimeoutError(AiProviderError, TimeoutError):
    """Raised when an AI provider request exceeds its timeout."""


class AiProviderUnavailableError(AiProviderError):
    """Raised when an AI provider cannot be reached or is unavailable."""


class AiProviderResponseError(AiProviderError):
    """Raised when an AI provider returns an unusable response envelope."""


class AiProviderInputError(AiProviderError, ValueError):
    """Raised when a document cannot be sent safely to an AI provider."""


class DemoFallbackError(AiError):
    """Raised when a registered demo fallback cannot be loaded safely."""
