from uuid import UUID

import dramatiq

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
        item = repository.get_item(UUID(str(job.catalog_item_id)))
        if item is None:
            raise ValueError(f"Catalog item {job.catalog_item_id} does not exist")

        client = get_embedding_client()
        embedding = client.embed_image(
            image_object_key=item.image_object_key,
            image_url=str(item.image_url) if item.image_url else None,
            model_id=job.model_id,
            dimensions=job.dimensions,
        )
        repository.upsert_embedding(
            catalog_item_id=item.id,
            model_id=embedding.model_id,
            dimensions=embedding.dimensions,
            embedding=embedding.embedding,
        )

