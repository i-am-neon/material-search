import dramatiq

from app.catalog.enrichment import CatalogEnricher
from app.catalog.repository import PostgresCatalogRepository
from app.catalog.schemas import CatalogEmbeddingJob
from app.core.observability import span
from app.db import get_connection
from app.model_services.factory import get_embedding_client
from app.workers import broker as _broker  # noqa: F401


@dramatiq.actor(queue_name="catalog-indexing", max_retries=3)
def index_catalog_item(payload: dict) -> None:
    job = CatalogEmbeddingJob.model_validate(payload)
    with span(
        "catalog.worker_index_item",
        queue_name="catalog-indexing",
        catalog_item_id=str(job.catalog_item_id),
        model_id=job.model_id,
        dimensions=job.dimensions,
    ):
        enrich_catalog_item(job)


def enrich_catalog_item(job: CatalogEmbeddingJob) -> None:
    with span(
        "catalog.enrich_item",
        catalog_item_id=str(job.catalog_item_id),
        model_id=job.model_id,
        dimensions=job.dimensions,
    ):
        with get_connection() as conn:
            repository = PostgresCatalogRepository(conn)
            CatalogEnricher(repository, get_embedding_client()).enrich_item(job)
