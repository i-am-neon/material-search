from abc import ABC, abstractmethod
from io import BytesIO
from math import ceil, floor
from urllib.parse import quote

import httpx
from PIL import Image
from pydantic import BaseModel

from app.core.config import get_settings
from app.model_services.segmentation import SegmentationMask, SegmentationRegion


class RegionArtifact(BaseModel):
    object_key: str
    signed_url: str
    width: int
    height: int


class RegionArtifactStore(ABC):
    @abstractmethod
    def create_region_crop(
        self,
        *,
        run_id: str,
        source_image_object_key: str | None,
        source_image_url: str | None,
        region: SegmentationRegion,
        image_width: int,
        image_height: int,
    ) -> RegionArtifact:
        raise NotImplementedError


class SupabaseRegionArtifactStore(RegionArtifactStore):
    def __init__(
        self,
        *,
        supabase_url: str,
        service_role_key: str,
        uploaded_image_bucket: str,
        generated_artifact_bucket: str,
        signed_url_ttl_seconds: int = 3600,
        timeout_seconds: float = 30.0,
    ):
        self.supabase_url = supabase_url.rstrip("/")
        self.service_role_key = service_role_key
        self.uploaded_image_bucket = uploaded_image_bucket
        self.generated_artifact_bucket = generated_artifact_bucket
        self.signed_url_ttl_seconds = signed_url_ttl_seconds
        self.timeout_seconds = timeout_seconds

    def create_region_crop(
        self,
        *,
        run_id: str,
        source_image_object_key: str | None,
        source_image_url: str | None,
        region: SegmentationRegion,
        image_width: int,
        image_height: int,
    ) -> RegionArtifact:
        image = self._load_source_image(
            image_object_key=source_image_object_key,
            image_url=source_image_url,
        )
        crop = crop_region_image(
            image=image,
            region=region,
            image_width=image_width,
            image_height=image_height,
        )
        object_key = f"runs/{run_id}/regions/{region.id}/crop.jpg"
        image_bytes = encode_jpeg(crop)
        self._upload_object(
            bucket=self.generated_artifact_bucket,
            object_key=object_key,
            content=image_bytes,
            content_type="image/jpeg",
        )
        return RegionArtifact(
            object_key=object_key,
            signed_url=self._create_signed_url(
                bucket=self.generated_artifact_bucket,
                object_key=object_key,
            ),
            width=crop.width,
            height=crop.height,
        )

    def _load_source_image(
        self, *, image_object_key: str | None, image_url: str | None
    ) -> Image.Image:
        if image_url:
            response = httpx.get(
                image_url,
                timeout=self.timeout_seconds,
                follow_redirects=True,
            )
        elif image_object_key:
            response = httpx.get(
                self._object_url(self.uploaded_image_bucket, image_object_key),
                headers=self._auth_headers(),
                timeout=self.timeout_seconds,
                follow_redirects=True,
            )
        else:
            raise ValueError("Either source_image_object_key or source_image_url is required")

        response.raise_for_status()
        return Image.open(BytesIO(response.content)).convert("RGB")

    def _upload_object(
        self, *, bucket: str, object_key: str, content: bytes, content_type: str
    ) -> None:
        response = httpx.post(
            self._object_url(bucket, object_key),
            headers={
                **self._auth_headers(),
                "content-type": content_type,
                "x-upsert": "true",
            },
            content=content,
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()

    def _create_signed_url(self, *, bucket: str, object_key: str) -> str:
        response = httpx.post(
            f"{self.supabase_url}/storage/v1/object/sign/{bucket}/{_quote_key(object_key)}",
            headers={**self._auth_headers(), "content-type": "application/json"},
            json={"expiresIn": self.signed_url_ttl_seconds},
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        signed_url = payload.get("signedURL") or payload.get("signedUrl")
        if not signed_url:
            raise RuntimeError("Supabase did not return a signed URL for the region crop")
        if signed_url.startswith("http://") or signed_url.startswith("https://"):
            return signed_url
        return f"{self.supabase_url}/storage/v1{signed_url}"

    def _object_url(self, bucket: str, object_key: str) -> str:
        return f"{self.supabase_url}/storage/v1/object/{bucket}/{_quote_key(object_key)}"

    def _auth_headers(self) -> dict[str, str]:
        return {
            "apikey": self.service_role_key,
            "authorization": f"Bearer {self.service_role_key}",
        }


class MissingRegionArtifactStore(RegionArtifactStore):
    def create_region_crop(
        self,
        *,
        run_id: str,
        source_image_object_key: str | None,
        source_image_url: str | None,
        region: SegmentationRegion,
        image_width: int,
        image_height: int,
    ) -> RegionArtifact:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required to create region crops"
        )


def get_region_artifact_store() -> RegionArtifactStore:
    settings = get_settings()
    if settings.supabase_url is None or not settings.supabase_service_role_key:
        return MissingRegionArtifactStore()
    return SupabaseRegionArtifactStore(
        supabase_url=str(settings.supabase_url),
        service_role_key=settings.supabase_service_role_key,
        uploaded_image_bucket=settings.uploaded_image_bucket,
        generated_artifact_bucket=settings.generated_artifact_bucket,
    )


def crop_region_image(
    *,
    image: Image.Image,
    region: SegmentationRegion,
    image_width: int,
    image_height: int,
) -> Image.Image:
    if image.size != (image_width, image_height):
        image = image.resize((image_width, image_height))

    x0, y0, x1, y1 = clamp_box(region.box_xyxy, image_width, image_height)
    if x1 <= x0 or y1 <= y0:
        raise ValueError(f"Region {region.id!r} has an empty crop box")

    crop = image.crop((x0, y0, x1, y1))
    if region.mask is None:
        return crop

    mask = decode_uncompressed_rle_mask(region.mask)
    mask_crop = mask.crop((x0, y0, x1, y1))
    background = Image.new("RGB", crop.size, "white")
    background.paste(crop, mask=mask_crop)
    return background


def clamp_box(box_xyxy: list[float], width: int, height: int) -> tuple[int, int, int, int]:
    x0, y0, x1, y1 = box_xyxy
    return (
        max(0, min(width, floor(x0))),
        max(0, min(height, floor(y0))),
        max(0, min(width, ceil(x1))),
        max(0, min(height, ceil(y1))),
    )


def decode_uncompressed_rle_mask(mask: SegmentationMask) -> Image.Image:
    if mask.format != "uncompressed_rle":
        raise ValueError(f"Unsupported mask format {mask.format!r}")
    height, width = mask.size
    values: list[int] = []
    current = 0
    for count in mask.counts:
        values.extend([current] * count)
        current = 1 - current
    expected = width * height
    if len(values) != expected:
        raise ValueError(f"Mask has {len(values)} pixels, expected {expected}")
    mask_bytes = bytes(255 if value else 0 for value in values)
    return Image.frombytes("L", (width, height), mask_bytes)


def encode_jpeg(image: Image.Image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=92)
    return buffer.getvalue()


def _quote_key(object_key: str) -> str:
    return quote(object_key.lstrip("/"), safe="/")
