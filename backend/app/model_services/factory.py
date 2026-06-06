from app.core.config import get_settings
from app.model_services.embeddings import (
    EmbeddingClient,
    HttpEmbeddingClient,
    MissingEmbeddingClient,
)


def get_embedding_client() -> EmbeddingClient:
    settings = get_settings()
    if settings.embedding_service_url is None:
        return MissingEmbeddingClient()
    return HttpEmbeddingClient(str(settings.embedding_service_url))

