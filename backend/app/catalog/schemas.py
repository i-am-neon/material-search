from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from app.core.config import DEFAULT_EMBEDDING_DIMENSIONS, DEFAULT_EMBEDDING_MODEL_ID


class CatalogItemCreate(BaseModel):
    manufacturer: str = Field(min_length=1, max_length=200)
    name: str = Field(min_length=1, max_length=300)
    material_family: str | None = Field(default=None, max_length=120)
    image_object_key: str = Field(min_length=1, max_length=1024)
    image_url: HttpUrl | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class CatalogItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    manufacturer: str
    name: str
    material_family: str | None
    image_object_key: str
    image_url: HttpUrl | None
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class CatalogItemList(BaseModel):
    items: list[CatalogItem]


class CatalogEmbeddingRequest(BaseModel):
    catalog_item_ids: list[UUID] | None = None
    model_id: str = DEFAULT_EMBEDDING_MODEL_ID
    dimensions: int = DEFAULT_EMBEDDING_DIMENSIONS


class CatalogEmbeddingJob(BaseModel):
    catalog_item_id: UUID
    model_id: str = DEFAULT_EMBEDDING_MODEL_ID
    dimensions: int = DEFAULT_EMBEDDING_DIMENSIONS
    requested_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class CatalogEmbeddingRecord(BaseModel):
    catalog_item_id: UUID
    model_id: str
    dimensions: int
    created_at: datetime


class CatalogVectorSearchRequest(BaseModel):
    embedding: list[float] = Field(min_length=1)
    model_id: str = DEFAULT_EMBEDDING_MODEL_ID
    limit: int = Field(default=12, ge=1, le=100)
    min_similarity: float = Field(default=0.0, ge=-1.0, le=1.0)


class CatalogMatch(BaseModel):
    item: CatalogItem
    model_id: str
    similarity: float


class CatalogVectorSearchResponse(BaseModel):
    matches: list[CatalogMatch]


class CatalogIndexAccepted(BaseModel):
    enqueued: int
    model_id: str
    dimensions: int

