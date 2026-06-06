from abc import ABC, abstractmethod
from typing import Any
from uuid import UUID

from psycopg import Connection
from psycopg.types.json import Jsonb

from app.model_services.segmentation import SegmentationRegion
from app.search.artifacts import RegionArtifact
from app.search.schemas import (
    MaterialSearchMatchRecord,
    MaterialSearchRegionRecord,
    MaterialSearchRun,
    RankedRegionMatch,
    SegmentMatchRequest,
)


class SearchRunRepository(ABC):
    @abstractmethod
    def create_run(self, request: SegmentMatchRequest) -> MaterialSearchRun:
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


class PostgresSearchRunRepository(SearchRunRepository):
    def __init__(self, conn: Connection):
        self.conn = conn

    def create_run(self, request: SegmentMatchRequest) -> MaterialSearchRun:
        row = self.conn.execute(
            """
            insert into material_search_runs (
              id,
              prompt,
              source_image_object_key,
              source_image_url,
              status
            )
            values (coalesce(%s::uuid, uuid_generate_v4()), %s, %s, %s, 'running')
            returning *
            """,
            (
                request.run_id,
                request.prompt,
                request.image_object_key,
                str(request.image_url) if request.image_url else None,
            ),
        ).fetchone()
        self.conn.commit()
        return MaterialSearchRun.model_validate(row)

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
        region: SegmentationRegion,
        artifact: RegionArtifact,
        embedding_model_id: str,
        embedding_dimensions: int,
    ) -> MaterialSearchRegionRecord:
        row = self.conn.execute(
            """
            insert into material_search_regions (
              run_id,
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
            values (%s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s, %s, %s, %s, 'matched')
            returning *
            """,
            (
                run_id,
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


def _require_row(row: dict[str, Any] | None, message: str) -> MaterialSearchRun:
    if row is None:
        raise ValueError(message)
    return MaterialSearchRun.model_validate(row)
