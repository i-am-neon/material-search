from abc import ABC, abstractmethod

import httpx
from pydantic import BaseModel, Field


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
        response = httpx.post(
            f"{self.base_url}/embed-image",
            json={
                "image_object_key": image_object_key,
                "image_url": image_url,
                "model_id": model_id,
                "dimensions": dimensions,
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        embedding = ImageEmbedding.model_validate(response.json())
        if embedding.model_id != model_id:
            raise ValueError(
                f"Embedding service returned model_id={embedding.model_id!r}, expected {model_id!r}"
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
