from datetime import UTC, datetime
from math import sqrt
from uuid import UUID, uuid4

import pytest

from app.catalog.schemas import CatalogItem, CatalogMatch
from app.model_services.embeddings import ImageEmbedding
from app.search.matching import RegionMatcher
from app.search.schemas import RegionMatchRequest


class RecordingEmbeddingClient:
    def __init__(self, embedding: ImageEmbedding):
        self.embedding = embedding
        self.calls: list[dict] = []

    def embed_image(
        self, *, image_object_key: str, image_url: str | None, model_id: str, dimensions: int
    ) -> ImageEmbedding:
        self.calls.append(
            {
                "image_object_key": image_object_key,
                "image_url": image_url,
                "model_id": model_id,
                "dimensions": dimensions,
            }
        )
        return self.embedding


class RecordingCatalogRepository:
    def __init__(self, matches: list[CatalogMatch]):
        self.matches = matches
        self.search_calls: list[dict] = []

    def create_item(self, item):
        raise NotImplementedError

    def list_items(self, limit: int = 100, offset: int = 0):
        raise NotImplementedError

    def get_item(self, catalog_item_id: UUID):
        raise NotImplementedError

    def list_items_missing_embedding(self, *, model_id: str, dimensions: int, limit: int = 500):
        raise NotImplementedError

    def count_items_missing_embedding(self, *, model_id: str, dimensions: int):
        raise NotImplementedError

    def upsert_embedding(self, **kwargs):
        raise NotImplementedError

    def search_by_embedding(
        self, *, embedding: list[float], model_id: str, limit: int, min_similarity: float
    ) -> list[CatalogMatch]:
        self.search_calls.append(
            {
                "embedding": embedding,
                "model_id": model_id,
                "limit": limit,
                "min_similarity": min_similarity,
            }
        )
        return self.matches


class InMemoryVectorCatalogRepository(RecordingCatalogRepository):
    def __init__(self, vectors: list[tuple[CatalogItem, list[float]]]):
        super().__init__(matches=[])
        self.vectors = vectors

    def search_by_embedding(
        self, *, embedding: list[float], model_id: str, limit: int, min_similarity: float
    ) -> list[CatalogMatch]:
        self.search_calls.append(
            {
                "embedding": embedding,
                "model_id": model_id,
                "limit": limit,
                "min_similarity": min_similarity,
            }
        )
        scored = [
            CatalogMatch(
                item=item,
                model_id=model_id,
                similarity=_cosine_similarity(embedding, vec),
            )
            for item, vec in self.vectors
        ]
        return [
            match
            for match in sorted(scored, key=lambda match: match.similarity, reverse=True)
            if match.similarity >= min_similarity
        ][:limit]


def test_match_region_embeds_crop_and_searches_catalog():
    match = CatalogMatch(item=make_item(name="Woven Linen"), model_id="test-model", similarity=0.91)
    embedding = ImageEmbedding(model_id="test-model", dimensions=3, embedding=[0.1, 0.2, 0.3])
    embedding_client = RecordingEmbeddingClient(embedding)
    repository = RecordingCatalogRepository([match])

    result = RegionMatcher(repository, embedding_client).match_region(
        RegionMatchRequest(
            region_id="sam3-region-1",
            crop_object_key="runs/run-1/regions/sam3-region-1/crop.jpg",
            crop_url="https://example.com/crop.jpg",
            model_id="test-model",
            dimensions=3,
            limit=5,
            min_similarity=0.4,
        )
    )

    assert embedding_client.calls == [
        {
            "image_object_key": "runs/run-1/regions/sam3-region-1/crop.jpg",
            "image_url": "https://example.com/crop.jpg",
            "model_id": "test-model",
            "dimensions": 3,
        }
    ]
    assert repository.search_calls == [
        {
            "embedding": [0.1, 0.2, 0.3],
            "model_id": "test-model",
            "limit": 5,
            "min_similarity": 0.4,
        }
    ]
    assert result.region_id == "sam3-region-1"
    assert result.model_id == "test-model"
    assert result.dimensions == 3
    assert result.matches[0].rank == 1
    assert result.matches[0].match.item.name == "Woven Linen"


@pytest.mark.parametrize(
    ("embedding", "message"),
    [
        (
            ImageEmbedding(model_id="other-model", dimensions=3, embedding=[0.1, 0.2, 0.3]),
            "model_id",
        ),
        (
            ImageEmbedding(model_id="test-model", dimensions=4, embedding=[0.1, 0.2, 0.3, 0.4]),
            "dimensions",
        ),
        (
            ImageEmbedding(model_id="test-model", dimensions=3, embedding=[0.1, 0.2]),
            "Embedding length",
        ),
    ],
)
def test_match_region_rejects_embedding_contract_mismatches(
    embedding: ImageEmbedding, message: str
):
    matcher = RegionMatcher(
        RecordingCatalogRepository([]),
        RecordingEmbeddingClient(embedding),
    )

    with pytest.raises(ValueError, match=message):
        matcher.match_region(
            RegionMatchRequest(
                region_id="sam3-region-1",
                crop_object_key="runs/run-1/regions/sam3-region-1/crop.jpg",
                model_id="test-model",
                dimensions=3,
            )
        )


def test_region_matching_eval_ranks_nearest_catalog_material():
    textile = make_item(name="Warm Gray Boucle", material_family="textile")
    stone = make_item(name="Honed Limestone", material_family="stone")
    wood = make_item(name="White Oak", material_family="wood")
    repository = InMemoryVectorCatalogRepository(
        [
            (stone, [0.0, 1.0, 0.0]),
            (textile, [1.0, 0.0, 0.0]),
            (wood, [0.0, 0.0, 1.0]),
        ]
    )
    embedding_client = RecordingEmbeddingClient(
        ImageEmbedding(model_id="test-model", dimensions=3, embedding=[0.95, 0.05, 0.0])
    )

    result = RegionMatcher(repository, embedding_client).match_region(
        RegionMatchRequest(
            region_id="sam3-upholstery-region",
            crop_object_key="runs/evals/upholstery/crop.jpg",
            model_id="test-model",
            dimensions=3,
            limit=2,
            min_similarity=0.0,
        )
    )

    assert [ranked.match.item.name for ranked in result.matches] == [
        "Warm Gray Boucle",
        "Honed Limestone",
    ]
    assert result.matches[0].match.similarity > result.matches[1].match.similarity


def test_match_region_returns_empty_matches_when_catalog_has_no_hits():
    embedding_client = RecordingEmbeddingClient(
        ImageEmbedding(model_id="test-model", dimensions=3, embedding=[0.1, 0.2, 0.3])
    )
    repository = RecordingCatalogRepository([])

    result = RegionMatcher(repository, embedding_client).match_region(
        RegionMatchRequest(
            region_id="sam3-region-1",
            crop_object_key="runs/run-1/regions/sam3-region-1/crop.jpg",
            model_id="test-model",
            dimensions=3,
            limit=5,
            min_similarity=0.4,
        )
    )

    assert result.matches == []
    assert repository.search_calls[0]["min_similarity"] == 0.4


def make_item(name: str, material_family: str = "textile") -> CatalogItem:
    now = datetime.now(UTC)
    return CatalogItem(
        id=uuid4(),
        manufacturer="Acme Materials",
        name=name,
        material_family=material_family,
        image_object_key=f"catalog/acme/{name.lower().replace(' ', '-')}.jpg",
        image_url=None,
        metadata={},
        created_at=now,
        updated_at=now,
    )


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    dot = sum(left_value * right_value for left_value, right_value in zip(left, right, strict=True))
    left_norm = sqrt(sum(value * value for value in left))
    right_norm = sqrt(sum(value * value for value in right))
    return dot / (left_norm * right_norm)
