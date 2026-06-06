from abc import ABC, abstractmethod
from pathlib import PurePath
from uuid import uuid4

import httpx
from pydantic import BaseModel

from app.core.config import get_settings
from app.search.artifacts import _quote_key


class UploadedImage(BaseModel):
    object_key: str
    content_type: str
    size_bytes: int


class UploadedImageStore(ABC):
    @abstractmethod
    def upload_image(
        self, *, filename: str, content: bytes, content_type: str | None
    ) -> UploadedImage:
        raise NotImplementedError


class SupabaseUploadedImageStore(UploadedImageStore):
    def __init__(
        self,
        *,
        supabase_url: str,
        service_role_key: str,
        uploaded_image_bucket: str,
        timeout_seconds: float = 30.0,
    ):
        self.supabase_url = supabase_url.rstrip("/")
        self.service_role_key = service_role_key
        self.uploaded_image_bucket = uploaded_image_bucket
        self.timeout_seconds = timeout_seconds

    def upload_image(
        self, *, filename: str, content: bytes, content_type: str | None
    ) -> UploadedImage:
        validated_content_type = validate_upload_content_type(content_type)
        object_key = build_upload_object_key(filename, validated_content_type)
        response = httpx.post(
            self._object_url(object_key),
            headers={
                **self._auth_headers(),
                "content-type": validated_content_type,
                "x-upsert": "false",
            },
            content=content,
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        return UploadedImage(
            object_key=object_key,
            content_type=validated_content_type,
            size_bytes=len(content),
        )

    def _object_url(self, object_key: str) -> str:
        return (
            f"{self.supabase_url}/storage/v1/object/"
            f"{self.uploaded_image_bucket}/{_quote_key(object_key)}"
        )

    def _auth_headers(self) -> dict[str, str]:
        return {
            "apikey": self.service_role_key,
            "authorization": f"Bearer {self.service_role_key}",
        }


class MissingUploadedImageStore(UploadedImageStore):
    def upload_image(
        self, *, filename: str, content: bytes, content_type: str | None
    ) -> UploadedImage:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required to upload reference images"
        )


def get_uploaded_image_store() -> UploadedImageStore:
    settings = get_settings()
    if settings.supabase_url is None or not settings.supabase_service_role_key:
        return MissingUploadedImageStore()
    return SupabaseUploadedImageStore(
        supabase_url=str(settings.supabase_url),
        service_role_key=settings.supabase_service_role_key,
        uploaded_image_bucket=settings.uploaded_image_bucket,
    )


def validate_upload_content_type(content_type: str | None) -> str:
    if content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise ValueError("Only JPEG, PNG, and WebP images can be uploaded")
    return content_type


def build_upload_object_key(filename: str, content_type: str) -> str:
    suffix = PurePath(filename).suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
        suffix = {
            "image/jpeg": ".jpg",
            "image/png": ".png",
            "image/webp": ".webp",
        }[content_type]
    return f"uploads/{uuid4()}/reference{suffix}"
