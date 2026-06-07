from abc import ABC, abstractmethod

import httpx
from pydantic import BaseModel, Field

from app.core.observability import span


class ImageEmbedding(BaseModel):
    model_id: str
    dimensions: int
    embedding: list[float] = Field(min_length=1)


class EmbeddingClient(ABC):
    @abstractmethod
    def embed_image(
        self, *, image_object_key: str, image_url: str | None, model_id: str, dimensions: int
    ) -> ImageEmbedding:
        raise NotImplementedError


class HttpEmbeddingClient(EmbeddingClient):
    def __init__(self, base_url: str, timeout_seconds: float = 60.0):
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def embed_image(
        self, *, image_object_key: str, image_url: str | None, model_id: str, dimensions: int
    ) -> ImageEmbedding:
        request_body = {
            "image_object_key": image_object_key,
            "image_url": image_url,
            "model_id": model_id,
            "dimensions": dimensions,
        }
        with span(
            "model_services.siglip.embed_image",
            provider="modal",
            endpoint="/embed-image",
            model_id=model_id,
            dimensions=dimensions,
            image_object_key=image_object_key,
            has_signed_image_url=image_url is not None,
        ) as active_span:
            response = httpx.post(
                f"{self.base_url}/embed-image",
                json=request_body,
                timeout=self.timeout_seconds,
            )
            active_span.set_attributes(_response_metadata(response))
            response.raise_for_status()
            embedding = ImageEmbedding.model_validate(response.json())
            active_span.set_attributes(
                {
                    "response_model_id": embedding.model_id,
                    "response_dimensions": embedding.dimensions,
                    "embedding_length": len(embedding.embedding),
                    "embedding_min": min(embedding.embedding),
                    "embedding_max": max(embedding.embedding),
                }
            )
            if embedding.model_id != model_id:
                raise ValueError(
                    f"Embedding service returned model_id={embedding.model_id!r}, "
                    f"expected {model_id!r}"
                )
            if embedding.dimensions != dimensions:
                raise ValueError(
                    "Embedding service returned "
                    f"dimensions={embedding.dimensions}, expected {dimensions}"
                )
            if len(embedding.embedding) != dimensions:
                raise ValueError(
                    f"Embedding length {len(embedding.embedding)} "
                    f"does not match dimensions {dimensions}"
                )
            return embedding


class MissingEmbeddingClient(EmbeddingClient):
    def embed_image(
        self, *, image_object_key: str, image_url: str | None, model_id: str, dimensions: int
    ) -> ImageEmbedding:
        raise RuntimeError("EMBEDDING_SERVICE_URL is required to enrich catalog vectors")


def _response_metadata(response: httpx.Response) -> dict[str, int]:
    metadata = {}
    status_code = getattr(response, "status_code", None)
    if status_code is not None:
        metadata["http_status_code"] = status_code
    content = getattr(response, "content", None)
    if content is not None:
        metadata["response_content_length"] = len(content)
    return metadata
