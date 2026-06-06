from uuid import UUID

from app.catalog.repository import CatalogRepository
from app.catalog.schemas import CatalogEmbeddingJob, CatalogIndexAccepted
from app.core.config import get_settings


class CatalogIndexingService:
    def __init__(self, repository: CatalogRepository):
        self.repository = repository

    def build_jobs(
        self, *, catalog_item_ids: list[UUID] | None, model_id: str, dimensions: int
    ) -> list[CatalogEmbeddingJob]:
        if catalog_item_ids:
            items = [self.repository.get_item(item_id) for item_id in catalog_item_ids]
            missing_ids = [
                str(item_id)
                for item_id, item in zip(catalog_item_ids, items, strict=True)
                if item is None
            ]
            if missing_ids:
                raise ValueError(f"Unknown catalog item ids: {', '.join(missing_ids)}")
            return [
                CatalogEmbeddingJob(
                    catalog_item_id=item.id,
                    model_id=model_id,
                    dimensions=dimensions,
                )
                for item in items
                if item is not None
            ]

        items = self.repository.list_items_missing_embedding(
            model_id=model_id, dimensions=dimensions, limit=500
        )
        return [
            CatalogEmbeddingJob(catalog_item_id=item.id, model_id=model_id, dimensions=dimensions)
            for item in items
        ]


def default_indexing_request() -> tuple[str, int]:
    settings = get_settings()
    return settings.embedding_model_id, settings.embedding_dimensions


def accepted_response(
    jobs: list[CatalogEmbeddingJob], model_id: str, dimensions: int
) -> CatalogIndexAccepted:
    return CatalogIndexAccepted(enqueued=len(jobs), model_id=model_id, dimensions=dimensions)
