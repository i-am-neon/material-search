from datetime import UTC, datetime
from uuid import uuid4

from psycopg.pq import TransactionStatus

from app.search.repository import PostgresSearchRunRepository


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
