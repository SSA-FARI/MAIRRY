from pathlib import Path

from pydantic import ValidationError

from ai.common.exceptions import AiOutputError, AiProviderError
from ai.document_extraction.fallback import (
    DEFAULT_DEMO_FALLBACK_REGISTRY,
    DemoFallbackRegistry,
)
from ai.document_extraction.schemas import DocumentAnalysisResult, DocumentExtraction
from ai.providers.base import AiProvider


async def analyze_document(
    file_path: Path,
    provider: AiProvider | None = None,
    *,
    enable_demo_fallback: bool = True,
    fallback_registry: DemoFallbackRegistry = DEFAULT_DEMO_FALLBACK_REGISTRY,
) -> DocumentAnalysisResult:
    provider_error: AiProviderError | AiOutputError

    if provider is None:
        provider_error = AiProviderError("AI provider is not configured")
    else:
        try:
            payload = await provider.extract_document(file_path)
        except (AiProviderError, TimeoutError):
            provider_error = AiProviderError("AI provider request failed")
        else:
            try:
                extraction = DocumentExtraction.model_validate(payload)
            except ValidationError:
                provider_error = AiOutputError("AI provider returned an invalid extraction")
            else:
                return DocumentAnalysisResult(
                    extraction=extraction,
                    analysis_source="LIVE_AI",
                )

    if enable_demo_fallback:
        fallback = fallback_registry.find(file_path)
        if fallback is not None:
            return DocumentAnalysisResult(
                extraction=fallback,
                analysis_source="DEMO_FALLBACK",
            )

    raise provider_error
