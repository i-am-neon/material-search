import dramatiq

from app.catalog.repository import PostgresCatalogRepository
from app.db import get_connection
from app.model_services.factory import get_embedding_client, get_sam3_client
from app.search.artifacts import get_region_artifact_store
from app.search.repository import PostgresSearchRunRepository
from app.search.schemas import SegmentMatchRequest
from app.search.service import SegmentCatalogMatchService
from app.workers import broker as _broker  # noqa: F401


@dramatiq.actor(queue_name="search-runs", max_retries=3)
def process_search_run(payload: dict) -> None:
    request = SegmentMatchRequest.model_validate(payload)
    run_search(request)


def run_search(request: SegmentMatchRequest) -> None:
    if request.run_id is None:
        raise ValueError("run_id is required to process a queued search run")

    with get_connection() as conn:
        catalog_repository = PostgresCatalogRepository(conn)
        search_run_repository = PostgresSearchRunRepository(conn)
        existing_run = search_run_repository.get_run(request.run_id)
        if existing_run is None:
            raise ValueError(f"Material search run {request.run_id} does not exist")
        if existing_run.status == "completed":
            return

        SegmentCatalogMatchService(
            sam3_client=get_sam3_client(),
            artifact_store=get_region_artifact_store(),
            embedding_client=get_embedding_client(),
            catalog_repository=catalog_repository,
            search_run_repository=search_run_repository,
        ).run_existing(request)
