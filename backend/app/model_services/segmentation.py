import base64
import json
import re
from abc import ABC, abstractmethod
from io import BytesIO
from pathlib import PurePath
from typing import Literal
from urllib.parse import quote

import httpx
from pydantic import BaseModel, Field

SAM3_MODEL_ID = "facebook/sam3"
COARSE_IMAGE_SEGMENTATION_MODEL_ID = "coarse-image-box-fallback"
GEMINI_BOX_SEGMENTATION_MODEL_ID = "gemini-3.5-flash-box-segmentation"
GEMINI_GENERATE_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


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

        response = httpx.post(
            f"{self.base_url}/segment-image",
            json={
                "prompt": prompt,
                "image_object_key": sam3_image_object_key,
                "image_url": sam3_image_url,
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


class FallbackSegmentationClient(Sam3Client):
    def __init__(self, *, primary: Sam3Client, fallback: Sam3Client):
        self.primary = primary
        self.fallback = fallback

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
        try:
            return self.primary.segment_image(
                prompt=prompt,
                image_object_key=image_object_key,
                image_url=image_url,
                confidence_threshold=confidence_threshold,
                max_regions=max_regions,
                include_masks=include_masks,
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 429:
                raise

        return self.fallback.segment_image(
            prompt=prompt,
            image_object_key=image_object_key,
            image_url=image_url,
            confidence_threshold=confidence_threshold,
            max_regions=max_regions,
            include_masks=False,
        )


class CoarseImageSegmentationClient(Sam3Client):
    def __init__(
        self,
        *,
        supabase_url: str | None = None,
        service_role_key: str | None = None,
        uploaded_image_bucket: str = "uploaded-images",
    ):
        self.supabase_url = supabase_url.rstrip("/") if supabase_url else None
        self.service_role_key = service_role_key
        self.uploaded_image_bucket = uploaded_image_bucket

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
        width, height = self._load_image_size(
            image_object_key=image_object_key,
            image_url=image_url,
        )
        return SegmentationResult(
            model_id=COARSE_IMAGE_SEGMENTATION_MODEL_ID,
            image_width=width,
            image_height=height,
            prompt=prompt,
            regions=[
                SegmentationRegion(
                    id="coarse_image_region_0",
                    prompt=prompt,
                    score=0.2,
                    box_xyxy=[0.0, 0.0, float(width), float(height)],
                )
            ],
        )

    def _load_image_size(
        self,
        *,
        image_object_key: str | None,
        image_url: str | None,
    ) -> tuple[int, int]:
        image_bytes = _load_image_bytes(
            image_object_key=image_object_key,
            image_url=image_url,
            supabase_url=self.supabase_url,
            service_role_key=self.service_role_key,
            uploaded_image_bucket=self.uploaded_image_bucket,
        )[0]
        from PIL import Image

        image = Image.open(BytesIO(image_bytes))
        return image.size


class GeminiBoxSegmentationClient(Sam3Client):
    def __init__(
        self,
        *,
        api_key: str,
        model_id: str = "gemini-3.5-flash",
        supabase_url: str | None = None,
        service_role_key: str | None = None,
        uploaded_image_bucket: str = "uploaded-images",
        timeout_seconds: float = 120.0,
    ):
        self.api_key = api_key
        self.model_id = model_id
        self.supabase_url = supabase_url.rstrip("/") if supabase_url else None
        self.service_role_key = service_role_key
        self.uploaded_image_bucket = uploaded_image_bucket
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
        image_bytes, mime_type, width, height = self._load_image(
            image_object_key=image_object_key,
            image_url=image_url,
        )
        response = httpx.post(
            GEMINI_GENERATE_URL.format(model=self.model_id),
            params={"key": self.api_key},
            json={
                "contents": [
                    {
                        "role": "user",
                        "parts": [
                            {
                                "text": _box_segmentation_prompt(
                                    prompt=prompt,
                                    image_width=width,
                                    image_height=height,
                                    confidence_threshold=confidence_threshold,
                                    max_regions=max_regions,
                                )
                            },
                            {
                                "inline_data": {
                                    "mime_type": mime_type,
                                    "data": base64.b64encode(image_bytes).decode("ascii"),
                                }
                            },
                        ],
                    }
                ],
                "generationConfig": {
                    "temperature": 0.1,
                    "response_mime_type": "application/json",
                },
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        text = _first_text_part(payload)
        data = json.loads(_strip_json_fence(text))
        regions = [
            _gemini_region_to_segmentation_region(
                region,
                prompt=prompt,
                width=width,
                height=height,
                index=index,
            )
            for index, region in enumerate(data.get("regions") or [])
        ][:max_regions]
        return SegmentationResult(
            model_id=GEMINI_BOX_SEGMENTATION_MODEL_ID,
            image_width=width,
            image_height=height,
            prompt=prompt,
            regions=regions,
        )

    def _load_image(
        self,
        *,
        image_object_key: str | None,
        image_url: str | None,
    ) -> tuple[bytes, str, int, int]:
        image_bytes, content_type = _load_image_bytes(
            image_object_key=image_object_key,
            image_url=image_url,
            supabase_url=self.supabase_url,
            service_role_key=self.service_role_key,
            uploaded_image_bucket=self.uploaded_image_bucket,
        )
        from PIL import Image

        image = Image.open(BytesIO(image_bytes))
        width, height = image.size
        return (
            image_bytes,
            _image_mime_type(content_type, image_object_key, image_url),
            width,
            height,
        )

    def _object_url(self, object_key: str) -> str:
        quoted_key = quote(object_key.lstrip("/"), safe="/")
        return f"{self.supabase_url}/storage/v1/object/{self.uploaded_image_bucket}/{quoted_key}"

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


def _load_image_bytes(
    *,
    image_object_key: str | None,
    image_url: str | None,
    supabase_url: str | None,
    service_role_key: str | None,
    uploaded_image_bucket: str,
) -> tuple[bytes, str]:
    if image_url:
        response = httpx.get(image_url, timeout=30.0, follow_redirects=True)
    elif image_object_key:
        if supabase_url is None or not service_role_key:
            raise RuntimeError(
                "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required "
                "to segment uploaded image object keys"
            )
        quoted_key = quote(image_object_key.lstrip("/"), safe="/")
        response = httpx.get(
            f"{supabase_url}/storage/v1/object/{uploaded_image_bucket}/{quoted_key}",
            headers={
                "apikey": service_role_key,
                "authorization": f"Bearer {service_role_key}",
            },
            timeout=30.0,
            follow_redirects=True,
        )
    else:
        raise ValueError("Either image_object_key or image_url is required")

    response.raise_for_status()
    content_type = response.headers.get("content-type", "").split(";", maxsplit=1)[0]
    return response.content, content_type


def _box_segmentation_prompt(
    *,
    prompt: str,
    image_width: int,
    image_height: int,
    confidence_threshold: float,
    max_regions: int,
) -> str:
    return f"""
You are segmenting material regions in an image for catalog matching.
Return JSON only. Find up to {max_regions} visible material regions matching:
{prompt}

Image size: {image_width} x {image_height} pixels.
Use pixel coordinates in the original image. Return tight bounding boxes around
physical material surfaces, not decorative labels or furniture outlines unless
the material surface itself is requested. Ignore candidates below confidence
{confidence_threshold}.

JSON shape:
{{
  "regions": [
    {{
      "id": "gemini_region_0",
      "score": 0.0,
      "box_xyxy": [x0, y0, x1, y1]
    }}
  ]
}}
""".strip()


def _first_text_part(payload: dict) -> str:
    candidates = payload.get("candidates") or []
    for candidate in candidates:
        content = candidate.get("content") or {}
        for part in content.get("parts") or []:
            text = part.get("text")
            if isinstance(text, str) and text.strip():
                return text
    raise RuntimeError("Gemini did not return segmentation JSON")


def _strip_json_fence(text: str) -> str:
    stripped = text.strip()
    fence_match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", stripped, flags=re.DOTALL)
    if fence_match:
        stripped = fence_match.group(1).strip()
    json.loads(stripped)
    return stripped


def _gemini_region_to_segmentation_region(
    region: dict,
    *,
    prompt: str,
    width: int,
    height: int,
    index: int,
) -> SegmentationRegion:
    box = region.get("box_xyxy") or []
    if len(box) != 4:
        raise ValueError(f"Gemini region {index} did not include four box coordinates")
    x0, y0, x1, y1 = [float(value) for value in box]
    return SegmentationRegion(
        id=str(region.get("id") or f"gemini_region_{index}"),
        prompt=prompt,
        score=max(0.0, min(1.0, float(region.get("score") or 0.5))),
        box_xyxy=[
            max(0.0, min(float(width), x0)),
            max(0.0, min(float(height), y0)),
            max(0.0, min(float(width), x1)),
            max(0.0, min(float(height), y1)),
        ],
    )


def _image_mime_type(content_type: str, image_object_key: str | None, image_url: str | None) -> str:
    if content_type in {"image/jpeg", "image/png", "image/webp"}:
        return content_type
    suffix = PurePath(image_object_key or image_url or "").suffix.lower()
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }.get(suffix, "image/jpeg")
