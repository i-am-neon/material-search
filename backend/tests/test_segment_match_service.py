from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from app.catalog.schemas import CatalogItem, CatalogMatch
from app.model_services.embeddings import ImageEmbedding
from app.model_services.segmentation import SegmentationRegion, SegmentationResult
from app.search.artifacts import RegionArtifact
from app.search.schemas import (
    MaterialSearchMatchRecord,
    MaterialSearchRegionRecord,
    MaterialSearchRun,
    SegmentMatchRequest,
)
from app.search.service import SegmentCatalogMatchService


class FakeSam3Client:
    def __init__(self):
        self.calls: list[dict] = []

    def segment_image(
        self,
        *,
        prompt: str,
        image_object_key: str | None = None,
        image_url: str | None = None,
        confidence_threshold: float = 0.5,
        max_regions: int = 20,
        include_masks: bool = False,
    ) -> SegmentationResult:
        self.calls.append(
            {
                "prompt": prompt,
                "image_object_key": image_object_key,
                "image_url": image_url,
                "confidence_threshold": confidence_threshold,
                "max_regions": max_regions,
                "include_masks": include_masks,
            }
        )
        return SegmentationResult(
            model_id="facebook/sam3",
            image_width=640,
            image_height=480,
            prompt=prompt,
            regions=[
                SegmentationRegion(
                    id="sam3_region_0",
                    prompt=prompt,
                    score=0.91,
                    box_xyxy=[10.0, 20.0, 110.0, 120.0],
                )
            ],
        )


class FailingSam3Client:
    def segment_image(self, **kwargs):
        raise RuntimeError("SAM3 unavailable")


class FakeArtifactStore:
    def __init__(self):
        self.calls: list[dict] = []

    def create_region_crop(
        self,
        *,
        run_id: str,
        source_image_object_key: str | None,
        source_image_url: str | None,
        region: SegmentationRegion,
        image_width: int,
        image_height: int,
    ) -> RegionArtifact:
        self.calls.append(
            {
                "run_id": run_id,
                "source_image_object_key": source_image_object_key,
                "source_image_url": source_image_url,
                "region_id": region.id,
                "image_width": image_width,
                "image_height": image_height,
            }
        )
        return RegionArtifact(
            object_key=f"runs/{run_id}/regions/{region.id}/crop.jpg",
            signed_url=f"https://example.com/signed/{region.id}.jpg",
            width=100,
            height=100,
        )


class FakeEmbeddingClient:
    def __init__(self):
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
        return ImageEmbedding(
            model_id=model_id,
            dimensions=dimensions,
            embedding=[0.2] * dimensions,
        )


class FakeCatalogRepository:
    def __init__(self):
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
        return [
            CatalogMatch(
                item=make_item(),
                model_id=model_id,
                similarity=0.88,
            )
        ]


class FakeSearchRunRepository:
    def __init__(self):
        self.create_run_calls: list[SegmentMatchRequest] = []
        self.create_region_calls: list[dict] = []
        self.replace_region_matches_calls: list[dict] = []
        self.complete_run_calls: list[dict] = []
        self.fail_run_calls: list[dict] = []
        self.region_id = uuid4()

    def create_run(self, request: SegmentMatchRequest) -> MaterialSearchRun:
        self.create_run_calls.append(request)
        now = datetime.now(UTC)
        return MaterialSearchRun(
            id=request.run_id or uuid4(),
            prompt=request.prompt,
            source_image_object_key=request.image_object_key,
            source_image_url=request.image_url,
            status="running",
            error=None,
            image_width=None,
            image_height=None,
            created_at=now,
            updated_at=now,
        )

    def complete_run(
        self, *, run_id: UUID, image_width: int, image_height: int
    ) -> MaterialSearchRun:
        self.complete_run_calls.append(
            {"run_id": run_id, "image_width": image_width, "image_height": image_height}
        )
        now = datetime.now(UTC)
        return MaterialSearchRun(
            id=run_id,
            prompt="upholstery",
            source_image_object_key="uploads/room.jpg",
            source_image_url=None,
            status="completed",
            error=None,
            image_width=image_width,
            image_height=image_height,
            created_at=now,
            updated_at=now,
        )

    def fail_run(self, *, run_id: UUID, error: str) -> MaterialSearchRun:
        self.fail_run_calls.append({"run_id": run_id, "error": error})
        now = datetime.now(UTC)
        return MaterialSearchRun(
            id=run_id,
            prompt="upholstery",
            source_image_object_key="uploads/room.jpg",
            source_image_url=None,
            status="failed",
            error=error,
            image_width=None,
            image_height=None,
            created_at=now,
            updated_at=now,
        )

    def create_region(
        self,
        *,
        run_id: UUID,
        region: SegmentationRegion,
        artifact: RegionArtifact,
        embedding_model_id: str,
        embedding_dimensions: int,
    ) -> MaterialSearchRegionRecord:
        self.create_region_calls.append(
            {
                "run_id": run_id,
                "source_region_id": region.id,
                "artifact_object_key": artifact.object_key,
                "embedding_model_id": embedding_model_id,
                "embedding_dimensions": embedding_dimensions,
            }
        )
        now = datetime.now(UTC)
        return MaterialSearchRegionRecord(
            id=self.region_id,
            run_id=run_id,
            source_region_id=region.id,
            prompt=region.prompt,
            score=region.score,
            box_xyxy=region.box_xyxy,
            mask=None,
            crop_object_key=artifact.object_key,
            crop_width=artifact.width,
            crop_height=artifact.height,
            embedding_model_id=embedding_model_id,
            embedding_dimensions=embedding_dimensions,
            status="matched",
            created_at=now,
            updated_at=now,
        )

    def replace_region_matches(
        self,
        *,
        run_id: UUID,
        region_id: UUID,
        matches,
    ) -> list[MaterialSearchMatchRecord]:
        self.replace_region_matches_calls.append(
            {
                "run_id": run_id,
                "region_id": region_id,
                "match_count": len(matches),
                "first_rank": matches[0].rank,
            }
        )
        now = datetime.now(UTC)
        return [
            MaterialSearchMatchRecord(
                id=uuid4(),
                run_id=run_id,
                region_id=region_id,
                catalog_item_id=match.match.item.id,
                embedding_model_id=match.match.model_id,
                similarity=match.match.similarity,
                rank=match.rank,
                created_at=now,
            )
            for match in matches
        ]


def test_segment_catalog_match_service_crops_embeds_and_matches_regions():
    sam3_client = FakeSam3Client()
    artifact_store = FakeArtifactStore()
    embedding_client = FakeEmbeddingClient()
    repository = FakeCatalogRepository()
    search_repository = FakeSearchRunRepository()
    run_id = uuid4()

    response = SegmentCatalogMatchService(
        sam3_client=sam3_client,
        artifact_store=artifact_store,
        embedding_client=embedding_client,
        catalog_repository=repository,
        search_run_repository=search_repository,
    ).segment_and_match(
        SegmentMatchRequest(
            run_id=run_id,
            image_object_key="uploads/room.jpg",
            prompt="upholstery",
            confidence_threshold=0.4,
            max_regions=3,
            model_id="test-model",
            dimensions=3,
            matches_per_region=2,
            min_similarity=0.5,
        )
    )

    assert sam3_client.calls[0]["image_object_key"] == "uploads/room.jpg"
    assert artifact_store.calls == [
        {
            "run_id": str(run_id),
            "source_image_object_key": "uploads/room.jpg",
            "source_image_url": None,
            "region_id": "sam3_region_0",
            "image_width": 640,
            "image_height": 480,
        }
    ]
    assert embedding_client.calls == [
        {
            "image_object_key": f"runs/{run_id}/regions/sam3_region_0/crop.jpg",
            "image_url": "https://example.com/signed/sam3_region_0.jpg",
            "model_id": "test-model",
            "dimensions": 3,
        }
    ]
    assert repository.search_calls[0]["limit"] == 2
    assert repository.search_calls[0]["min_similarity"] == 0.5
    assert search_repository.create_run_calls[0].run_id == run_id
    assert search_repository.create_region_calls == [
        {
            "run_id": run_id,
            "source_region_id": "sam3_region_0",
            "artifact_object_key": f"runs/{run_id}/regions/sam3_region_0/crop.jpg",
            "embedding_model_id": "test-model",
            "embedding_dimensions": 3,
        }
    ]
    assert search_repository.replace_region_matches_calls == [
        {
            "run_id": run_id,
            "region_id": search_repository.region_id,
            "match_count": 1,
            "first_rank": 1,
        }
    ]
    assert search_repository.complete_run_calls == [
        {"run_id": run_id, "image_width": 640, "image_height": 480}
    ]
    assert search_repository.fail_run_calls == []
    assert response.run_id == run_id
    assert response.regions[0].region.id == "sam3_region_0"
    assert response.regions[0].crop_width == 100
    assert response.regions[0].matches[0].rank == 1
    assert response.regions[0].matches[0].match.item.name == "Warm Gray Boucle"


def test_segment_catalog_match_service_marks_run_failed_on_error():
    search_repository = FakeSearchRunRepository()
    run_id = uuid4()

    with pytest.raises(RuntimeError, match="SAM3 unavailable"):
        SegmentCatalogMatchService(
            sam3_client=FailingSam3Client(),
            artifact_store=FakeArtifactStore(),
            embedding_client=FakeEmbeddingClient(),
            catalog_repository=FakeCatalogRepository(),
            search_run_repository=search_repository,
        ).segment_and_match(
            SegmentMatchRequest(
                run_id=run_id,
                image_object_key="uploads/room.jpg",
                prompt="upholstery",
                model_id="test-model",
                dimensions=3,
            )
        )

    assert search_repository.complete_run_calls == []
    assert search_repository.fail_run_calls == [
        {"run_id": run_id, "error": "SAM3 unavailable"}
    ]


def make_item() -> CatalogItem:
    now = datetime.now(UTC)
    return CatalogItem(
        id=uuid4(),
        manufacturer="Acme Materials",
        name="Warm Gray Boucle",
        material_family="textile",
        image_object_key="catalog/acme/warm-gray-boucle.jpg",
        image_url=None,
        metadata={},
        created_at=now,
        updated_at=now,
    )
