from typing import Annotated, Protocol
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.catalog.dependencies import get_catalog_repository
from app.catalog.repository import CatalogRepository
from app.model_services.embeddings import EmbeddingClient
from app.model_services.factory import (
    get_embedding_client,
    get_material_planner_client,
    get_sam3_client,
)
from app.model_services.planning import MaterialPlannerClient
from app.model_services.segmentation import Sam3Client
from app.search.artifacts import RegionArtifactStore, get_region_artifact_store
from app.search.dependencies import get_search_run_repository
from app.search.repository import SearchRunRepository
from app.search.schemas import (
    SearchRunAccepted,
    SearchRunStatusResponse,
    SegmentMatchRequest,
    SegmentMatchResponse,
    UploadImageResponse,
)
from app.search.service import SegmentCatalogMatchService
from app.search.uploads import UploadedImageStore, get_uploaded_image_store
from app.workers.search_runs import process_search_run

router = APIRouter(prefix="/search", tags=["search"])

MAX_UPLOAD_BYTES = 12 * 1024 * 1024


class SearchRunDispatcher(Protocol):
    def enqueue(self, request: SegmentMatchRequest) -> None:
        raise NotImplementedError


class DramatiqSearchRunDispatcher:
    def enqueue(self, request: SegmentMatchRequest) -> None:
        process_search_run.send(request.model_dump(mode="json"))


def get_search_run_dispatcher() -> SearchRunDispatcher:
    return DramatiqSearchRunDispatcher()


@router.post(
    "/uploads",
    response_model=UploadImageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_search_image(
    image: Annotated[UploadFile, File()],
    uploaded_image_store: Annotated[UploadedImageStore, Depends(get_uploaded_image_store)],
) -> UploadImageResponse:
    content = await image.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded image is empty")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Uploaded image must be 12 MB or smaller")

    try:
        uploaded = uploaded_image_store.upload_image(
            filename=image.filename or "reference",
            content=content,
            content_type=image.content_type,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Image storage upload failed: {exc}") from exc

    return UploadImageResponse(
        image_object_key=uploaded.object_key,
        content_type=uploaded.content_type,
        size_bytes=uploaded.size_bytes,
    )


@router.post(
    "/runs",
    response_model=SearchRunAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_search_run(
    request: SegmentMatchRequest,
    search_run_repository: Annotated[SearchRunRepository, Depends(get_search_run_repository)],
    dispatcher: Annotated[SearchRunDispatcher, Depends(get_search_run_dispatcher)],
) -> SearchRunAccepted:
    run = search_run_repository.create_run(request, status="queued")
    queued_request = request.model_copy(update={"run_id": run.id})
    try:
        dispatcher.enqueue(queued_request)
    except Exception as exc:
        search_run_repository.fail_run(run_id=run.id, error=f"Search enqueue failed: {exc}")
        raise HTTPException(status_code=503, detail="Search queue is unavailable") from exc
    return SearchRunAccepted(run_id=run.id, status=run.status)


@router.get("/runs/{run_id}", response_model=SearchRunStatusResponse)
def get_search_run_status(
    run_id: UUID,
    search_run_repository: Annotated[SearchRunRepository, Depends(get_search_run_repository)],
) -> SearchRunStatusResponse:
    run = search_run_repository.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Search run {run_id} was not found")
    result = search_run_repository.get_run_result(run_id) if run.status == "completed" else None
    return SearchRunStatusResponse(run=run, result=result)


@router.post("/segment-matches", response_model=SegmentMatchResponse)
def segment_catalog_matches(
    request: SegmentMatchRequest,
    repository: Annotated[CatalogRepository, Depends(get_catalog_repository)],
    artifact_store: Annotated[RegionArtifactStore, Depends(get_region_artifact_store)],
    planner_client: Annotated[MaterialPlannerClient, Depends(get_material_planner_client)],
    sam3_client: Annotated[Sam3Client, Depends(get_sam3_client)],
    embedding_client: Annotated[EmbeddingClient, Depends(get_embedding_client)],
    search_run_repository: Annotated[SearchRunRepository, Depends(get_search_run_repository)],
) -> SegmentMatchResponse:
    service = SegmentCatalogMatchService(
        sam3_client=sam3_client,
        planner_client=planner_client,
        artifact_store=artifact_store,
        embedding_client=embedding_client,
        catalog_repository=repository,
        search_run_repository=search_run_repository,
    )
    return service.segment_and_match(request)
