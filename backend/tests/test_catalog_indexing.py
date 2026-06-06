from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from app.catalog.schemas import CatalogEmbeddingJob, CatalogItem
from app.catalog.service import CatalogIndexingService
from app.model_services.embeddings import ImageEmbedding
from app.workers import catalog_indexing


class FakeRepository:
    def __init__(self, items: list[CatalogItem]):
        self.items = {item.id: item for item in items}
        self.upserts: list[dict] = []

    def create_item(self, item):
        raise NotImplementedError

    def list_items(self, limit: int = 100, offset: int = 0):
        return list(self.items.values())[offset : offset + limit]

    def get_item(self, catalog_item_id: UUID):
        return self.items.get(catalog_item_id)

    def list_items_missing_embedding(self, *, model_id: str, dimensions: int, limit: int = 500):
        return list(self.items.values())[:limit]

    def upsert_embedding(self, **kwargs):
        self.upserts.append(kwargs)

    def search_by_embedding(self, *, embedding, model_id: str, limit: int, min_similarity: float):
        raise NotImplementedError


class FakeEmbeddingClient:
    def embed_image(
        self, *, image_object_key: str, image_url: str | None, model_id: str, dimensions: int
    ):
        return ImageEmbedding(
            model_id=model_id,
            dimensions=dimensions,
            embedding=[0.25] * dimensions,
        )


def make_item(item_id: UUID | None = None) -> CatalogItem:
    now = datetime.now(UTC)
    return CatalogItem(
        id=item_id or uuid4(),
        manufacturer="Acme Materials",
        name="Brushed Linen",
        material_family="textile",
        image_object_key="catalog/acme/brushed-linen.jpg",
        image_url=None,
        metadata={"color": "warm gray"},
        created_at=now,
        updated_at=now,
    )


def test_build_jobs_for_missing_embeddings():
    item = make_item()
    repository = FakeRepository([item])

    jobs = CatalogIndexingService(repository).build_jobs(
        catalog_item_ids=None,
        model_id="google/siglip2-so400m-patch14-384",
        dimensions=1152,
    )

    assert [job.catalog_item_id for job in jobs] == [item.id]
    assert jobs[0].model_id == "google/siglip2-so400m-patch14-384"
    assert jobs[0].dimensions == 1152


def test_build_jobs_rejects_unknown_ids():
    missing_id = uuid4()
    repository = FakeRepository([])

    with pytest.raises(ValueError, match=str(missing_id)):
        CatalogIndexingService(repository).build_jobs(
            catalog_item_ids=[missing_id],
            model_id="google/siglip2-so400m-patch14-384",
            dimensions=1152,
        )


def test_enrich_catalog_item_upserts_embedding(monkeypatch):
    item = make_item()
    repository = FakeRepository([item])

    @contextmanager
    def fake_connection() -> Iterator[object]:
        yield object()

    monkeypatch.setattr(catalog_indexing, "get_connection", fake_connection)
    monkeypatch.setattr(catalog_indexing, "PostgresCatalogRepository", lambda conn: repository)
    monkeypatch.setattr(catalog_indexing, "get_embedding_client", lambda: FakeEmbeddingClient())

    catalog_indexing.enrich_catalog_item(
        CatalogEmbeddingJob(catalog_item_id=item.id, model_id="test-model", dimensions=3)
    )

    assert repository.upserts == [
        {
            "catalog_item_id": item.id,
            "model_id": "test-model",
            "dimensions": 3,
            "embedding": [0.25, 0.25, 0.25],
        }
    ]
