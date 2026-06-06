from abc import ABC, abstractmethod
from typing import Literal

import httpx
from pydantic import BaseModel, Field

SAM3_MODEL_ID = "facebook/sam3"


class SegmentationMask(BaseModel):
    format: Literal["uncompressed_rle"]
    size: list[int] = Field(min_length=2, max_length=2)
    counts: list[int] = Field(min_length=1)


class SegmentationRegion(BaseModel):
    id: str
    prompt: str
    score: float = Field(ge=0.0, le=1.0)
    box_xyxy: list[float] = Field(min_length=4, max_length=4)
    mask: SegmentationMask | None = None


class SegmentationResult(BaseModel):
    model_id: str
    image_width: int = Field(gt=0)
    image_height: int = Field(gt=0)
    prompt: str
    regions: list[SegmentationRegion]


class Sam3Client(ABC):
    @abstractmethod
    def segment_image(
        self,
        *,
        prompt: str,
        image_object_key: str | None = None,
        image_url: str | None = None,
        confidence_threshold: float = 0.5,
        max_regions: int = 20,
        include_masks: bool = False,
    ) -> SegmentationResult:
        raise NotImplementedError


class HttpSam3Client(Sam3Client):
    def __init__(self, base_url: str, timeout_seconds: float = 180.0):
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def segment_image(
        self,
        *,
        prompt: str,
        image_object_key: str | None = None,
        image_url: str | None = None,
        confidence_threshold: float = 0.5,
        max_regions: int = 20,
        include_masks: bool = False,
    ) -> SegmentationResult:
        response = httpx.post(
            f"{self.base_url}/segment-image",
            json={
                "prompt": prompt,
                "image_object_key": image_object_key,
                "image_url": image_url,
                "confidence_threshold": confidence_threshold,
                "max_regions": max_regions,
                "include_masks": include_masks,
            },
            timeout=self.timeout_seconds,
            follow_redirects=True,
        )
        response.raise_for_status()
        result = SegmentationResult.model_validate(response.json())
        if result.model_id != SAM3_MODEL_ID:
            raise ValueError(
                f"SAM3 service returned model_id={result.model_id!r}, expected {SAM3_MODEL_ID!r}"
            )
        if result.prompt != prompt:
            raise ValueError(f"SAM3 service returned prompt={result.prompt!r}, expected {prompt!r}")
        if len(result.regions) > max_regions:
            raise ValueError(
                "SAM3 service returned "
                f"{len(result.regions)} regions, expected at most {max_regions}"
            )
        return result


class MissingSam3Client(Sam3Client):
    def segment_image(
        self,
        *,
        prompt: str,
        image_object_key: str | None = None,
        image_url: str | None = None,
        confidence_threshold: float = 0.5,
        max_regions: int = 20,
        include_masks: bool = False,
    ) -> SegmentationResult:
        raise RuntimeError("SAM3_SERVICE_URL is required to segment material regions")
