from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl, model_validator

from app.catalog.schemas import CatalogMatch
from app.core.config import DEFAULT_EMBEDDING_DIMENSIONS, DEFAULT_EMBEDDING_MODEL_ID
from app.model_services.segmentation import SegmentationRegion


class RegionMatchRequest(BaseModel):
    region_id: str = Field(min_length=1)
    crop_object_key: str = Field(min_length=1, max_length=1024)
    crop_url: HttpUrl | None = None
    model_id: str = DEFAULT_EMBEDDING_MODEL_ID
    dimensions: int = DEFAULT_EMBEDDING_DIMENSIONS
    limit: int = Field(default=12, ge=1, le=100)
    min_similarity: float = Field(default=0.0, ge=-1.0, le=1.0)


class RankedRegionMatch(BaseModel):
    region_id: str
    rank: int = Field(ge=1)
    match: CatalogMatch


class RegionMatchSet(BaseModel):
    region_id: str
    crop_object_key: str
    crop_url: HttpUrl | None = None
    crop_width: int | None = Field(default=None, gt=0)
    crop_height: int | None = Field(default=None, gt=0)
    model_id: str
    dimensions: int
    matches: list[RankedRegionMatch]


class SegmentMatchRequest(BaseModel):
    run_id: UUID | None = None
    image_object_key: str | None = Field(default=None, min_length=1, max_length=1024)
    image_url: HttpUrl | None = None
    prompt: str = Field(min_length=1)
    confidence_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    max_regions: int = Field(default=5, ge=1, le=20)
    include_masks: bool = False
    model_id: str = DEFAULT_EMBEDDING_MODEL_ID
    dimensions: int = DEFAULT_EMBEDDING_DIMENSIONS
    matches_per_region: int = Field(default=12, ge=1, le=100)
    min_similarity: float = Field(default=0.0, ge=-1.0, le=1.0)

    @model_validator(mode="after")
    def require_image_source(self) -> "SegmentMatchRequest":
        if self.image_object_key is None and self.image_url is None:
            raise ValueError("Either image_object_key or image_url is required")
        return self


class SegmentRegionMatchSet(BaseModel):
    region: SegmentationRegion
    crop_object_key: str
    crop_url: HttpUrl
    crop_width: int = Field(gt=0)
    crop_height: int = Field(gt=0)
    model_id: str
    dimensions: int
    matches: list[RankedRegionMatch]


class SegmentMatchResponse(BaseModel):
    run_id: UUID
    prompt: str
    image_width: int
    image_height: int
    regions: list[SegmentRegionMatchSet]


class UploadImageResponse(BaseModel):
    image_object_key: str
    content_type: str
    size_bytes: int


SearchRunStatus = Literal["running", "completed", "failed"]
SearchRegionStatus = Literal["matched", "failed"]


class MaterialSearchRun(BaseModel):
    id: UUID
    prompt: str
    source_image_object_key: str | None
    source_image_url: HttpUrl | None
    status: SearchRunStatus
    error: str | None
    image_width: int | None
    image_height: int | None
    created_at: datetime
    updated_at: datetime


class MaterialSearchRegionRecord(BaseModel):
    id: UUID
    run_id: UUID
    source_region_id: str
    prompt: str
    score: float
    box_xyxy: list[float]
    mask: dict | None
    crop_object_key: str
    crop_width: int
    crop_height: int
    embedding_model_id: str
    embedding_dimensions: int
    status: SearchRegionStatus
    created_at: datetime
    updated_at: datetime


class MaterialSearchMatchRecord(BaseModel):
    id: UUID
    run_id: UUID
    region_id: UUID
    catalog_item_id: UUID
    embedding_model_id: str
    similarity: float
    rank: int
    created_at: datetime
