from app.core.config import get_settings
from app.model_services.embeddings import (
    EmbeddingClient,
    HttpEmbeddingClient,
    MissingEmbeddingClient,
)
from app.model_services.segmentation import HttpSam3Client, MissingSam3Client, Sam3Client


def get_embedding_client() -> EmbeddingClient:
    settings = get_settings()
    if settings.embedding_service_url is None:
        return MissingEmbeddingClient()
    return HttpEmbeddingClient(str(settings.embedding_service_url))


def get_sam3_client() -> Sam3Client:
    settings = get_settings()
    if settings.sam3_service_url is None:
        return MissingSam3Client()
    return HttpSam3Client(str(settings.sam3_service_url))
