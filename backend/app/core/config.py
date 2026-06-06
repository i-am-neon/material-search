from functools import lru_cache
from typing import Any

from pydantic import AnyHttpUrl, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_EMBEDDING_MODEL_ID = "google/siglip2-so400m-patch14-384"
DEFAULT_EMBEDDING_DIMENSIONS = 1152


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Material Search API"
    environment: str = "local"
    database_url: str = Field(default="", validation_alias="DATABASE_URL")
    redis_url: str = Field(default="redis://localhost:6379/0", validation_alias="REDIS_URL")
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://127.0.0.1:5173",
            "http://localhost:5173",
            "http://127.0.0.1:6006",
            "http://localhost:6006",
            "https://i-am-neon.github.io",
        ],
        validation_alias="CORS_ORIGINS",
    )

    embedding_service_url: AnyHttpUrl | None = Field(
        default=None, validation_alias="EMBEDDING_SERVICE_URL"
    )
    sam3_service_url: AnyHttpUrl | None = Field(default=None, validation_alias="SAM3_SERVICE_URL")
    embedding_model_id: str = Field(
        default=DEFAULT_EMBEDDING_MODEL_ID, validation_alias="EMBEDDING_MODEL_ID"
    )
    embedding_dimensions: int = Field(
        default=DEFAULT_EMBEDDING_DIMENSIONS, validation_alias="EMBEDDING_DIMENSIONS"
    )
    gemini_api_key: str = Field(default="", validation_alias="GEMINI_API_KEY")

    catalog_image_bucket: str = Field(
        default="catalog-images", validation_alias="CATALOG_IMAGE_BUCKET"
    )
    uploaded_image_bucket: str = Field(
        default="uploaded-images", validation_alias="UPLOADED_IMAGE_BUCKET"
    )
    generated_artifact_bucket: str = Field(
        default="generated-artifacts", validation_alias="GENERATED_ARTIFACT_BUCKET"
    )
    supabase_url: AnyHttpUrl | None = Field(default=None, validation_alias="SUPABASE_URL")
    supabase_service_role_key: str = Field(
        default="", validation_alias="SUPABASE_SERVICE_ROLE_KEY"
    )

    @field_validator("embedding_service_url", "sam3_service_url", "supabase_url", mode="before")
    @classmethod
    def empty_url_is_none(cls, value: Any) -> Any:
        if value == "":
            return None
        return value

    @field_validator("redis_url", mode="before")
    @classmethod
    def empty_redis_uses_local_default(cls, value: Any) -> Any:
        if value == "":
            return "redis://localhost:6379/0"
        return value

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: Any) -> Any:
        if value is None or value == "":
            return []
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
