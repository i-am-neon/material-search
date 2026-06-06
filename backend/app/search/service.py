from uuid import UUID, uuid4

from app.catalog.repository import CatalogRepository
from app.model_services.embeddings import EmbeddingClient
from app.model_services.segmentation import Sam3Client
from app.search.artifacts import RegionArtifactStore
from app.search.orchestration import MaterialSearchGraph
from app.search.repository import SearchRunRepository
from app.search.schemas import (
    SegmentMatchRequest,
    SegmentMatchResponse,
)


class SegmentCatalogMatchService:
    def __init__(
        self,
        *,
        sam3_client: Sam3Client,
        artifact_store: RegionArtifactStore,
        embedding_client: EmbeddingClient,
        catalog_repository: CatalogRepository,
        search_run_repository: SearchRunRepository | None = None,
    ):
        self.sam3_client = sam3_client
        self.artifact_store = artifact_store
        self.embedding_client = embedding_client
        self.catalog_repository = catalog_repository
        self.search_run_repository = search_run_repository

    def segment_and_match(self, request: SegmentMatchRequest) -> SegmentMatchResponse:
        run_id = self._create_run(request)
        return self.run_existing(request.model_copy(update={"run_id": run_id}))

    def run_existing(self, request: SegmentMatchRequest) -> SegmentMatchResponse:
        return MaterialSearchGraph(
            sam3_client=self.sam3_client,
            artifact_store=self.artifact_store,
            embedding_client=self.embedding_client,
            catalog_repository=self.catalog_repository,
            search_run_repository=self.search_run_repository,
        ).run(request)

    def _create_run(self, request: SegmentMatchRequest) -> UUID:
        if self.search_run_repository is None:
            return request.run_id or uuid4()
        return self.search_run_repository.create_run(request, status="running").id
