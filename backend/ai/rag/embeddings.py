from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from typing import Any, Protocol, Self

import httpx

DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_EMBEDDING_VERSION = "v1"
DEFAULT_EMBEDDING_DIMENSIONS = 1536
DEFAULT_MAX_CONNECTIONS = 20
DEFAULT_MAX_KEEPALIVE_CONNECTIONS = 10


class EmbeddingError(RuntimeError):
    """Raised when embeddings cannot be generated or validated."""


class EmbeddingClient(Protocol):
    model_name: str
    version: str
    dimensions: int

    def embed(self, text: str) -> list[float]: ...

    def embed_many(self, texts: Iterable[str]) -> list[list[float]]: ...


class OpenAiEmbeddingClient:
    """Synchronous adapter for OpenAI-compatible Embeddings APIs, including SSAFY GMS."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model_name: str = DEFAULT_EMBEDDING_MODEL,
        version: str = DEFAULT_EMBEDDING_VERSION,
        dimensions: int = DEFAULT_EMBEDDING_DIMENSIONS,
        timeout_seconds: float = 45,
        batch_size: int = 64,
        http_client: httpx.Client | None = None,
    ) -> None:
        normalized_base_url = base_url.strip().rstrip("/")
        parsed_base_url = httpx.URL(normalized_base_url)
        if parsed_base_url.scheme not in {"http", "https"} or not parsed_base_url.host:
            raise ValueError("Embedding base URL must be an absolute HTTP(S) URL")
        if not model_name.strip():
            raise ValueError("Embedding model name must not be blank")
        if not version.strip():
            raise ValueError("Embedding version must not be blank")
        if dimensions <= 0 or timeout_seconds <= 0 or batch_size <= 0:
            raise ValueError("Embedding dimensions, timeout, and batch size must be positive")

        self._api_key = api_key.strip()
        self._embeddings_url = (
            normalized_base_url
            if normalized_base_url.endswith("/embeddings")
            else f"{normalized_base_url}/embeddings"
        )
        self._timeout_seconds = timeout_seconds
        self._batch_size = batch_size
        self._owns_http_client = http_client is None
        self._http_client = http_client or httpx.Client(
            timeout=timeout_seconds,
            limits=httpx.Limits(
                max_connections=DEFAULT_MAX_CONNECTIONS,
                max_keepalive_connections=DEFAULT_MAX_KEEPALIVE_CONNECTIONS,
            ),
        )
        self.model_name = model_name.strip()
        self.version = version.strip()
        self.dimensions = dimensions

    def embed(self, text: str) -> list[float]:
        return self.embed_many([text])[0]

    def close(self) -> None:
        if self._owns_http_client and not self._http_client.is_closed:
            self._http_client.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def embed_many(self, texts: Iterable[str]) -> list[list[float]]:
        normalized = [text.strip() for text in texts]
        if not normalized:
            return []
        if any(not text for text in normalized):
            raise ValueError("Embedding input must not be blank")
        if not self._api_key:
            raise EmbeddingError("AI_API_KEY is required for embeddings")

        vectors: list[list[float]] = []
        for start in range(0, len(normalized), self._batch_size):
            vectors.extend(self._request(normalized[start : start + self._batch_size]))
        return vectors

    def _request(self, inputs: list[str]) -> list[list[float]]:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        try:
            response = self._http_client.post(
                self._embeddings_url,
                headers=headers,
                json={"model": self.model_name, "input": inputs},
                timeout=self._timeout_seconds,
            )
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise EmbeddingError("Embedding provider request timed out") from exc
        except httpx.HTTPStatusError as exc:
            raise EmbeddingError(
                f"Embedding provider rejected the request ({exc.response.status_code})"
            ) from exc
        except httpx.RequestError as exc:
            raise EmbeddingError("Embedding provider is unavailable") from exc

        try:
            payload: Any = response.json()
            response_model = payload["model"]
            data = sorted(payload["data"], key=lambda item: item["index"])
            vectors = [item["embedding"] for item in data]
        except (KeyError, TypeError, ValueError) as exc:
            raise EmbeddingError("Embedding provider returned an invalid response") from exc
        if response_model != self.model_name:
            raise EmbeddingError("Embedding provider returned a different model")
        if len(vectors) != len(inputs):
            raise EmbeddingError("Embedding provider returned an unexpected vector count")
        if any(not _valid_vector(vector, self.dimensions) for vector in vectors):
            raise EmbeddingError("Embedding provider returned an incompatible vector dimension")
        return [[float(value) for value in vector] for vector in vectors]


def _valid_vector(vector: object, dimensions: int) -> bool:
    return (
        isinstance(vector, list)
        and len(vector) == dimensions
        and all(isinstance(value, int | float) and math.isfinite(value) for value in vector)
    )


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right) or not left:
        return 0.0
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if not left_norm or not right_norm:
        return 0.0
    score = sum(a * b for a, b in zip(left, right, strict=True)) / (left_norm * right_norm)
    return max(0.0, min(1.0, score))
