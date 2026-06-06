from abc import ABC, abstractmethod
from typing import Any
from uuid import UUID

from psycopg import Connection
from psycopg.pq import TransactionStatus
from psycopg.types.json import Jsonb

from app.catalog.schemas import CatalogItem, CatalogMatch
from app.model_services.segmentation import SegmentationMask, SegmentationRegion
from app.search.artifacts import RegionArtifact
from app.search.schemas import (
    MaterialSearchMatchRecord,
    MaterialSearchPlan,
    MaterialSearchRegionRecord,
    MaterialSearchRun,
    PlannedMaterialTarget,
    RankedRegionMatch,
    SearchRunStatus,
    SegmentMatchRequest,
    SegmentMatchResponse,
    SegmentRegionMatchSet,
    build_result_region_id,
)


class SearchRunRepository(ABC):
    @abstractmethod
    def create_run(
        self, request: SegmentMatchRequest, *, status: SearchRunStatus = "running"
    ) -> MaterialSearchRun:
        raise NotImplementedError

    @abstractmethod
    def get_run(self, run_id: UUID) -> MaterialSearchRun | None:
        raise NotImplementedError

    @abstractmethod
    def mark_run_running(self, run_id: UUID) -> MaterialSearchRun:
        raise NotImplementedError

    @abstractmethod
    def clear_run_outputs(self, run_id: UUID) -> None:
        raise NotImplementedError

    @abstractmethod
    def replace_planned_targets(self, *, run_id: UUID, plan: MaterialSearchPlan) -> None:
        raise NotImplementedError

    @abstractmethod
    def complete_run(
        self, *, run_id: UUID, image_width: int, image_height: int
    ) -> MaterialSearchRun:
        raise NotImplementedError

    @abstractmethod
    def fail_run(self, *, run_id: UUID, error: str) -> MaterialSearchRun:
        raise NotImplementedError

    @abstractmethod
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
        raise NotImplementedError

    @abstractmethod
    def replace_region_matches(
        self,
        *,
        run_id: UUID,
        region_id: UUID,
        matches: list[RankedRegionMatch],
    ) -> list[MaterialSearchMatchRecord]:
        raise NotImplementedError

    @abstractmethod
    def get_run_result(self, run_id: UUID) -> SegmentMatchResponse | None:
        raise NotImplementedError


class PostgresSearchRunRepository(SearchRunRepository):
    def __init__(self, conn: Connection):
        self.conn = conn

    def create_run(
        self, request: SegmentMatchRequest, *, status: SearchRunStatus = "running"
    ) -> MaterialSearchRun:
        row = self.conn.execute(
            """
            insert into material_search_runs (
              id,
              prompt,
              source_image_object_key,
              source_image_url,
              status
            )
            values (coalesce(%s::uuid, uuid_generate_v4()), %s, %s, %s, %s)
            returning *
            """,
            (
                request.run_id,
                request.prompt,
                request.image_object_key,
                str(request.image_url) if request.image_url else None,
                status,
            ),
        ).fetchone()
        self.conn.commit()
        return MaterialSearchRun.model_validate(row)

    def get_run(self, run_id: UUID) -> MaterialSearchRun | None:
        row = self.conn.execute(
            "select * from material_search_runs where id = %s",
            (run_id,),
        ).fetchone()
        return MaterialSearchRun.model_validate(row) if row else None

    def mark_run_running(self, run_id: UUID) -> MaterialSearchRun:
        row = self.conn.execute(
            """
            update material_search_runs
            set status = 'running',
                error = null
            where id = %s
            returning *
            """,
            (run_id,),
        ).fetchone()
        self.conn.commit()
        return _require_row(row, f"Material search run {run_id} does not exist")

    def clear_run_outputs(self, run_id: UUID) -> None:
        self.conn.execute("delete from material_search_regions where run_id = %s", (run_id,))
        self.conn.execute("delete from material_search_targets where run_id = %s", (run_id,))
        self.conn.commit()

    def replace_planned_targets(self, *, run_id: UUID, plan: MaterialSearchPlan) -> None:
        with self.conn.transaction():
            self.conn.execute("delete from material_search_targets where run_id = %s", (run_id,))
            for target in plan.targets:
                self.conn.execute(
                    """
                    insert into material_search_targets (
                      run_id,
                      target_id,
                      label,
                      sam3_prompt,
                      material_family_hint,
                      reason,
                      priority,
                      max_regions,
                      avoid
                    )
                    values (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                    """,
                    (
                        run_id,
                        target.target_id,
                        target.label,
                        target.sam3_prompt,
                        target.material_family_hint,
                        target.reason,
                        target.priority,
                        target.max_regions,
                        Jsonb(plan.avoid),
                    ),
                )
        self.conn.commit()

    def complete_run(
        self, *, run_id: UUID, image_width: int, image_height: int
    ) -> MaterialSearchRun:
        row = self.conn.execute(
            """
            update material_search_runs
            set status = 'completed',
                error = null,
                image_width = %s,
                image_height = %s
            where id = %s
            returning *
            """,
            (image_width, image_height, run_id),
        ).fetchone()
        self.conn.commit()
        return _require_row(row, f"Material search run {run_id} does not exist")

    def fail_run(self, *, run_id: UUID, error: str) -> MaterialSearchRun:
        if self.conn.info.transaction_status == TransactionStatus.INERROR:
            self.conn.rollback()
        row = self.conn.execute(
            """
            update material_search_runs
            set status = 'failed',
                error = %s
            where id = %s
            returning *
            """,
            (error, run_id),
        ).fetchone()
        self.conn.commit()
        return _require_row(row, f"Material search run {run_id} does not exist")

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
        row = self.conn.execute(
            """
            insert into material_search_regions (
              run_id,
              target_id,
              target_label,
              source_region_id,
              prompt,
              score,
              box_xyxy,
              mask,
              crop_object_key,
              crop_width,
              crop_height,
              embedding_model_id,
              embedding_dimensions,
              status
            )
            values (
              %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s, %s, %s, %s, 'matched'
            )
            on conflict (run_id, target_id, source_region_id) do update
            set target_label = excluded.target_label,
                prompt = excluded.prompt,
                score = excluded.score,
                box_xyxy = excluded.box_xyxy,
                mask = excluded.mask,
                crop_object_key = excluded.crop_object_key,
                crop_width = excluded.crop_width,
                crop_height = excluded.crop_height,
                embedding_model_id = excluded.embedding_model_id,
                embedding_dimensions = excluded.embedding_dimensions,
                status = excluded.status,
                updated_at = now()
            returning *
            """,
            (
                run_id,
                target.target_id if target else None,
                target.label if target else None,
                region.id,
                region.prompt,
                region.score,
                Jsonb(region.box_xyxy),
                Jsonb(region.mask.model_dump(mode="json")) if region.mask else None,
                artifact.object_key,
                artifact.width,
                artifact.height,
                embedding_model_id,
                embedding_dimensions,
            ),
        ).fetchone()
        self.conn.commit()
        return MaterialSearchRegionRecord.model_validate(row)

    def replace_region_matches(
        self,
        *,
        run_id: UUID,
        region_id: UUID,
        matches: list[RankedRegionMatch],
    ) -> list[MaterialSearchMatchRecord]:
        with self.conn.transaction():
            self.conn.execute(
                "delete from material_search_matches where region_id = %s",
                (region_id,),
            )
            rows = []
            for match in matches:
                row = self.conn.execute(
                    """
                    insert into material_search_matches (
                      run_id,
                      region_id,
                      catalog_item_id,
                      embedding_model_id,
                      similarity,
                      rank
                    )
                    values (%s, %s, %s, %s, %s, %s)
                    returning *
                    """,
                    (
                        run_id,
                        region_id,
                        match.match.item.id,
                        match.match.model_id,
                        match.match.similarity,
                        match.rank,
                    ),
                ).fetchone()
                rows.append(row)
        self.conn.commit()
        return [MaterialSearchMatchRecord.model_validate(row) for row in rows]

    def get_run_result(self, run_id: UUID) -> SegmentMatchResponse | None:
        run = self.get_run(run_id)
        if run is None or run.image_width is None or run.image_height is None:
            return None

        region_rows = self.conn.execute(
            """
            select *
            from material_search_regions
            where run_id = %s
            order by created_at asc
            """,
            (run_id,),
        ).fetchall()

        regions = [self._region_match_set(row) for row in region_rows]
        plan = self._get_run_plan(run_id)
        return SegmentMatchResponse(
            run_id=run.id,
            prompt=run.prompt,
            plan=plan,
            image_width=run.image_width,
            image_height=run.image_height,
            regions=regions,
        )

    def _get_run_plan(self, run_id: UUID) -> MaterialSearchPlan | None:
        rows = self.conn.execute(
            """
            select *
            from material_search_targets
            where run_id = %s
            order by priority asc
            """,
            (run_id,),
        ).fetchall()
        if not rows:
            return None
        return MaterialSearchPlan(
            user_intent_summary="Planned material targets",
            avoid=rows[0]["avoid"] or [],
            targets=[
                PlannedMaterialTarget(
                    target_id=row["target_id"],
                    label=row["label"],
                    sam3_prompt=row["sam3_prompt"],
                    material_family_hint=row["material_family_hint"],
                    reason=row["reason"],
                    priority=row["priority"],
                    max_regions=row["max_regions"],
                )
                for row in rows
            ],
        )

    def _region_match_set(self, row: dict[str, Any]) -> SegmentRegionMatchSet:
        match_rows = self.conn.execute(
            """
            select
              msm.rank,
              msm.similarity,
              msm.embedding_model_id as match_model_id,
              ci.id as catalog_item_id,
              ci.manufacturer,
              ci.name,
              ci.material_family,
              ci.image_object_key,
              ci.image_url,
              ci.metadata,
              ci.created_at,
              ci.updated_at
            from material_search_matches msm
            join catalog_items ci on ci.id = msm.catalog_item_id
            where msm.region_id = %s
            order by msm.rank asc
            """,
            (row["id"],),
        ).fetchall()
        source_region_id = row["source_region_id"]
        result_region_id = build_result_region_id(
            target_id=row["target_id"],
            source_region_id=source_region_id,
        )
        return SegmentRegionMatchSet(
            result_region_id=result_region_id,
            region=SegmentationRegion(
                id=source_region_id,
                prompt=row["prompt"],
                score=row["score"],
                box_xyxy=row["box_xyxy"],
                mask=SegmentationMask.model_validate(row["mask"]) if row["mask"] else None,
            ),
            target_id=row["target_id"],
            target_label=row["target_label"],
            crop_object_key=row["crop_object_key"],
            crop_url=None,
            crop_width=row["crop_width"],
            crop_height=row["crop_height"],
            model_id=row["embedding_model_id"],
            dimensions=row["embedding_dimensions"],
            matches=[
                RankedRegionMatch(
                    region_id=result_region_id,
                    rank=match_row["rank"],
                    match=CatalogMatch(
                        item=CatalogItem.model_validate(
                            {
                                "id": match_row["catalog_item_id"],
                                "manufacturer": match_row["manufacturer"],
                                "name": match_row["name"],
                                "material_family": match_row["material_family"],
                                "image_object_key": match_row["image_object_key"],
                                "image_url": match_row["image_url"],
                                "metadata": match_row["metadata"],
                                "created_at": match_row["created_at"],
                                "updated_at": match_row["updated_at"],
                            }
                        ),
                        model_id=match_row["match_model_id"],
                        similarity=match_row["similarity"],
                    ),
                )
                for match_row in match_rows
            ],
        )


def _require_row(row: dict[str, Any] | None, message: str) -> MaterialSearchRun:
    if row is None:
        raise ValueError(message)
    return MaterialSearchRun.model_validate(row)
