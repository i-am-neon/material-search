from datetime import UTC, datetime
from math import sqrt
from uuid import UUID, uuid4

import httpx
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


class RateLimitedEmbeddingClient:
    def embed_image(self, **kwargs):
        request = httpx.Request("POST", "https://embedding.example.com/embed-image")
        response = httpx.Response(
            429,
            request=request,
            text="modal-http: Webhook failed: workspace billing cycle spend limit reached",
        )
        raise httpx.HTTPStatusError(
            "Client error '429 Too Many Requests'",
            request=request,
            response=response,
        )


class RateLimitedCatalogRepository:
    def search_by_embedding(self, **kwargs):
        request = httpx.Request("POST", "https://db.example.com/rpc/match_catalog_items")
        response = httpx.Response(429, request=request, text="rate limit reached")
        raise httpx.HTTPStatusError(
            "Client error '429 Too Many Requests'",
            request=request,
            response=response,
        )


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


def test_match_region_filters_visible_matches_by_material_hint():
    stone = CatalogMatch(
        item=make_item(name="Honed Limestone", material_family="stone"),
        model_id="test-model",
        similarity=0.97,
    )
    wood = CatalogMatch(
        item=make_item(name="White Oak", material_family="wood"),
        model_id="test-model",
        similarity=0.94,
    )
    carpet = CatalogMatch(
        item=make_item(name="Hard Truth - Steel", material_family="flooring"),
        model_id="test-model",
        similarity=0.82,
    )
    entry_carpet = CatalogMatch(
        item=make_item(
            name="Pedigrid - Graphite",
            material_family="textile",
            metadata={"source_category": "Flooring"},
        ),
        model_id="test-model",
        similarity=0.8,
    )
    repository = RecordingCatalogRepository([stone, wood, carpet, entry_carpet])
    embedding_client = RecordingEmbeddingClient(
        ImageEmbedding(model_id="test-model", dimensions=3, embedding=[0.1, 0.2, 0.3])
    )

    result = RegionMatcher(repository, embedding_client).match_region(
        RegionMatchRequest(
            region_id="floor__sam3-region-1",
            crop_object_key="runs/run-1/regions/floor/crop.jpg",
            material_filter_hint="flooring",
            model_id="test-model",
            dimensions=3,
            limit=2,
        )
    )

    assert repository.search_calls[0]["limit"] == 8
    assert [(ranked.rank, ranked.match.item.name) for ranked in result.matches] == [
        (1, "Hard Truth - Steel"),
        (2, "Pedigrid - Graphite"),
    ]


def test_match_region_filters_visible_matches_by_leather_hint():
    textile = CatalogMatch(
        item=make_item(name="Green Performance Boucle", material_family="textile"),
        model_id="test-model",
        similarity=0.97,
    )
    leather = CatalogMatch(
        item=make_item(name="Leather Essentials Cowhide", material_family="leather"),
        model_id="test-model",
        similarity=0.91,
    )
    hide = CatalogMatch(
        item=make_item(
            name="Garrett Wovens",
            material_family="textile",
            metadata={"materials": ["Leather", "Leather Hide"]},
        ),
        model_id="test-model",
        similarity=0.9,
    )
    repository = RecordingCatalogRepository([textile, leather, hide])
    embedding_client = RecordingEmbeddingClient(
        ImageEmbedding(model_id="test-model", dimensions=3, embedding=[0.1, 0.2, 0.3])
    )

    result = RegionMatcher(repository, embedding_client).match_region(
        RegionMatchRequest(
            region_id="chair__sam3-region-1",
            crop_object_key="runs/run-1/regions/chair/crop.jpg",
            material_filter_hint="leather",
            model_id="test-model",
            dimensions=3,
            limit=2,
        )
    )

    assert repository.search_calls[0]["limit"] == 8
    assert [(ranked.rank, ranked.match.item.name) for ranked in result.matches] == [
        (1, "Leather Essentials Cowhide"),
        (2, "Garrett Wovens"),
    ]


def test_match_region_includes_model_selected_surface_alternate():
    textile = CatalogMatch(
        item=make_item(name="Cream Textile Card", material_family="textile"),
        model_id="test-model",
        similarity=0.98,
    )
    stone = CatalogMatch(
        item=make_item(
            name="Honed Limestone",
            material_family="stone",
            metadata={"source_category": "Masonry & Stone"},
        ),
        model_id="test-model",
        similarity=0.95,
    )
    solid_surface = CatalogMatch(
        item=make_item(
            name="Swanstone Solid Surface - Charcoal Gray",
            material_family="surface",
            metadata={"source_category": "Surfaces", "materials": ["countertop", "slab"]},
        ),
        model_id="test-model",
        similarity=0.91,
    )
    repository = RecordingCatalogRepository([textile, stone, solid_surface])
    embedding_client = RecordingEmbeddingClient(
        ImageEmbedding(model_id="test-model", dimensions=3, embedding=[0.1, 0.2, 0.3])
    )

    result = RegionMatcher(repository, embedding_client).match_region(
        RegionMatchRequest(
            region_id="countertop__sam3-region-1",
            crop_object_key="runs/run-1/regions/countertop/crop.jpg",
            material_filter_hint="stone",
            material_filter_hints=["stone", "surface"],
            model_id="test-model",
            dimensions=3,
            limit=2,
        )
    )

    assert repository.search_calls[0]["limit"] == 16
    assert [(ranked.rank, ranked.match.item.name) for ranked in result.matches] == [
        (1, "Honed Limestone"),
        (2, "Swanstone Solid Surface - Charcoal Gray"),
    ]


def test_match_region_does_not_expand_stone_hint_without_model_selected_alternate():
    stone = CatalogMatch(
        item=make_item(name="Honed Limestone", material_family="stone"),
        model_id="test-model",
        similarity=0.95,
    )
    solid_surface = CatalogMatch(
        item=make_item(name="Swanstone Solid Surface - Charcoal Gray", material_family="surface"),
        model_id="test-model",
        similarity=0.91,
    )
    repository = RecordingCatalogRepository([stone, solid_surface])
    embedding_client = RecordingEmbeddingClient(
        ImageEmbedding(model_id="test-model", dimensions=3, embedding=[0.1, 0.2, 0.3])
    )

    result = RegionMatcher(repository, embedding_client).match_region(
        RegionMatchRequest(
            region_id="stone_floor__sam3-region-1",
            crop_object_key="runs/run-1/regions/stone-floor/crop.jpg",
            material_filter_hint="stone",
            model_id="test-model",
            dimensions=3,
            limit=2,
        )
    )

    assert repository.search_calls[0]["limit"] == 8
    assert [(ranked.rank, ranked.match.item.name) for ranked in result.matches] == [
        (1, "Honed Limestone"),
    ]


def test_match_region_filters_hardware_only_from_explicit_planner_category():
    brass_paint = CatalogMatch(
        item=make_item(name="Brass - Paint Finish", material_family="paint"),
        model_id="test-model",
        similarity=0.97,
    )
    brass_pull = CatalogMatch(
        item=make_item(
            name="Round Brass Cabinet Knob",
            material_family="hardware",
            metadata={"source_category": "Hardware"},
        ),
        model_id="test-model",
        similarity=0.89,
    )
    repository = RecordingCatalogRepository([brass_paint, brass_pull])
    embedding_client = RecordingEmbeddingClient(
        ImageEmbedding(model_id="test-model", dimensions=3, embedding=[0.1, 0.2, 0.3])
    )

    result = RegionMatcher(repository, embedding_client).match_region(
        RegionMatchRequest(
            region_id="brass_hardware__sam3-region-1",
            crop_object_key="runs/run-1/regions/brass/crop.jpg",
            material_filter_hint="hardware",
            model_id="test-model",
            dimensions=3,
            limit=1,
        )
    )

    assert repository.search_calls[0]["limit"] == 4
    assert [(ranked.rank, ranked.match.item.name) for ranked in result.matches] == [
        (1, "Round Brass Cabinet Knob"),
    ]


def test_match_region_does_not_infer_category_filter_from_free_text_hint():
    brass_paint = CatalogMatch(
        item=make_item(name="Brass - Paint Finish", material_family="paint"),
        model_id="test-model",
        similarity=0.97,
    )
    brass_pull = CatalogMatch(
        item=make_item(name="Round Brass Cabinet Knob", material_family="hardware"),
        model_id="test-model",
        similarity=0.89,
    )
    repository = RecordingCatalogRepository([brass_paint, brass_pull])
    embedding_client = RecordingEmbeddingClient(
        ImageEmbedding(model_id="test-model", dimensions=3, embedding=[0.1, 0.2, 0.3])
    )

    result = RegionMatcher(repository, embedding_client).match_region(
        RegionMatchRequest(
            region_id="brass_hardware__sam3-region-1",
            crop_object_key="runs/run-1/regions/brass/crop.jpg",
            material_filter_hint="brass hardware pull",
            model_id="test-model",
            dimensions=3,
            limit=1,
        )
    )

    assert repository.search_calls[0]["limit"] == 1
    assert [(ranked.rank, ranked.match.item.name) for ranked in result.matches] == [
        (1, "Brass - Paint Finish"),
    ]


def test_match_region_falls_back_to_nearest_neighbors_when_category_filter_has_no_hits():
    stone = CatalogMatch(
        item=make_item(name="Honed Limestone", material_family="stone"),
        model_id="test-model",
        similarity=0.97,
    )
    wood = CatalogMatch(
        item=make_item(name="White Oak", material_family="wood"),
        model_id="test-model",
        similarity=0.94,
    )
    repository = RecordingCatalogRepository([stone, wood])
    embedding_client = RecordingEmbeddingClient(
        ImageEmbedding(model_id="test-model", dimensions=3, embedding=[0.1, 0.2, 0.3])
    )

    result = RegionMatcher(repository, embedding_client).match_region(
        RegionMatchRequest(
            region_id="floor__sam3-region-1",
            crop_object_key="runs/run-1/regions/floor/crop.jpg",
            material_filter_hint="flooring",
            model_id="test-model",
            dimensions=3,
            limit=1,
        )
    )

    assert [ranked.match.item.name for ranked in result.matches] == ["Honed Limestone"]


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


def test_match_region_propagates_embedding_429_without_keyword_fallback():
    matcher = RegionMatcher(RecordingCatalogRepository([]), RateLimitedEmbeddingClient())

    with pytest.raises(httpx.HTTPStatusError, match="429 Too Many Requests"):
        matcher.match_region(
            RegionMatchRequest(
                region_id="green_upholstery__coarse_image_region_0",
                crop_object_key="runs/run-1/regions/coarse/crop.jpg",
                model_id="test-model",
                dimensions=3,
                limit=2,
                min_similarity=0.0,
            )
        )


def test_match_region_propagates_vector_search_429_without_keyword_fallback():
    matcher = RegionMatcher(
        RateLimitedCatalogRepository(),
        RecordingEmbeddingClient(
            ImageEmbedding(model_id="test-model", dimensions=3, embedding=[0.1, 0.2, 0.3])
        ),
    )

    with pytest.raises(httpx.HTTPStatusError, match="429 Too Many Requests"):
        matcher.match_region(
            RegionMatchRequest(
                region_id="green_upholstery__coarse_image_region_0",
                crop_object_key="runs/run-1/regions/coarse/crop.jpg",
                model_id="test-model",
                dimensions=3,
                limit=2,
                min_similarity=0.0,
            )
        )


def make_item(
    name: str, material_family: str = "textile", metadata: dict | None = None
) -> CatalogItem:
    now = datetime.now(UTC)
    return CatalogItem(
        id=uuid4(),
        manufacturer="Acme Materials",
        name=name,
        material_family=material_family,
        image_object_key=f"catalog/acme/{name.lower().replace(' ', '-')}.jpg",
        image_url=None,
        metadata=metadata or {},
        created_at=now,
        updated_at=now,
    )


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    dot = sum(left_value * right_value for left_value, right_value in zip(left, right, strict=True))
    left_norm = sqrt(sum(value * value for value in left))
    right_norm = sqrt(sum(value * value for value in right))
    return dot / (left_norm * right_norm)
