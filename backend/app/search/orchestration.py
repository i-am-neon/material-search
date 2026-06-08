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
from app.core.observability import search_source_kind, span
from app.model_services.embeddings import EmbeddingClient, ImageEmbedding
from app.model_services.planning import MaterialPlannerClient, SegmentationPromptRepair
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
_MAX_SEGMENTATION_REPAIR_ROUNDS = 1
_MAX_REPAIR_ALTERNATE_PROMPTS = 3

_T = TypeVar("_T")
_R = TypeVar("_R")


class PlannedSegmentation(BaseModel):
    target: PlannedMaterialTarget
    segmentation: SegmentationResult
    max_regions: int


class PlannedSegmentationRepair(BaseModel):
    target: PlannedMaterialTarget
    failed_prompt: str
    alternate_prompts: list[str]
    reason: str


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
    segmentation_repairs: list[PlannedSegmentationRepair]
    segmentation_repair_round: int
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
            with span(
                "material_search.run",
                run_id=str(request.run_id),
                source_kind=search_source_kind(
                    image_object_key=request.image_object_key,
                    image_url=request.image_url,
                ),
                prompt_length=len(request.prompt),
                max_regions=request.max_regions,
                matches_per_region=request.matches_per_region,
                model_id=request.model_id,
                dimensions=request.dimensions,
            ) as active_span:
                final_state = self.graph.invoke({"request": request})
                active_span.set_attributes(
                    {
                        "image_width": final_state["image_width"],
                        "image_height": final_state["image_height"],
                        "region_count": len(final_state["regions"]),
                    }
                )
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
        graph.add_node("repair_segmentation_prompts", self._repair_segmentation_prompts)
        graph.add_node("retry_failed_targets", self._retry_failed_targets)
        graph.add_node("match_regions", self._match_regions)
        graph.add_node("complete_run", self._complete_run)
        graph.set_entry_point("prepare_run")
        graph.add_edge("prepare_run", "plan_search")
        graph.add_edge("plan_search", "segment_targets")
        graph.add_conditional_edges(
            "segment_targets",
            self._route_after_segmentation,
            {
                "repair_segmentation_prompts": "repair_segmentation_prompts",
                "match_regions": "match_regions",
            },
        )
        graph.add_edge("repair_segmentation_prompts", "retry_failed_targets")
        graph.add_conditional_edges(
            "retry_failed_targets",
            self._route_after_segmentation,
            {
                "repair_segmentation_prompts": "repair_segmentation_prompts",
                "match_regions": "match_regions",
            },
        )
        graph.add_edge("match_regions", "complete_run")
        graph.add_edge("complete_run", END)
        return graph.compile()

    def _prepare_run(self, state: SearchGraphState) -> SearchGraphState:
        request = state["request"]
        with span("material_search.prepare_run", run_id=str(request.run_id)):
            if self.search_run_repository is not None:
                self.search_run_repository.mark_run_running(request.run_id)
                self.search_run_repository.clear_run_outputs(request.run_id)
        return {}

    def _plan_search(self, state: SearchGraphState) -> SearchGraphState:
        request = state["request"]
        with span(
            "material_search.plan_search",
            run_id=str(request.run_id),
            prompt_length=len(request.prompt),
            max_regions=request.max_regions,
        ) as active_span:
            plan = self.planner_client.plan_material_search(request)
            active_span.set_attributes(
                {
                    "is_material_search": plan.is_material_search,
                    "target_count": len(plan.targets),
                    "target_ids": [target.target_id for target in plan.targets],
                    "target_labels": [target.label for target in plan.targets],
                    "avoid_count": len(plan.avoid),
                    "unsupported": not plan.is_material_search,
                }
            )
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

        with span(
            "material_search.segment_targets",
            run_id=str(request.run_id),
            target_count=len(work_items),
            region_budget=request.max_regions,
            confidence_threshold=request.confidence_threshold,
            include_masks=request.include_masks,
        ) as active_span:
            segmentations = _run_ordered_in_parallel(
                work_items,
                lambda work: self._segment_target(request=request, work=work),
                max_workers=_MAX_SEGMENTATION_WORKERS,
            )

            image_width: int | None = None
            image_height: int | None = None
            for planned in segmentations:
                image_width = image_width or planned.segmentation.image_width
                image_height = image_height or planned.segmentation.image_height

            if image_width is None or image_height is None:
                raise RuntimeError("Material search plan did not produce any segmentation requests")

            stored_segments = _stored_segments_from_segmentations(segmentations)
            active_span.set_attributes(
                {
                    "image_width": image_width,
                    "image_height": image_height,
                    "segment_count": len(stored_segments),
                }
            )
            should_store_initial_segments = (
                not _failed_segmentations(segmentations)
                or _MAX_SEGMENTATION_REPAIR_ROUNDS <= 0
            )
            if self.search_run_repository is not None and should_store_initial_segments:
                self.search_run_repository.store_segments(
                    run_id=request.run_id,
                    segments=stored_segments,
                    image_width=image_width,
                    image_height=image_height,
                )

        return {
            "segmentations": segmentations,
            "segmentation_repairs": [],
            "segmentation_repair_round": 0,
            "image_width": image_width,
            "image_height": image_height,
        }

    def _route_after_segmentation(self, state: SearchGraphState) -> str:
        repair_round = state.get("segmentation_repair_round", 0)
        if repair_round >= _MAX_SEGMENTATION_REPAIR_ROUNDS:
            return "match_regions"
        if _failed_segmentations(state.get("segmentations", [])):
            return "repair_segmentation_prompts"
        return "match_regions"

    def _repair_segmentation_prompts(self, state: SearchGraphState) -> SearchGraphState:
        request = state["request"]
        failed = _failed_segmentations(state["segmentations"])
        repair_round = state.get("segmentation_repair_round", 0) + 1

        with span(
            "material_search.repair_segmentation_prompts",
            run_id=str(request.run_id),
            failed_target_count=len(failed),
            repair_round=repair_round,
            max_alternates=_MAX_REPAIR_ALTERNATE_PROMPTS,
        ) as active_span:
            repairs = [
                self._repair_segmentation_prompt(
                    request=request,
                    planned=planned,
                    repair_round=repair_round,
                )
                for planned in failed
            ]
            active_span.set_attributes(
                {
                    "repair_count": len(repairs),
                    "target_ids": [repair.target.target_id for repair in repairs],
                    "alternate_prompt_count": sum(
                        len(repair.alternate_prompts) for repair in repairs
                    ),
                }
            )

        return {
            "segmentation_repairs": repairs,
            "segmentation_repair_round": repair_round,
        }

    def _repair_segmentation_prompt(
        self,
        *,
        request: SegmentMatchRequest,
        planned: PlannedSegmentation,
        repair_round: int,
    ) -> PlannedSegmentationRepair:
        target = planned.target
        failed_prompt = planned.segmentation.prompt
        repair_fn = getattr(self.planner_client, "repair_segmentation_prompts", None)
        if repair_fn is None:
            repair = SegmentationPromptRepair(
                target_id=target.target_id,
                failed_prompt=failed_prompt,
                alternate_prompts=[],
                reason="Prompt repair is not configured.",
            )
        else:
            repair = repair_fn(
                request=request,
                target=target,
                failed_prompt=failed_prompt,
                max_alternates=_MAX_REPAIR_ALTERNATE_PROMPTS,
            )
        with span(
            "material_search.repair_segmentation_prompt",
            run_id=str(request.run_id),
            target_id=target.target_id,
            target_label=target.label,
            repair_round=repair_round,
            failed_prompt=failed_prompt,
            alternate_prompts=repair.alternate_prompts,
            alternate_prompt_count=len(repair.alternate_prompts),
            repair_reason=repair.reason,
        ):
            return PlannedSegmentationRepair(
                target=target,
                failed_prompt=failed_prompt,
                alternate_prompts=repair.alternate_prompts,
                reason=repair.reason,
            )

    def _retry_failed_targets(self, state: SearchGraphState) -> SearchGraphState:
        request = state["request"]
        segmentations = state["segmentations"]
        repairs_by_target_id = {
            repair.target.target_id: repair for repair in state.get("segmentation_repairs", [])
        }
        failed = _failed_segmentations(segmentations)

        with span(
            "material_search.retry_failed_targets",
            run_id=str(request.run_id),
            failed_target_count=len(failed),
            repair_round=state.get("segmentation_repair_round", 0),
        ) as active_span:
            retried = [
                self._retry_failed_target(
                    request=request,
                    planned=planned,
                    repair=repairs_by_target_id.get(planned.target.target_id),
                )
                for planned in failed
            ]
            retried_by_target_id = {planned.target.target_id: planned for planned in retried}
            updated = [
                retried_by_target_id.get(planned.target.target_id, planned)
                for planned in segmentations
            ]
            active_span.set_attributes(
                {
                    "retried_target_count": len(retried),
                    "recovered_target_count": sum(
                        1 for planned in retried if planned.segmentation.regions
                    ),
                    "remaining_failed_target_count": len(_failed_segmentations(updated)),
                }
            )
            if self.search_run_repository is not None:
                self.search_run_repository.store_segments(
                    run_id=request.run_id,
                    segments=_stored_segments_from_segmentations(updated),
                    image_width=state["image_width"],
                    image_height=state["image_height"],
                )

        return {"segmentations": updated}

    def _retry_failed_target(
        self,
        *,
        request: SegmentMatchRequest,
        planned: PlannedSegmentation,
        repair: PlannedSegmentationRepair | None,
    ) -> PlannedSegmentation:
        if repair is None or not repair.alternate_prompts:
            return planned

        target = planned.target
        max_regions = max(1, planned.max_regions)
        with span(
            "material_search.retry_failed_target",
            run_id=str(request.run_id),
            target_id=target.target_id,
            target_label=target.label,
            failed_prompt=repair.failed_prompt,
            alternate_prompts=repair.alternate_prompts,
            alternate_prompt_count=len(repair.alternate_prompts),
        ) as active_span:
            last_segmentation = planned.segmentation
            for attempt_index, prompt in enumerate(repair.alternate_prompts, start=1):
                retry_target = target.model_copy(update={"sam3_prompt": prompt})
                retry = self._segment_target(
                    request=request,
                    work=SegmentationWork(target=retry_target, max_regions=max_regions),
                    attempt_index=attempt_index,
                    repaired_from_prompt=repair.failed_prompt,
                )
                last_segmentation = retry.segmentation
                if retry.segmentation.regions:
                    active_span.set_attributes(
                        {
                            "recovered": True,
                            "winning_prompt": prompt,
                            "attempt_count": attempt_index,
                            "region_count": len(retry.segmentation.regions),
                        }
                    )
                    return retry
            active_span.set_attributes(
                {
                    "recovered": False,
                    "attempt_count": len(repair.alternate_prompts),
                    "last_prompt": last_segmentation.prompt,
                    "region_count": len(last_segmentation.regions),
                }
            )
            return PlannedSegmentation(
                target=target,
                segmentation=last_segmentation,
                max_regions=planned.max_regions,
            )

    def _segment_target(
        self,
        *,
        request: SegmentMatchRequest,
        work: SegmentationWork,
        attempt_index: int = 0,
        repaired_from_prompt: str | None = None,
    ) -> PlannedSegmentation:
        target = work.target
        with span(
            "material_search.segment_target",
            run_id=str(request.run_id),
            target_id=target.target_id,
            target_label=target.label,
            material_family_hint=target.material_family_hint,
            sam3_prompt=target.sam3_prompt,
            max_regions=work.max_regions,
            attempt_index=attempt_index,
            repaired_from_prompt=repaired_from_prompt,
        ) as active_span:
            segmentation = self.sam3_client.segment_image(
                prompt=target.sam3_prompt,
                image_object_key=request.image_object_key,
                image_url=str(request.image_url) if request.image_url else None,
                confidence_threshold=request.confidence_threshold,
                max_regions=work.max_regions,
                include_masks=request.include_masks,
            )
            active_span.set_attributes(
                {
                    "region_count": len(segmentation.regions),
                    "image_width": segmentation.image_width,
                    "image_height": segmentation.image_height,
                    "model_id": segmentation.model_id,
                }
            )
            return PlannedSegmentation(
                target=target,
                segmentation=segmentation,
                max_regions=work.max_regions,
            )

    def _prepare_region_match(
        self, *, request: SegmentMatchRequest, work: RegionMatchWork
    ) -> PreparedRegionMatch:
        with span(
            "material_search.prepare_region_match",
            run_id=str(request.run_id),
            result_region_id=work.result_region_id,
            source_region_id=work.region.id,
            target_id=work.target.target_id,
            target_label=work.target.label,
            region_score=work.region.score,
        ) as active_span:
            artifact_region = work.region.model_copy(update={"id": work.result_region_id})
            artifact = self.artifact_store.create_region_crop(
                run_id=str(request.run_id),
                source_image_object_key=request.image_object_key,
                source_image_url=str(request.image_url) if request.image_url else None,
                region=artifact_region,
                image_width=work.segmentation.image_width,
                image_height=work.segmentation.image_height,
            )
            active_span.set_attributes(
                {
                    "crop_object_key": artifact.object_key,
                    "crop_width": artifact.width,
                    "crop_height": artifact.height,
                }
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
                active_span.set_attributes(
                    {
                        "embedding_model_id": embedding.model_id,
                        "embedding_dimensions": embedding.dimensions,
                        "embedding_fallback": False,
                    }
                )
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code != 429:
                    raise
                active_span.set_attributes(
                    {
                        "embedding_fallback": True,
                        "fallback_reason": "embedding_service_429",
                    }
                )
                embedding = None
            return PreparedRegionMatch(work=work, artifact=artifact, embedding=embedding)

    def _match_prepared_region(
        self, *, request: SegmentMatchRequest, prepared: PreparedRegionMatch
    ) -> SegmentRegionMatchSet:
        work = prepared.work
        target = work.target
        region = work.region
        artifact = prepared.artifact
        with span(
            "material_search.match_region",
            run_id=str(request.run_id),
            result_region_id=work.result_region_id,
            source_region_id=region.id,
            target_id=target.target_id,
            target_label=target.label,
            embedding_fallback=prepared.embedding is None,
            limit=request.matches_per_region,
            min_similarity=request.min_similarity,
        ) as active_span:
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
                active_span.set_attribute("persisted_region_id", str(persisted_region.id))
            active_span.set_attributes(
                {
                    "match_count": len(match_set.matches),
                    "top_similarity": (
                        match_set.matches[0].match.similarity if match_set.matches else None
                    ),
                    "match_model_id": match_set.model_id,
                    "match_dimensions": match_set.dimensions,
                }
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

        with span(
            "material_search.match_regions",
            run_id=str(request.run_id),
            segmentation_count=len(segmentations),
        ) as active_span:
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

            active_span.set_attribute("region_count", len(work_items))
            prepared_matches = _run_ordered_in_parallel(
                work_items,
                lambda work: self._prepare_region_match(request=request, work=work),
                max_workers=_MAX_REGION_MATCH_WORKERS,
            )
            regions = [
                self._match_prepared_region(request=request, prepared=prepared)
                for prepared in prepared_matches
            ]
            active_span.set_attributes(
                {
                    "prepared_count": len(prepared_matches),
                    "matched_region_count": len(regions),
                    "total_match_count": sum(len(region.matches) for region in regions),
                }
            )
            return {"regions": regions}

    def _complete_run(self, state: SearchGraphState) -> SearchGraphState:
        request = state["request"]
        with span(
            "material_search.complete_run",
            run_id=str(request.run_id),
            image_width=state["image_width"],
            image_height=state["image_height"],
            region_count=len(state["regions"]),
        ):
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
    return target.material_family_hint or ""


def _failed_segmentations(segmentations: list[PlannedSegmentation]) -> list[PlannedSegmentation]:
    return [planned for planned in segmentations if not planned.segmentation.regions]


def _stored_segments_from_segmentations(
    segmentations: list[PlannedSegmentation],
) -> list[StoredSegment]:
    return [
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


def _run_ordered_in_parallel(
    items: list[_T], fn: Callable[[_T], _R], *, max_workers: int
) -> list[_R]:
    if len(items) <= 1:
        return [fn(item) for item in items]

    with ThreadPoolExecutor(max_workers=min(len(items), max_workers)) as executor:
        futures = [executor.submit(fn, item) for item in items]
        return [future.result() for future in futures]
