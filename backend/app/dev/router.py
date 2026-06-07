from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, HttpUrl, model_validator

from app.model_services.factory import get_sam3_client
from app.model_services.segmentation import Sam3Client, SegmentationResult

router = APIRouter(prefix="/dev", tags=["dev"])


class RawSam3SegmentRequest(BaseModel):
    image_object_key: str | None = Field(default=None, min_length=1, max_length=1024)
    image_url: HttpUrl | None = None
    prompt: str = Field(min_length=1, max_length=240)
    confidence_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    max_regions: int = Field(default=20, ge=1, le=100)
    include_masks: bool = False

    @model_validator(mode="after")
    def require_image_source(self) -> "RawSam3SegmentRequest":
        if self.image_object_key is None and self.image_url is None:
            raise ValueError("Either image_object_key or image_url is required")
        return self


@router.post("/sam3/segment", response_model=SegmentationResult)
def segment_with_sam3(
    request: RawSam3SegmentRequest,
    sam3_client: Annotated[Sam3Client, Depends(get_sam3_client)],
) -> SegmentationResult:
    try:
        return sam3_client.segment_image(
            prompt=request.prompt,
            image_object_key=request.image_object_key,
            image_url=str(request.image_url) if request.image_url else None,
            confidence_threshold=request.confidence_threshold,
            max_regions=request.max_regions,
            include_masks=request.include_masks,
        )
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"SAM3 service request failed: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
