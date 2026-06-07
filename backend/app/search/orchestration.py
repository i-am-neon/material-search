import re
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import TypedDict, TypeVar
from urllib.parse import urlsplit, urlunsplit

import httpx
from langgraph.graph import END, StateGraph
from pydantic import BaseModel

from app.catalog.repository import CatalogRepository
from app.model_services.embeddings import EmbeddingClient, ImageEmbedding
from app.model_services.planning import MaterialPlannerClient
from app.model_services.segmentation import Sam3Client, SegmentationRegion, SegmentationResult
from app.search.artifacts import RegionArtifact, RegionArtifactStore
from app.search.matching import RegionMatcher
from app.search.repository import SearchRunRepository
from app.search.schemas import (
    MaterialSearchPlan,
    PlannedMaterialTarget,
    RegionMatchRequest,
    SegmentMatchRequest,
    SegmentMatchResponse,
    SegmentRegionMatchSet,
    StoredSegment,
    build_result_region_id,
)

_MAX_SEGMENTATION_WORKERS = 5
_MAX_REGION_MATCH_WORKERS = 8

_T = TypeVar("_T")
_R = TypeVar("_R")


class PlannedSegmentation(BaseModel):
    target: PlannedMaterialTarget
    segmentation: SegmentationResult


@dataclass(frozen=True)
class SegmentationWork:
    target: PlannedMaterialTarget
    max_regions: int


@dataclass(frozen=True)
class RegionMatchWork:
    target: PlannedMaterialTarget
    segmentation: SegmentationResult
    region: SegmentationRegion
    result_region_id: str


@dataclass(frozen=True)
class PreparedRegionMatch:
    work: RegionMatchWork
    artifact: RegionArtifact
    embedding: ImageEmbedding | None


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
                self.search_run_repository.fail_run(
                    run_id=request.run_id,
                    error=_safe_error_message(str(exc)),
                )
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

        work_items: list[SegmentationWork] = []
        remaining_region_budget = request.max_regions
        for target in sorted(plan.targets, key=lambda item: item.priority):
            if remaining_region_budget <= 0:
                break
            target_max_regions = min(target.max_regions, remaining_region_budget)
            work_items.append(SegmentationWork(target=target, max_regions=target_max_regions))
            remaining_region_budget -= target_max_regions

        segmentations = _run_ordered_in_parallel(
            work_items,
            lambda work: PlannedSegmentation(
                target=work.target,
                segmentation=self.sam3_client.segment_image(
                    prompt=work.target.sam3_prompt,
                    image_object_key=request.image_object_key,
                    image_url=str(request.image_url) if request.image_url else None,
                    confidence_threshold=request.confidence_threshold,
                    max_regions=work.max_regions,
                    include_masks=request.include_masks,
                ),
            ),
            max_workers=_MAX_SEGMENTATION_WORKERS,
        )

        image_width: int | None = None
        image_height: int | None = None
        for planned in segmentations:
            image_width = image_width or planned.segmentation.image_width
            image_height = image_height or planned.segmentation.image_height

        if image_width is None or image_height is None:
            raise RuntimeError("Material search plan did not produce any segmentation requests")

        if self.search_run_repository is not None:
            stored_segments = [
                StoredSegment(
                    result_region_id=build_result_region_id(
                        target_id=planned.target.target_id,
                        source_region_id=region.id,
                    ),
                    target_id=planned.target.target_id,
                    source_region_id=region.id,
                    label=planned.target.label,
                    box_xyxy=list(region.box_xyxy),
                    score=region.score,
                )
                for planned in segmentations
                for region in planned.segmentation.regions
            ]
            self.search_run_repository.store_segments(
                run_id=request.run_id,
                segments=stored_segments,
                image_width=image_width,
                image_height=image_height,
            )

        return {
            "segmentations": segmentations,
            "image_width": image_width,
            "image_height": image_height,
        }

    def _prepare_region_match(
        self, *, request: SegmentMatchRequest, work: RegionMatchWork
    ) -> PreparedRegionMatch:
        artifact_region = work.region.model_copy(update={"id": work.result_region_id})
        artifact = self.artifact_store.create_region_crop(
            run_id=str(request.run_id),
            source_image_object_key=request.image_object_key,
            source_image_url=str(request.image_url) if request.image_url else None,
            region=artifact_region,
            image_width=work.segmentation.image_width,
            image_height=work.segmentation.image_height,
        )
        try:
            embedding = self.region_matcher.embed_region(
                RegionMatchRequest(
                    region_id=work.result_region_id,
                    crop_object_key=artifact.object_key,
                    crop_url=artifact.signed_url,
                    material_filter_hint=_material_filter_hint(work.target),
                    model_id=request.model_id,
                    dimensions=request.dimensions,
                    limit=request.matches_per_region,
                    min_similarity=request.min_similarity,
                )
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 429:
                raise
            embedding = None
        return PreparedRegionMatch(work=work, artifact=artifact, embedding=embedding)

    def _match_prepared_region(
        self, *, request: SegmentMatchRequest, prepared: PreparedRegionMatch
    ) -> SegmentRegionMatchSet:
        work = prepared.work
        target = work.target
        region = work.region
        artifact = prepared.artifact
        match_request = RegionMatchRequest(
            region_id=work.result_region_id,
            crop_object_key=artifact.object_key,
            crop_url=artifact.signed_url,
            material_filter_hint=_material_filter_hint(target),
            model_id=request.model_id,
            dimensions=request.dimensions,
            limit=request.matches_per_region,
            min_similarity=request.min_similarity,
        )
        if prepared.embedding is None:
            match_set = self.region_matcher.match_fallback(match_request)
        else:
            match_set = self.region_matcher.match_embedding(match_request, prepared.embedding)
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

        return SegmentRegionMatchSet(
            result_region_id=work.result_region_id,
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

    def _match_regions(self, state: SearchGraphState) -> SearchGraphState:
        request = state["request"]
        segmentations = state["segmentations"]

        work_items: list[RegionMatchWork] = []
        for planned in segmentations:
            target = planned.target
            segmentation = planned.segmentation
            for region in segmentation.regions:
                result_region_id = build_result_region_id(
                    target_id=target.target_id,
                    source_region_id=region.id,
                )
                work_items.append(
                    RegionMatchWork(
                        target=target,
                        segmentation=segmentation,
                        region=region,
                        result_region_id=result_region_id,
                    )
                )

        prepared_matches = _run_ordered_in_parallel(
            work_items,
            lambda work: self._prepare_region_match(request=request, work=work),
            max_workers=_MAX_REGION_MATCH_WORKERS,
        )

        return {
            "regions": [
                self._match_prepared_region(request=request, prepared=prepared)
                for prepared in prepared_matches
            ]
        }

    def _complete_run(self, state: SearchGraphState) -> SearchGraphState:
        request = state["request"]
        if self.search_run_repository is not None:
            self.search_run_repository.complete_run(
                run_id=request.run_id,
                image_width=state["image_width"],
                image_height=state["image_height"],
            )
        return {}


def _safe_error_message(message: str) -> str:
    return re.sub(r"https?://[^\s'\"<>]+", _redact_url_match, message)


def _redact_url_match(match: re.Match[str]) -> str:
    url = match.group(0)
    try:
        parsed = urlsplit(url)
    except ValueError:
        return url
    if not parsed.query:
        return url
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", parsed.fragment))


def _material_filter_hint(target: PlannedMaterialTarget) -> str:
    return " ".join(
        value
        for value in (target.material_family_hint, target.label, target.sam3_prompt)
        if value
    )


def _run_ordered_in_parallel(
    items: list[_T], fn: Callable[[_T], _R], *, max_workers: int
) -> list[_R]:
    if len(items) <= 1:
        return [fn(item) for item in items]

    with ThreadPoolExecutor(max_workers=min(len(items), max_workers)) as executor:
        futures = [executor.submit(fn, item) for item in items]
        return [future.result() for future in futures]
