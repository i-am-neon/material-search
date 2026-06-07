from dataclasses import dataclass
from uuid import UUID

from app.catalog.repository import CatalogRepository
from app.catalog.schemas import CatalogEmbeddingJob
from app.core.observability import span
from app.model_services.embeddings import EmbeddingClient


@dataclass(frozen=True)
class CatalogEnrichmentResult:
    catalog_item_id: UUID
    model_id: str
    dimensions: int


class CatalogEnricher:
    def __init__(self, repository: CatalogRepository, embedding_client: EmbeddingClient):
        self.repository = repository
        self.embedding_client = embedding_client

    def enrich_item(self, job: CatalogEmbeddingJob) -> CatalogEnrichmentResult:
        item = self.repository.get_item(UUID(str(job.catalog_item_id)))
        if item is None:
            raise ValueError(f"Catalog item {job.catalog_item_id} does not exist")

        with span(
            "catalog.embed_item_image",
            catalog_item_id=str(item.id),
            manufacturer=item.manufacturer,
            material_family=item.material_family,
            model_id=job.model_id,
            dimensions=job.dimensions,
            has_image_url=item.image_url is not None,
        ) as active_span:
            embedding = self.embedding_client.embed_image(
                image_object_key=item.image_object_key,
                image_url=str(item.image_url) if item.image_url else None,
                model_id=job.model_id,
                dimensions=job.dimensions,
            )
            active_span.set_attributes(
                {
                    "embedding_model_id": embedding.model_id,
                    "embedding_dimensions": embedding.dimensions,
                }
            )
        self.repository.upsert_embedding(
            catalog_item_id=item.id,
            model_id=embedding.model_id,
            dimensions=embedding.dimensions,
            embedding=embedding.embedding,
        )
        return CatalogEnrichmentResult(
            catalog_item_id=item.id,
            model_id=embedding.model_id,
            dimensions=embedding.dimensions,
        )
