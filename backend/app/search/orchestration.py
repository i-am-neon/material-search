from typing import TypedDict

from langgraph.graph import END, StateGraph
from pydantic import BaseModel

from app.catalog.repository import CatalogRepository
from app.model_services.embeddings import EmbeddingClient
from app.model_services.planning import MaterialPlannerClient
from app.model_services.segmentation import Sam3Client, SegmentationResult
from app.search.artifacts import RegionArtifactStore
from app.search.matching import RegionMatcher
from app.search.repository import SearchRunRepository
from app.search.schemas import (
    MaterialSearchPlan,
    PlannedMaterialTarget,
    RegionMatchRequest,
    SegmentMatchRequest,
    SegmentMatchResponse,
    SegmentRegionMatchSet,
    build_result_region_id,
)


class PlannedSegmentation(BaseModel):
    target: PlannedMaterialTarget
    segmentation: SegmentationResult


class SearchGraphState(TypedDict, total=False):
    request: SegmentMatchRequest
    plan: MaterialSearchPlan
    segmentations: list[PlannedSegmentation]
    image_width: int
    image_height: int
    regions: list[SegmentRegionMatchSet]


class MaterialSearchGraph:
    def __init__(
        self,
        *,
        sam3_client: Sam3Client,
        planner_client: MaterialPlannerClient,
        artifact_store: RegionArtifactStore,
        embedding_client: EmbeddingClient,
        catalog_repository: CatalogRepository,
        search_run_repository: SearchRunRepository | None = None,
    ):
        self.sam3_client = sam3_client
        self.planner_client = planner_client
        self.artifact_store = artifact_store
        self.region_matcher = RegionMatcher(catalog_repository, embedding_client)
        self.search_run_repository = search_run_repository
        self.graph = self._build_graph()

    def run(self, request: SegmentMatchRequest) -> SegmentMatchResponse:
        if request.run_id is None:
            raise ValueError("run_id is required to execute a material search graph")

        try:
            final_state = self.graph.invoke({"request": request})
        except Exception as exc:
            if self.search_run_repository is not None:
                self.search_run_repository.fail_run(run_id=request.run_id, error=str(exc))
            raise

        plan = final_state["plan"]
        regions = final_state["regions"]
        return SegmentMatchResponse(
            run_id=request.run_id,
            prompt=request.prompt,
            plan=plan,
            image_width=final_state["image_width"],
            image_height=final_state["image_height"],
            regions=regions,
        )

    def _build_graph(self):
        graph = StateGraph(SearchGraphState)
        graph.add_node("prepare_run", self._prepare_run)
        graph.add_node("plan_search", self._plan_search)
        graph.add_node("segment_targets", self._segment_targets)
        graph.add_node("match_regions", self._match_regions)
        graph.add_node("complete_run", self._complete_run)
        graph.set_entry_point("prepare_run")
        graph.add_edge("prepare_run", "plan_search")
        graph.add_edge("plan_search", "segment_targets")
        graph.add_edge("segment_targets", "match_regions")
        graph.add_edge("match_regions", "complete_run")
        graph.add_edge("complete_run", END)
        return graph.compile()

    def _prepare_run(self, state: SearchGraphState) -> SearchGraphState:
        request = state["request"]
        if self.search_run_repository is not None:
            self.search_run_repository.mark_run_running(request.run_id)
            self.search_run_repository.clear_run_outputs(request.run_id)
        return {}

    def _plan_search(self, state: SearchGraphState) -> SearchGraphState:
        request = state["request"]
        plan = self.planner_client.plan_material_search(request)
        if self.search_run_repository is not None:
            self.search_run_repository.replace_planned_targets(run_id=request.run_id, plan=plan)
        return {"plan": plan}

    def _segment_targets(self, state: SearchGraphState) -> SearchGraphState:
        request = state["request"]
        plan = state["plan"]

        if not plan.is_material_search:
            reason = plan.unsupported_reason or "The request is not a material search"
            raise RuntimeError(f"Material search planner declined request: {reason}")

        segmentations: list[PlannedSegmentation] = []
        remaining_regions = request.max_regions
        image_width: int | None = None
        image_height: int | None = None
        for target in sorted(plan.targets, key=lambda item: item.priority):
            if remaining_regions <= 0:
                break
            target_max_regions = min(target.max_regions, remaining_regions)
            segmentation = self.sam3_client.segment_image(
                prompt=target.sam3_prompt,
                image_object_key=request.image_object_key,
                image_url=str(request.image_url) if request.image_url else None,
                confidence_threshold=request.confidence_threshold,
                max_regions=target_max_regions,
                include_masks=request.include_masks,
            )
            image_width = image_width or segmentation.image_width
            image_height = image_height or segmentation.image_height
            segmentations.append(PlannedSegmentation(target=target, segmentation=segmentation))
            remaining_regions -= len(segmentation.regions)

        if image_width is None or image_height is None:
            raise RuntimeError("Material search plan did not produce any segmentation requests")

        return {
            "segmentations": segmentations,
            "image_width": image_width,
            "image_height": image_height,
        }

    def _match_regions(self, state: SearchGraphState) -> SearchGraphState:
        request = state["request"]
        segmentations = state["segmentations"]

        region_results: list[SegmentRegionMatchSet] = []
        for planned in segmentations:
            target = planned.target
            segmentation = planned.segmentation
            for region in segmentation.regions:
                result_region_id = build_result_region_id(
                    target_id=target.target_id,
                    source_region_id=region.id,
                )
                artifact_region = region.model_copy(update={"id": result_region_id})
                artifact = self.artifact_store.create_region_crop(
                    run_id=str(request.run_id),
                    source_image_object_key=request.image_object_key,
                    source_image_url=str(request.image_url) if request.image_url else None,
                    region=artifact_region,
                    image_width=segmentation.image_width,
                    image_height=segmentation.image_height,
                )
                match_set = self.region_matcher.match_region(
                    RegionMatchRequest(
                        region_id=result_region_id,
                        crop_object_key=artifact.object_key,
                        crop_url=artifact.signed_url,
                        model_id=request.model_id,
                        dimensions=request.dimensions,
                        limit=request.matches_per_region,
                        min_similarity=request.min_similarity,
                    )
                )
                if self.search_run_repository is not None:
                    persisted_region = self.search_run_repository.create_region(
                        run_id=request.run_id,
                        target=target,
                        region=region,
                        artifact=artifact,
                        embedding_model_id=match_set.model_id,
                        embedding_dimensions=match_set.dimensions,
                    )
                    self.search_run_repository.replace_region_matches(
                        run_id=request.run_id,
                        region_id=persisted_region.id,
                        matches=match_set.matches,
                    )

                region_results.append(
                    SegmentRegionMatchSet(
                        result_region_id=result_region_id,
                        region=region,
                        target_id=target.target_id,
                        target_label=target.label,
                        crop_object_key=artifact.object_key,
                        crop_url=artifact.signed_url,
                        crop_width=artifact.width,
                        crop_height=artifact.height,
                        model_id=match_set.model_id,
                        dimensions=match_set.dimensions,
                        matches=match_set.matches,
                    )
                )
        return {"regions": region_results}

    def _complete_run(self, state: SearchGraphState) -> SearchGraphState:
        request = state["request"]
        if self.search_run_repository is not None:
            self.search_run_repository.complete_run(
                run_id=request.run_id,
                image_width=state["image_width"],
                image_height=state["image_height"],
            )
        return {}
