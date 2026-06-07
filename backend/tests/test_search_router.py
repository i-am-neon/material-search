from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.catalog.dependencies import get_catalog_repository
from app.catalog.schemas import CatalogItem, CatalogMatch
from app.main import create_app
from app.model_services.embeddings import ImageEmbedding
from app.model_services.factory import (
    get_embedding_client,
    get_material_planner_client,
    get_sam3_client,
)
from app.model_services.segmentation import SegmentationRegion, SegmentationResult
from app.search.artifacts import RegionArtifact, get_region_artifact_store
from app.search.dependencies import get_search_run_repository
from app.search.router import get_search_run_dispatcher
from app.search.schemas import (
    MaterialSearchMatchRecord,
    MaterialSearchPlan,
    MaterialSearchRegionRecord,
    MaterialSearchRun,
    PlannedMaterialTarget,
    SegmentMatchRequest,
    SegmentMatchResponse,
    SegmentRegionMatchSet,
)
from app.search.uploads import UploadedImage, get_uploaded_image_store


class FakeSam3Client:
    def segment_image(self, **kwargs) -> SegmentationResult:
        return SegmentationResult(
            model_id="facebook/sam3",
            image_width=320,
            image_height=240,
            prompt=kwargs["prompt"],
            regions=[
                SegmentationRegion(
                    id="sam3_region_0",
                    prompt=kwargs["prompt"],
                    score=0.93,
                    box_xyxy=[1.0, 2.0, 101.0, 122.0],
                )
            ],
        )


class FakeArtifactStore:
    def create_region_crop(self, **kwargs) -> RegionArtifact:
        region = kwargs["region"]
        return RegionArtifact(
            object_key=f"runs/{kwargs['run_id']}/regions/{region.id}/crop.jpg",
            signed_url=f"https://example.com/signed/{region.id}.jpg",
            width=100,
            height=120,
        )


class FakePlannerClient:
    def plan_material_search(self, request: SegmentMatchRequest) -> MaterialSearchPlan:
        return MaterialSearchPlan(
            user_intent_summary="Search for upholstery",
            avoid=[],
            targets=[
                PlannedMaterialTarget(
                    target_id="upholstery",
                    label="Upholstery",
                    sam3_prompt=request.prompt,
                    material_family_hint="textile",
                    reason="The user asked for upholstery.",
                    priority=1,
                    max_regions=2,
                )
            ],
        )


class FakeEmbeddingClient:
    def embed_image(
        self, *, image_object_key: str, image_url: str | None, model_id: str, dimensions: int
    ) -> ImageEmbedding:
        return ImageEmbedding(
            model_id=model_id,
            dimensions=dimensions,
            embedding=[0.1] * dimensions,
        )


class FakeCatalogRepository:
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
        return [CatalogMatch(item=make_item(), model_id=model_id, similarity=0.9)]


class FakeSearchRunRepository:
    def __init__(self):
        self.run: MaterialSearchRun | None = None
        self.queued_request: SegmentMatchRequest | None = None
        self.result: SegmentMatchResponse | None = None

    def create_run(
        self, request: SegmentMatchRequest, *, status: str = "running"
    ) -> MaterialSearchRun:
        now = datetime.now(UTC)
        self.queued_request = request
        self.run = MaterialSearchRun(
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
        return self.run

    def get_run(self, run_id: UUID) -> MaterialSearchRun | None:
        return self.run if self.run and self.run.id == run_id else None

    def mark_run_running(self, run_id: UUID) -> MaterialSearchRun:
        if self.run is None:
            raise ValueError(f"Run {run_id} does not exist")
        self.run = self.run.model_copy(update={"status": "running", "error": None})
        return self.run

    def clear_run_outputs(self, run_id: UUID) -> None:
        return None

    def replace_planned_targets(self, *, run_id: UUID, plan: MaterialSearchPlan) -> None:
        return None

    def store_segments(
        self, *, run_id: UUID, segments, image_width: int, image_height: int
    ) -> None:
        return None

    def get_run_progress(self, run_id: UUID):
        return None

    def complete_run(
        self, *, run_id: UUID, image_width: int, image_height: int
    ) -> MaterialSearchRun:
        now = datetime.now(UTC)
        self.run = MaterialSearchRun(
            id=run_id,
            prompt="upholstery",
            source_image_object_key=None,
            source_image_url="https://example.com/room.jpg",
            status="completed",
            error=None,
            image_width=image_width,
            image_height=image_height,
            created_at=now,
            updated_at=now,
        )
        return self.run

    def fail_run(self, *, run_id: UUID, error: str) -> MaterialSearchRun:
        now = datetime.now(UTC)
        self.run = MaterialSearchRun(
            id=run_id,
            prompt="upholstery",
            source_image_object_key=None,
            source_image_url="https://example.com/room.jpg",
            status="failed",
            error=error,
            image_width=None,
            image_height=None,
            created_at=now,
            updated_at=now,
        )
        return self.run

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
        now = datetime.now(UTC)
        return MaterialSearchRegionRecord(
            id=uuid4(),
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

    def get_run_result(self, run_id: UUID) -> SegmentMatchResponse | None:
        return self.result if self.result and self.result.run_id == run_id else None


class FakeSearchRunDispatcher:
    def __init__(self):
        self.requests: list[SegmentMatchRequest] = []

    def enqueue(self, request: SegmentMatchRequest) -> None:
        self.requests.append(request)


class FakeUploadedImageStore:
    def __init__(self):
        self.calls: list[dict] = []

    def upload_image(
        self, *, filename: str, content: bytes, content_type: str | None
    ) -> UploadedImage:
        self.calls.append(
            {
                "filename": filename,
                "content": content,
                "content_type": content_type,
            }
        )
        return UploadedImage(
            object_key="uploads/run/reference.jpg",
            content_type=content_type or "image/jpeg",
            size_bytes=len(content),
        )


def test_segment_matches_endpoint_returns_region_catalog_matches():
    app = create_app()
    app.dependency_overrides[get_catalog_repository] = lambda: FakeCatalogRepository()
    app.dependency_overrides[get_region_artifact_store] = lambda: FakeArtifactStore()
    app.dependency_overrides[get_material_planner_client] = lambda: FakePlannerClient()
    app.dependency_overrides[get_sam3_client] = lambda: FakeSam3Client()
    app.dependency_overrides[get_embedding_client] = lambda: FakeEmbeddingClient()
    app.dependency_overrides[get_search_run_repository] = lambda: FakeSearchRunRepository()
    run_id = uuid4()

    response = TestClient(app).post(
        "/search/segment-matches",
        json={
            "run_id": str(run_id),
            "image_url": "https://example.com/room.jpg",
            "prompt": "upholstery",
            "model_id": "test-model",
            "dimensions": 3,
            "matches_per_region": 1,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["run_id"] == str(run_id)
    assert payload["regions"][0]["result_region_id"] == "upholstery__sam3_region_0"
    assert payload["regions"][0]["region"]["id"] == "sam3_region_0"
    assert payload["regions"][0]["target_id"] == "upholstery"
    assert (
        payload["regions"][0]["crop_object_key"]
        == f"runs/{run_id}/regions/upholstery__sam3_region_0/crop.jpg"
    )
    assert payload["regions"][0]["matches"][0]["rank"] == 1
    assert payload["regions"][0]["matches"][0]["match"]["item"]["name"] == "Warm Gray Boucle"


def test_create_search_run_persists_and_enqueues_run():
    app = create_app()
    repository = FakeSearchRunRepository()
    dispatcher = FakeSearchRunDispatcher()
    app.dependency_overrides[get_search_run_repository] = lambda: repository
    app.dependency_overrides[get_search_run_dispatcher] = lambda: dispatcher

    response = TestClient(app).post(
        "/search/runs",
        json={
            "image_url": "https://example.com/room.jpg",
            "prompt": "upholstery",
            "model_id": "test-model",
            "dimensions": 3,
        },
    )

    assert response.status_code == 202
    payload = response.json()
    assert payload["status"] == "queued"
    assert repository.run is not None
    assert payload["run_id"] == str(repository.run.id)
    assert len(dispatcher.requests) == 1
    assert dispatcher.requests[0].run_id == repository.run.id
    assert dispatcher.requests[0].prompt == "upholstery"


def test_get_search_run_status_returns_completed_result():
    app = create_app()
    repository = FakeSearchRunRepository()
    run = repository.create_run(
        SegmentMatchRequest(
            image_url="https://example.com/room.jpg",
            prompt="upholstery",
            model_id="test-model",
            dimensions=3,
        ),
        status="completed",
    )
    repository.run = run.model_copy(update={"image_width": 320, "image_height": 240})
    repository.result = SegmentMatchResponse(
        run_id=run.id,
        prompt="upholstery",
        image_width=320,
        image_height=240,
        regions=[
            SegmentRegionMatchSet(
                result_region_id="upholstery__sam3_region_0",
                region=SegmentationRegion(
                    id="sam3_region_0",
                    prompt="upholstery",
                    score=0.93,
                    box_xyxy=[1.0, 2.0, 101.0, 122.0],
                ),
                crop_object_key="runs/run/regions/sam3_region_0/crop.jpg",
                crop_url=None,
                crop_width=100,
                crop_height=120,
                model_id="test-model",
                dimensions=3,
                matches=[],
            )
        ],
    )
    app.dependency_overrides[get_search_run_repository] = lambda: repository

    response = TestClient(app).get(f"/search/runs/{run.id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["run"]["status"] == "completed"
    assert payload["result"]["run_id"] == str(run.id)
    assert payload["result"]["regions"][0]["region"]["id"] == "sam3_region_0"


def test_upload_search_image_returns_uploaded_object_key():
    app = create_app()
    store = FakeUploadedImageStore()
    app.dependency_overrides[get_uploaded_image_store] = lambda: store

    response = TestClient(app).post(
        "/search/uploads",
        files={"image": ("room.jpg", b"image-bytes", "image/jpeg")},
    )

    assert response.status_code == 201
    assert response.json() == {
        "image_object_key": "uploads/run/reference.jpg",
        "content_type": "image/jpeg",
        "size_bytes": 11,
    }
    assert store.calls == [
        {
            "filename": "room.jpg",
            "content": b"image-bytes",
            "content_type": "image/jpeg",
        }
    ]


def test_upload_search_image_rejects_empty_upload():
    app = create_app()
    app.dependency_overrides[get_uploaded_image_store] = lambda: FakeUploadedImageStore()

    response = TestClient(app).post(
        "/search/uploads",
        files={"image": ("room.jpg", b"", "image/jpeg")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Uploaded image is empty"


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
