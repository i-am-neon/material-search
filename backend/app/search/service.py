from uuid import UUID, uuid4

from app.catalog.repository import CatalogRepository
from app.model_services.embeddings import EmbeddingClient
from app.model_services.segmentation import Sam3Client
from app.search.artifacts import RegionArtifactStore
from app.search.matching import RegionMatcher
from app.search.repository import SearchRunRepository
from app.search.schemas import (
    RegionMatchRequest,
    SegmentMatchRequest,
    SegmentMatchResponse,
    SegmentRegionMatchSet,
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
        self.region_matcher = RegionMatcher(catalog_repository, embedding_client)
        self.search_run_repository = search_run_repository

    def segment_and_match(self, request: SegmentMatchRequest) -> SegmentMatchResponse:
        run_id = self._create_run(request)
        try:
            segmentation = self.sam3_client.segment_image(
                prompt=request.prompt,
                image_object_key=request.image_object_key,
                image_url=str(request.image_url) if request.image_url else None,
                confidence_threshold=request.confidence_threshold,
                max_regions=request.max_regions,
                include_masks=request.include_masks,
            )

            region_results: list[SegmentRegionMatchSet] = []
            for region in segmentation.regions:
                artifact = self.artifact_store.create_region_crop(
                    run_id=str(run_id),
                    source_image_object_key=request.image_object_key,
                    source_image_url=str(request.image_url) if request.image_url else None,
                    region=region,
                    image_width=segmentation.image_width,
                    image_height=segmentation.image_height,
                )
                match_set = self.region_matcher.match_region(
                    RegionMatchRequest(
                        region_id=region.id,
                        crop_object_key=artifact.object_key,
                        crop_url=artifact.signed_url,
                        model_id=request.model_id,
                        dimensions=request.dimensions,
                        limit=request.matches_per_region,
                        min_similarity=request.min_similarity,
                    )
                )
                persisted_region = None
                if self.search_run_repository is not None:
                    persisted_region = self.search_run_repository.create_region(
                        run_id=run_id,
                        region=region,
                        artifact=artifact,
                        embedding_model_id=match_set.model_id,
                        embedding_dimensions=match_set.dimensions,
                    )
                    self.search_run_repository.replace_region_matches(
                        run_id=run_id,
                        region_id=persisted_region.id,
                        matches=match_set.matches,
                    )
                region_results.append(
                    SegmentRegionMatchSet(
                        region=region,
                        crop_object_key=artifact.object_key,
                        crop_url=artifact.signed_url,
                        crop_width=artifact.width,
                        crop_height=artifact.height,
                        model_id=match_set.model_id,
                        dimensions=match_set.dimensions,
                        matches=match_set.matches,
                    )
                )

            if self.search_run_repository is not None:
                self.search_run_repository.complete_run(
                    run_id=run_id,
                    image_width=segmentation.image_width,
                    image_height=segmentation.image_height,
                )

            return SegmentMatchResponse(
                run_id=run_id,
                prompt=segmentation.prompt,
                image_width=segmentation.image_width,
                image_height=segmentation.image_height,
                regions=region_results,
            )
        except Exception as exc:
            if self.search_run_repository is not None:
                self.search_run_repository.fail_run(run_id=run_id, error=str(exc))
            raise

    def _create_run(self, request: SegmentMatchRequest) -> UUID:
        if self.search_run_repository is None:
            return request.run_id or uuid4()
        return self.search_run_repository.create_run(request).id
