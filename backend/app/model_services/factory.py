from app.core.config import get_settings
from app.model_services.embeddings import (
    EmbeddingClient,
    HttpEmbeddingClient,
    MissingEmbeddingClient,
)
from app.model_services.planning import (
    GeminiMaterialPlannerClient,
    MaterialPlannerClient,
    MissingMaterialPlannerClient,
)
from app.model_services.segmentation import (
    FallbackSegmentationClient,
    GeminiBoxSegmentationClient,
    HttpSam3Client,
    MissingSam3Client,
    Sam3Client,
)


def get_embedding_client() -> EmbeddingClient:
    settings = get_settings()
    if settings.embedding_service_url is None:
        return MissingEmbeddingClient()
    return HttpEmbeddingClient(str(settings.embedding_service_url))


def get_sam3_client() -> Sam3Client:
    settings = get_settings()
    if settings.sam3_service_url is None:
        if settings.gemini_api_key:
            return GeminiBoxSegmentationClient(
                api_key=settings.gemini_api_key,
                supabase_url=str(settings.supabase_url) if settings.supabase_url else None,
                service_role_key=settings.supabase_service_role_key,
                uploaded_image_bucket=settings.uploaded_image_bucket,
            )
        return MissingSam3Client()
    sam3_client = HttpSam3Client(
        str(settings.sam3_service_url),
        supabase_url=str(settings.supabase_url) if settings.supabase_url else None,
        service_role_key=settings.supabase_service_role_key,
        uploaded_image_bucket=settings.uploaded_image_bucket,
    )
    if not settings.gemini_api_key:
        return sam3_client
    return FallbackSegmentationClient(
        primary=sam3_client,
        fallback=GeminiBoxSegmentationClient(
            api_key=settings.gemini_api_key,
            supabase_url=str(settings.supabase_url) if settings.supabase_url else None,
            service_role_key=settings.supabase_service_role_key,
            uploaded_image_bucket=settings.uploaded_image_bucket,
        ),
    )


def get_material_planner_client() -> MaterialPlannerClient:
    settings = get_settings()
    if not settings.gemini_api_key:
        return MissingMaterialPlannerClient()
    return GeminiMaterialPlannerClient(
        api_key=settings.gemini_api_key,
        supabase_url=str(settings.supabase_url) if settings.supabase_url else None,
        service_role_key=settings.supabase_service_role_key,
        uploaded_image_bucket=settings.uploaded_image_bucket,
    )
