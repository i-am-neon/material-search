from datetime import UTC, datetime
from uuid import uuid4

from psycopg.pq import TransactionStatus

from app.model_services.segmentation import SegmentationRegion
from app.search.artifacts import RegionArtifact
from app.search.repository import PostgresSearchRunRepository
from app.search.schemas import PlannedMaterialTarget


class FakeConnectionInfo:
    transaction_status = TransactionStatus.INERROR


class FakeConnection:
    def __init__(self):
        self.info = FakeConnectionInfo()
        self.rollback_calls = 0
        self.execute_calls = []

    def rollback(self):
        self.rollback_calls += 1
        self.info.transaction_status = TransactionStatus.IDLE

    def execute(self, sql, params):
        self.execute_calls.append({"sql": sql, "params": params})
        return self

    def fetchone(self):
        return {
            "id": self.execute_calls[-1]["params"][1],
            "prompt": "upholstery",
            "source_image_object_key": "uploads/room.jpg",
            "source_image_url": None,
            "status": "failed",
            "error": self.execute_calls[-1]["params"][0],
            "image_width": None,
            "image_height": None,
            "created_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC),
        }

    def commit(self):
        return None


def test_fail_run_rolls_back_aborted_transaction_before_status_update():
    conn = FakeConnection()
    run_id = uuid4()

    run = PostgresSearchRunRepository(conn).fail_run(run_id=run_id, error="SAM3 unavailable")

    assert conn.rollback_calls == 1
    assert conn.execute_calls[0]["params"] == ("SAM3 unavailable", run_id)
    assert run.status == "failed"
    assert run.error == "SAM3 unavailable"


class FakeCreateRegionConnection:
    def __init__(self):
        self.execute_calls = []

    def execute(self, sql, params):
        self.execute_calls.append({"sql": sql, "params": params})
        return self

    def fetchone(self):
        params = self.execute_calls[-1]["params"]
        return {
            "id": uuid4(),
            "run_id": params[0],
            "target_id": params[1],
            "target_label": params[2],
            "source_region_id": params[3],
            "prompt": params[4],
            "score": params[5],
            "box_xyxy": [1.0, 2.0, 101.0, 122.0],
            "mask": None,
            "crop_object_key": params[8],
            "crop_width": params[9],
            "crop_height": params[10],
            "embedding_model_id": params[11],
            "embedding_dimensions": params[12],
            "status": "matched",
            "created_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC),
        }

    def commit(self):
        return None


def test_create_region_upserts_target_scoped_source_region_for_worker_retries():
    conn = FakeCreateRegionConnection()
    run_id = uuid4()

    region = PostgresSearchRunRepository(conn).create_region(
        run_id=run_id,
        target=PlannedMaterialTarget(
            target_id="upholstery",
            label="Upholstery",
            sam3_prompt="green upholstery",
            material_family_hint="textile",
            reason="The user asked for upholstery.",
            priority=1,
            max_regions=1,
        ),
        region=SegmentationRegion(
            id="sam3_region_0",
            prompt="green upholstery",
            score=0.91,
            box_xyxy=[1.0, 2.0, 101.0, 122.0],
        ),
        artifact=RegionArtifact(
            object_key="runs/run/regions/upholstery__sam3_region_0/crop.jpg",
            signed_url="https://example.com/crop.jpg",
            width=100,
            height=120,
        ),
        embedding_model_id="test-model",
        embedding_dimensions=3,
    )

    sql = conn.execute_calls[0]["sql"]
    assert "on conflict (run_id, target_id, source_region_id) do update" in sql
    assert region.target_id == "upholstery"
    assert region.source_region_id == "sam3_region_0"
