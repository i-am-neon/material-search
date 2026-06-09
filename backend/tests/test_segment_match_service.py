from datetime import UTC, datetime
from threading import Barrier, Lock
from uuid import UUID, uuid4

import httpx
import pytest

from app.catalog.schemas import CatalogItem, CatalogMatch
from app.model_services.embeddings import ImageEmbedding
from app.model_services.planning import SegmentationPromptRepair
from app.model_services.segmentation import SegmentationRegion, SegmentationResult
from app.search.artifacts import RegionArtifact
from app.search.schemas import (
    MaterialSearchMatchRecord,
    MaterialSearchPlan,
    MaterialSearchRegionRecord,
    MaterialSearchRun,
    PlannedMaterialTarget,
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


class FakePlannerClient:
    def __init__(self):
        self.calls: list[SegmentMatchRequest] = []

    def plan_material_search(self, request: SegmentMatchRequest) -> MaterialSearchPlan:
        self.calls.append(request)
        return MaterialSearchPlan(
            user_intent_summary="Search for upholstery",
            avoid=[],
            targets=[
                PlannedMaterialTarget(
                    target_id="upholstery",
                    label="Upholstery",
                    sam3_prompt="upholstery",
                    material_family_hint="textile",
                    reason="The user asked for upholstery.",
                    priority=1,
                    max_regions=2,
                )
            ],
        )


class RepairingPlannerClient:
    def __init__(self):
        self.repair_calls: list[dict] = []

    def plan_material_search(self, request: SegmentMatchRequest) -> MaterialSearchPlan:
        return MaterialSearchPlan(
            user_intent_summary="Search for green shower tile",
            avoid=[],
            targets=[
                PlannedMaterialTarget(
                    target_id="green_shower_tile",
                    label="Green Shower Tile",
                    sam3_prompt="green square tile",
                    material_family_hint="tile",
                    reason="The user asked for the green shower tile.",
                    priority=1,
                    max_regions=1,
                )
            ],
        )

    def repair_segmentation_prompts(
        self,
        *,
        request: SegmentMatchRequest,
        target: PlannedMaterialTarget,
        failed_prompt: str,
        max_alternates: int = 3,
    ):
        self.repair_calls.append(
            {
                "prompt": request.prompt,
                "target_id": target.target_id,
                "failed_prompt": failed_prompt,
                "max_alternates": max_alternates,
            }
        )
        return SegmentationPromptRepair(
            target_id=target.target_id,
            failed_prompt=failed_prompt,
            alternate_prompts=["dark green tiled shower wall", "green ceramic tile wall"],
            reason="Target the larger tiled wall surface instead of one tile.",
        )


class MultiTargetPlannerClient:
    def plan_material_search(self, request: SegmentMatchRequest) -> MaterialSearchPlan:
        return MaterialSearchPlan(
            user_intent_summary="Search for upholstery and floor",
            avoid=[],
            targets=[
                PlannedMaterialTarget(
                    target_id="upholstery",
                    label="Upholstery",
                    sam3_prompt="upholstery",
                    material_family_hint="textile",
                    reason="The user asked for upholstery.",
                    priority=1,
                    max_regions=1,
                ),
                PlannedMaterialTarget(
                    target_id="floor",
                    label="Floor",
                    sam3_prompt="stone floor",
                    material_family_hint="stone",
                    reason="The user asked for flooring.",
                    priority=2,
                    max_regions=1,
                ),
            ],
        )


class UnsupportedIntentPlannerClient:
    def plan_material_search(self, request: SegmentMatchRequest) -> MaterialSearchPlan:
        return MaterialSearchPlan(
            user_intent_summary="The request is not material matching.",
            is_material_search=False,
            unsupported_reason="Lamp shape matching is not a material search.",
            avoid=[],
            targets=[],
        )


class FailingSam3Client:
    def segment_image(self, **kwargs):
        raise RuntimeError("SAM3 unavailable")


class ZeroThenRepairSam3Client:
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
        regions = []
        if prompt == "dark green tiled shower wall":
            regions = [
                SegmentationRegion(
                    id="sam3_region_0",
                    prompt=prompt,
                    score=0.93,
                    box_xyxy=[120.0, 90.0, 370.0, 470.0],
                )
            ]
        return SegmentationResult(
            model_id="facebook/sam3",
            image_width=640,
            image_height=480,
            prompt=prompt,
            regions=regions,
        )


class BarrierSam3Client:
    def __init__(self, expected_calls: int):
        self.barrier = Barrier(expected_calls, timeout=1.0)
        self.calls: list[dict] = []
        self.lock = Lock()

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
        with self.lock:
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
        self.barrier.wait()
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


class MultiRegionSam3Client:
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
        return SegmentationResult(
            model_id="facebook/sam3",
            image_width=640,
            image_height=480,
            prompt=prompt,
            regions=[
                SegmentationRegion(
                    id=f"sam3_region_{index}",
                    prompt=prompt,
                    score=0.91,
                    box_xyxy=[10.0 + index, 20.0, 110.0 + index, 120.0],
                )
                for index in range(min(2, max_regions))
            ],
        )


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


class RateLimitedEmbeddingClient(FakeEmbeddingClient):
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
        request = httpx.Request("POST", "https://embedding.example.com/embed-image")
        response = httpx.Response(429, request=request, text="rate limit reached")
        raise httpx.HTTPStatusError(
            "Client error '429 Too Many Requests'",
            request=request,
            response=response,
        )


class BarrierEmbeddingClient(FakeEmbeddingClient):
    def __init__(self, expected_calls: int):
        super().__init__()
        self.barrier = Barrier(expected_calls, timeout=1.0)
        self.lock = Lock()

    def embed_image(
        self, *, image_object_key: str, image_url: str | None, model_id: str, dimensions: int
    ) -> ImageEmbedding:
        with self.lock:
            self.calls.append(
                {
                    "image_object_key": image_object_key,
                    "image_url": image_url,
                    "model_id": model_id,
                    "dimensions": dimensions,
                }
            )
        self.barrier.wait()
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
        self.replace_planned_targets_calls: list[dict] = []
        self.store_segments_calls: list[dict] = []
        self.region_id = uuid4()

    def create_run(
        self, request: SegmentMatchRequest, *, status: str = "running"
    ) -> MaterialSearchRun:
        self.create_run_calls.append(request)
        now = datetime.now(UTC)
        return MaterialSearchRun(
            id=request.run_id or uuid4(),
            prompt=request.prompt,
            source_image_object_key=request.image_object_key,
            source_image_url=request.image_url,
            status=status,
            error=None,
            image_width=None,
            image_height=None,
            created_at=now,
            updated_at=now,
        )

    def get_run(self, run_id: UUID) -> MaterialSearchRun | None:
        raise NotImplementedError

    def mark_run_running(self, run_id: UUID) -> MaterialSearchRun:
        now = datetime.now(UTC)
        return MaterialSearchRun(
            id=run_id,
            prompt="upholstery",
            source_image_object_key="uploads/room.jpg",
            source_image_url=None,
            status="running",
            error=None,
            image_width=None,
            image_height=None,
            created_at=now,
            updated_at=now,
        )

    def clear_run_outputs(self, run_id: UUID) -> None:
        return None

    def replace_planned_targets(self, *, run_id: UUID, plan: MaterialSearchPlan) -> None:
        self.replace_planned_targets_calls.append(
            {
                "run_id": run_id,
                "target_ids": [target.target_id for target in plan.targets],
                "avoid": plan.avoid,
            }
        )

    def store_segments(
        self, *, run_id: UUID, segments, image_width: int, image_height: int
    ) -> None:
        self.store_segments_calls.append(
            {
                "run_id": run_id,
                "result_region_ids": [segment.result_region_id for segment in segments],
                "image_width": image_width,
                "image_height": image_height,
            }
        )

    def get_run_progress(self, run_id: UUID):
        return None

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
        target: PlannedMaterialTarget | None,
        region: SegmentationRegion,
        artifact: RegionArtifact,
        embedding_model_id: str,
        embedding_dimensions: int,
    ) -> MaterialSearchRegionRecord:
        self.create_region_calls.append(
            {
                "run_id": run_id,
                "target_id": target.target_id if target else None,
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
            target_id=target.target_id if target else None,
            target_label=target.label if target else None,
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

    def get_run_result(self, run_id: UUID):
        raise NotImplementedError


def test_segment_catalog_match_service_crops_embeds_and_matches_regions():
    sam3_client = FakeSam3Client()
    artifact_store = FakeArtifactStore()
    embedding_client = FakeEmbeddingClient()
    repository = FakeCatalogRepository()
    search_repository = FakeSearchRunRepository()
    run_id = uuid4()

    response = SegmentCatalogMatchService(
        sam3_client=sam3_client,
        planner_client=FakePlannerClient(),
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
    assert search_repository.replace_planned_targets_calls == [
        {"run_id": run_id, "target_ids": ["upholstery"], "avoid": []}
    ]
    assert artifact_store.calls == [
        {
            "run_id": str(run_id),
            "source_image_object_key": "uploads/room.jpg",
            "source_image_url": None,
            "region_id": "upholstery__sam3_region_0",
            "image_width": 640,
            "image_height": 480,
        }
    ]
    assert embedding_client.calls == [
        {
            "image_object_key": f"runs/{run_id}/regions/upholstery__sam3_region_0/crop.jpg",
            "image_url": "https://example.com/signed/upholstery__sam3_region_0.jpg",
            "model_id": "test-model",
            "dimensions": 3,
        }
    ]
    assert repository.search_calls[0]["limit"] == 8
    assert repository.search_calls[0]["min_similarity"] == 0.5
    assert search_repository.create_run_calls[0].run_id == run_id
    assert search_repository.create_region_calls == [
        {
            "run_id": run_id,
            "target_id": "upholstery",
            "source_region_id": "sam3_region_0",
            "artifact_object_key": f"runs/{run_id}/regions/upholstery__sam3_region_0/crop.jpg",
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
    assert response.plan is not None
    assert response.plan.targets[0].sam3_prompt == "upholstery"
    assert response.regions[0].result_region_id == "upholstery__sam3_region_0"
    assert response.regions[0].target_id == "upholstery"
    assert response.regions[0].region.id == "sam3_region_0"
    assert response.regions[0].crop_width == 100
    assert response.regions[0].matches[0].region_id == "upholstery__sam3_region_0"
    assert response.regions[0].matches[0].rank == 1
    assert response.regions[0].matches[0].match.item.name == "Warm Gray Boucle"


def test_segment_catalog_match_service_uses_target_scoped_region_ids_for_duplicate_sam3_ids():
    artifact_store = FakeArtifactStore()
    embedding_client = FakeEmbeddingClient()
    response = SegmentCatalogMatchService(
        sam3_client=FakeSam3Client(),
        planner_client=MultiTargetPlannerClient(),
        artifact_store=artifact_store,
        embedding_client=embedding_client,
        catalog_repository=FakeCatalogRepository(),
        search_run_repository=FakeSearchRunRepository(),
    ).segment_and_match(
        SegmentMatchRequest(
            run_id=uuid4(),
            image_object_key="uploads/room.jpg",
            prompt="upholstery and floor",
            max_regions=2,
            model_id="test-model",
            dimensions=3,
        )
    )

    assert [region.result_region_id for region in response.regions] == [
        "upholstery__sam3_region_0",
        "floor__sam3_region_0",
    ]
    assert sorted(call["region_id"] for call in artifact_store.calls) == [
        "floor__sam3_region_0",
        "upholstery__sam3_region_0",
    ]
    assert sorted(call["image_object_key"] for call in embedding_client.calls) == [
        f"runs/{response.run_id}/regions/floor__sam3_region_0/crop.jpg",
        f"runs/{response.run_id}/regions/upholstery__sam3_region_0/crop.jpg",
    ]
    assert [region.region.id for region in response.regions] == [
        "sam3_region_0",
        "sam3_region_0",
    ]


def test_segment_catalog_match_service_segments_planned_targets_concurrently():
    sam3_client = BarrierSam3Client(expected_calls=2)

    response = SegmentCatalogMatchService(
        sam3_client=sam3_client,
        planner_client=MultiTargetPlannerClient(),
        artifact_store=FakeArtifactStore(),
        embedding_client=FakeEmbeddingClient(),
        catalog_repository=FakeCatalogRepository(),
    ).segment_and_match(
        SegmentMatchRequest(
            run_id=uuid4(),
            image_object_key="uploads/room.jpg",
            prompt="upholstery and floor",
            max_regions=2,
            model_id="test-model",
            dimensions=3,
        )
    )

    assert sorted(call["prompt"] for call in sam3_client.calls) == [
        "stone floor",
        "upholstery",
    ]
    assert [region.result_region_id for region in response.regions] == [
        "upholstery__sam3_region_0",
        "floor__sam3_region_0",
    ]


def test_segment_catalog_match_service_prepares_region_matches_concurrently():
    embedding_client = BarrierEmbeddingClient(expected_calls=2)

    response = SegmentCatalogMatchService(
        sam3_client=MultiRegionSam3Client(),
        planner_client=FakePlannerClient(),
        artifact_store=FakeArtifactStore(),
        embedding_client=embedding_client,
        catalog_repository=FakeCatalogRepository(),
    ).segment_and_match(
        SegmentMatchRequest(
            run_id=uuid4(),
            image_object_key="uploads/room.jpg",
            prompt="upholstery",
            max_regions=2,
            model_id="test-model",
            dimensions=3,
        )
    )

    assert sorted(call["image_object_key"] for call in embedding_client.calls) == [
        f"runs/{response.run_id}/regions/upholstery__sam3_region_0/crop.jpg",
        f"runs/{response.run_id}/regions/upholstery__sam3_region_1/crop.jpg",
    ]
    assert [region.result_region_id for region in response.regions] == [
        "upholstery__sam3_region_0",
        "upholstery__sam3_region_1",
    ]


def test_segment_catalog_match_service_repairs_zero_region_sam3_prompt():
    sam3_client = ZeroThenRepairSam3Client()
    planner_client = RepairingPlannerClient()
    artifact_store = FakeArtifactStore()
    embedding_client = FakeEmbeddingClient()
    search_repository = FakeSearchRunRepository()
    run_id = uuid4()

    response = SegmentCatalogMatchService(
        sam3_client=sam3_client,
        planner_client=planner_client,
        artifact_store=artifact_store,
        embedding_client=embedding_client,
        catalog_repository=FakeCatalogRepository(),
        search_run_repository=search_repository,
    ).segment_and_match(
        SegmentMatchRequest(
            run_id=run_id,
            image_object_key="uploads/bathroom.png",
            prompt="Find the green shower tile.",
            max_regions=1,
            model_id="test-model",
            dimensions=3,
        )
    )

    assert [call["prompt"] for call in sam3_client.calls] == [
        "green square tile",
        "dark green tiled shower wall",
    ]
    assert planner_client.repair_calls == [
        {
            "prompt": "Find the green shower tile.",
            "target_id": "green_shower_tile",
            "failed_prompt": "green square tile",
            "max_alternates": 3,
        }
    ]
    assert [call["result_region_ids"] for call in search_repository.store_segments_calls] == [
        ["green_shower_tile__sam3_region_0"],
    ]
    assert response.regions[0].target_id == "green_shower_tile"
    assert response.regions[0].region.prompt == "dark green tiled shower wall"
    assert response.regions[0].region.score == 0.93
    assert artifact_store.calls[0]["region_id"] == "green_shower_tile__sam3_region_0"
    assert embedding_client.calls[0]["image_object_key"] == (
        f"runs/{run_id}/regions/green_shower_tile__sam3_region_0/crop.jpg"
    )


def test_segment_catalog_match_service_marks_run_failed_on_error():
    search_repository = FakeSearchRunRepository()
    run_id = uuid4()

    with pytest.raises(RuntimeError, match="SAM3 unavailable"):
        SegmentCatalogMatchService(
            sam3_client=FailingSam3Client(),
            planner_client=FakePlannerClient(),
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


def test_segment_catalog_match_service_fails_on_embedding_429_without_keyword_fallback():
    search_repository = FakeSearchRunRepository()
    repository = FakeCatalogRepository()
    embedding_client = RateLimitedEmbeddingClient()
    run_id = uuid4()

    with pytest.raises(httpx.HTTPStatusError, match="429 Too Many Requests"):
        SegmentCatalogMatchService(
            sam3_client=FakeSam3Client(),
            planner_client=FakePlannerClient(),
            artifact_store=FakeArtifactStore(),
            embedding_client=embedding_client,
            catalog_repository=repository,
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

    assert embedding_client.calls == [
        {
            "image_object_key": f"runs/{run_id}/regions/upholstery__sam3_region_0/crop.jpg",
            "image_url": "https://example.com/signed/upholstery__sam3_region_0.jpg",
            "model_id": "test-model",
            "dimensions": 3,
        }
    ]
    assert repository.search_calls == []
    assert search_repository.complete_run_calls == []
    assert len(search_repository.fail_run_calls) == 1
    assert search_repository.fail_run_calls[0]["run_id"] == run_id
    assert "429 Too Many Requests" in search_repository.fail_run_calls[0]["error"]


def test_segment_catalog_match_service_declines_unsupported_planner_intent():
    sam3_client = FakeSam3Client()
    search_repository = FakeSearchRunRepository()
    run_id = uuid4()

    with pytest.raises(RuntimeError, match="planner declined request"):
        SegmentCatalogMatchService(
            sam3_client=sam3_client,
            planner_client=UnsupportedIntentPlannerClient(),
            artifact_store=FakeArtifactStore(),
            embedding_client=FakeEmbeddingClient(),
            catalog_repository=FakeCatalogRepository(),
            search_run_repository=search_repository,
        ).segment_and_match(
            SegmentMatchRequest(
                run_id=run_id,
                image_object_key="uploads/room.jpg",
                prompt="Match the lamp shape.",
                model_id="test-model",
                dimensions=3,
            )
        )

    assert sam3_client.calls == []
    assert search_repository.complete_run_calls == []
    assert search_repository.fail_run_calls == [
        {
            "run_id": run_id,
            "error": (
                "Material search planner declined request: "
                "Lamp shape matching is not a material search."
            ),
        }
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
