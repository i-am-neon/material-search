from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator

from app.catalog.schemas import CatalogMatch
from app.core.config import DEFAULT_EMBEDDING_DIMENSIONS, DEFAULT_EMBEDDING_MODEL_ID
from app.model_services.segmentation import SegmentationRegion

CATALOG_FILTER_CATEGORIES: tuple[str, ...] = (
    "tile",
    "paint",
    "surface",
    "flooring",
    "textile",
    "leather",
    "wallcovering",
    "stone",
    "paneling",
    "bathroom",
    "kitchen",
    "hardware",
    "lighting",
    "furniture",
)


class PlannedMaterialTarget(BaseModel):
    target_id: str = Field(min_length=1, max_length=64)
    label: str = Field(min_length=1, max_length=120)
    sam3_prompt: str = Field(min_length=1, max_length=160)
    material_family_hint: str | None = Field(default=None, max_length=80)
    material_family_hints: list[str] = Field(default_factory=list, max_length=5)
    reason: str = Field(min_length=1, max_length=500)
    priority: int = Field(ge=1, le=20)
    max_regions: int = Field(default=2, ge=1, le=5)

    @field_validator("material_family_hint")
    @classmethod
    def normalize_material_family_hint(cls, value: str | None) -> str | None:
        normalized = (value or "").lower().replace("_", " ").replace("-", " ").strip()
        if not normalized or normalized in {"null", "none"}:
            return None
        allowed = set(CATALOG_FILTER_CATEGORIES)
        return normalized if normalized in allowed else None

    @field_validator("material_family_hints", mode="before")
    @classmethod
    def normalize_material_family_hints(cls, value: object) -> list[str]:
        if value is None or value == "":
            return []
        values = [value] if isinstance(value, str) else value
        if not isinstance(values, list):
            return []

        allowed = set(CATALOG_FILTER_CATEGORIES)
        normalized_values: list[str] = []
        for item in values:
            if not isinstance(item, str):
                continue
            normalized = item.lower().replace("_", " ").replace("-", " ").strip()
            if normalized in allowed and normalized not in normalized_values:
                normalized_values.append(normalized)
        return normalized_values


class MaterialSearchPlan(BaseModel):
    user_intent_summary: str = Field(min_length=1, max_length=500)
    avoid: list[str] = Field(default_factory=list, max_length=12)
    is_material_search: bool = True
    unsupported_reason: str | None = Field(default=None, max_length=500)
    targets: list[PlannedMaterialTarget] = Field(default_factory=list, max_length=15)

    @model_validator(mode="after")
    def require_targets_for_material_search(self) -> "MaterialSearchPlan":
        if self.is_material_search and not self.targets:
            raise ValueError("Material search plans require at least one target")
        if not self.is_material_search and not self.unsupported_reason:
            raise ValueError("Unsupported material search plans require unsupported_reason")
        return self


class RegionMatchRequest(BaseModel):
    region_id: str = Field(min_length=1)
    crop_object_key: str = Field(min_length=1, max_length=1024)
    crop_url: HttpUrl | None = None
    material_filter_hint: str | None = Field(default=None, max_length=400)
    material_filter_hints: list[str] = Field(default_factory=list, max_length=5)
    model_id: str = DEFAULT_EMBEDDING_MODEL_ID
    dimensions: int = DEFAULT_EMBEDDING_DIMENSIONS
    limit: int = Field(default=12, ge=1, le=100)
    min_similarity: float = Field(default=0.0, ge=-1.0, le=1.0)

    @field_validator("material_filter_hints", mode="before")
    @classmethod
    def normalize_material_filter_hints(cls, value: object) -> list[str]:
        return PlannedMaterialTarget.normalize_material_family_hints(value)


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
    result_region_id: str
    region: SegmentationRegion
    target_id: str | None = None
    target_label: str | None = None
    crop_object_key: str
    crop_url: HttpUrl | None = None
    crop_width: int = Field(gt=0)
    crop_height: int = Field(gt=0)
    model_id: str
    dimensions: int
    matches: list[RankedRegionMatch]


class SegmentMatchResponse(BaseModel):
    run_id: UUID
    prompt: str
    plan: MaterialSearchPlan | None = None
    image_width: int
    image_height: int
    regions: list[SegmentRegionMatchSet]


class UploadImageResponse(BaseModel):
    image_object_key: str
    content_type: str
    size_bytes: int


SearchRunStatus = Literal["queued", "running", "completed", "failed"]
SearchRegionStatus = Literal["matched", "failed"]
# Finer-grained pipeline position within a running run, streamed to the client.
SearchRunStage = Literal["queued", "planning", "segmenting", "matching", "complete", "failed"]
ProgressSurfaceStatus = Literal["pending", "matching", "matched"]


class MaterialSearchRun(BaseModel):
    id: UUID
    prompt: str
    source_image_object_key: str | None
    source_image_url: HttpUrl | None
    status: SearchRunStatus
    stage: SearchRunStage = "queued"
    intent_summary: str | None = None
    error: str | None
    image_width: int | None
    image_height: int | None
    created_at: datetime
    updated_at: datetime


class StoredSegment(BaseModel):
    """A segmented surface persisted at segmentation time, before matching runs."""

    result_region_id: str
    target_id: str | None = None
    source_region_id: str
    label: str
    box_xyxy: list[float]
    score: float


class ProgressSurface(BaseModel):
    result_region_id: str
    label: str
    box_xyxy: list[float]
    score: float
    status: ProgressSurfaceStatus
    match_count: int = 0
    thumb_url: str | None = None


class SearchRunProgress(BaseModel):
    """Partial view of a run while it executes; the client polls a stream of these."""

    stage: SearchRunStage
    intent: str | None = None
    planned_targets: list[str] = Field(default_factory=list)
    surfaces: list[ProgressSurface] = Field(default_factory=list)
    image_width: int | None = None
    image_height: int | None = None


class MaterialSearchRegionRecord(BaseModel):
    id: UUID
    run_id: UUID
    target_id: str | None = None
    target_label: str | None = None
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


class SearchRunAccepted(BaseModel):
    run_id: UUID
    status: SearchRunStatus


class SearchRunStatusResponse(BaseModel):
    run: MaterialSearchRun
    result: SegmentMatchResponse | None = None
    progress: SearchRunProgress | None = None


def build_result_region_id(*, target_id: str | None, source_region_id: str) -> str:
    return f"{target_id}__{source_region_id}" if target_id else source_region_id
