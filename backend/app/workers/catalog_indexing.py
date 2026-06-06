import dramatiq

from app.catalog.enrichment import CatalogEnricher
from app.catalog.repository import PostgresCatalogRepository
from app.catalog.schemas import CatalogEmbeddingJob
from app.db import get_connection
from app.model_services.factory import get_embedding_client
from app.workers import broker as _broker  # noqa: F401


@dramatiq.actor(queue_name="catalog-indexing", max_retries=3)
def index_catalog_item(payload: dict) -> None:
    job = CatalogEmbeddingJob.model_validate(payload)
    enrich_catalog_item(job)


def enrich_catalog_item(job: CatalogEmbeddingJob) -> None:
    with get_connection() as conn:
        repository = PostgresCatalogRepository(conn)
        CatalogEnricher(repository, get_embedding_client()).enrich_item(job)
