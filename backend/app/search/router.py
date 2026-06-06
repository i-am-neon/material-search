from typing import Annotated

from fastapi import APIRouter, Depends

from app.catalog.dependencies import get_catalog_repository
from app.catalog.repository import CatalogRepository
from app.model_services.embeddings import EmbeddingClient
from app.model_services.factory import get_embedding_client, get_sam3_client
from app.model_services.segmentation import Sam3Client
from app.search.artifacts import RegionArtifactStore, get_region_artifact_store
from app.search.dependencies import get_search_run_repository
from app.search.repository import SearchRunRepository
from app.search.schemas import SegmentMatchRequest, SegmentMatchResponse
from app.search.service import SegmentCatalogMatchService

router = APIRouter(prefix="/search", tags=["search"])


@router.post("/segment-matches", response_model=SegmentMatchResponse)
def segment_catalog_matches(
    request: SegmentMatchRequest,
    repository: Annotated[CatalogRepository, Depends(get_catalog_repository)],
    artifact_store: Annotated[RegionArtifactStore, Depends(get_region_artifact_store)],
    sam3_client: Annotated[Sam3Client, Depends(get_sam3_client)],
    embedding_client: Annotated[EmbeddingClient, Depends(get_embedding_client)],
    search_run_repository: Annotated[SearchRunRepository, Depends(get_search_run_repository)],
) -> SegmentMatchResponse:
    service = SegmentCatalogMatchService(
        sam3_client=sam3_client,
        artifact_store=artifact_store,
        embedding_client=embedding_client,
        catalog_repository=repository,
        search_run_repository=search_run_repository,
    )
    return service.segment_and_match(request)
