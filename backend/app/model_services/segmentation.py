from abc import ABC, abstractmethod
from typing import Literal
from urllib.parse import quote

import httpx
from pydantic import BaseModel, Field

from app.core.observability import search_source_kind, span

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
    def __init__(
        self,
        base_url: str,
        timeout_seconds: float = 180.0,
        *,
        supabase_url: str | None = None,
        service_role_key: str | None = None,
        uploaded_image_bucket: str = "uploaded-images",
        signed_url_ttl_seconds: int = 3600,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.supabase_url = supabase_url.rstrip("/") if supabase_url else None
        self.service_role_key = service_role_key
        self.uploaded_image_bucket = uploaded_image_bucket
        self.signed_url_ttl_seconds = signed_url_ttl_seconds

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
        sam3_image_url = image_url
        sam3_image_object_key = image_object_key
        if image_object_key and image_url is None and self.supabase_url and self.service_role_key:
            sam3_image_url = self._create_signed_uploaded_image_url(image_object_key)
            sam3_image_object_key = None

        request_body = {
            "prompt": prompt,
            "image_object_key": sam3_image_object_key,
            "image_url": sam3_image_url,
            "confidence_threshold": confidence_threshold,
            "max_regions": max_regions,
            "include_masks": include_masks,
        }
        with span(
            "model_services.sam3.segment_image",
            provider="modal",
            model_id=SAM3_MODEL_ID,
            endpoint="/segment-image",
            prompt=prompt,
            source_kind=search_source_kind(
                image_object_key=sam3_image_object_key,
                image_url=sam3_image_url,
            ),
            image_object_key=sam3_image_object_key,
            has_signed_image_url=sam3_image_url is not None,
            confidence_threshold=confidence_threshold,
            max_regions=max_regions,
            include_masks=include_masks,
        ) as active_span:
            response = httpx.post(
                f"{self.base_url}/segment-image",
                json=request_body,
                timeout=self.timeout_seconds,
                follow_redirects=True,
            )
            active_span.set_attributes(_response_metadata(response))
            response.raise_for_status()
            result = SegmentationResult.model_validate(response.json())
            active_span.set_attributes(
                {
                    "response_model_id": result.model_id,
                    "image_width": result.image_width,
                    "image_height": result.image_height,
                    "region_count": len(result.regions),
                    "regions": [
                        {
                            "id": region.id,
                            "score": region.score,
                            "box_xyxy": region.box_xyxy,
                            "has_mask": region.mask is not None,
                        }
                        for region in result.regions
                    ],
                }
            )
            if result.model_id != SAM3_MODEL_ID:
                raise ValueError(
                    f"SAM3 service returned model_id={result.model_id!r}, "
                    f"expected {SAM3_MODEL_ID!r}"
                )
            if result.prompt != prompt:
                raise ValueError(
                    f"SAM3 service returned prompt={result.prompt!r}, expected {prompt!r}"
                )
            if len(result.regions) > max_regions:
                raise ValueError(
                    "SAM3 service returned "
                    f"{len(result.regions)} regions, expected at most {max_regions}"
                )
            return result

    def _create_signed_uploaded_image_url(self, object_key: str) -> str:
        response = httpx.post(
            (
                f"{self.supabase_url}/storage/v1/object/sign/"
                f"{self.uploaded_image_bucket}/{_quote_key(object_key)}"
            ),
            headers={**self._auth_headers(), "content-type": "application/json"},
            json={"expiresIn": self.signed_url_ttl_seconds},
            timeout=30.0,
        )
        response.raise_for_status()
        payload = response.json()
        signed_url = payload.get("signedURL") or payload.get("signedUrl")
        if not signed_url:
            raise RuntimeError("Supabase did not return a signed URL for the uploaded image")
        if signed_url.startswith("http://") or signed_url.startswith("https://"):
            return signed_url
        return f"{self.supabase_url}/storage/v1{signed_url}"

    def _auth_headers(self) -> dict[str, str]:
        return {
            "apikey": self.service_role_key or "",
            "authorization": f"Bearer {self.service_role_key}",
        }


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


def _quote_key(object_key: str) -> str:
    return quote(object_key.lstrip("/"), safe="/")


def _response_metadata(response: httpx.Response) -> dict[str, int]:
    metadata = {}
    status_code = getattr(response, "status_code", None)
    if status_code is not None:
        metadata["http_status_code"] = status_code
    content = getattr(response, "content", None)
    if content is not None:
        metadata["response_content_length"] = len(content)
    return metadata
