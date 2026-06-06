from collections.abc import Iterator
from contextlib import contextmanager

from psycopg import Connection
from psycopg.rows import dict_row

from app.core.config import get_settings


@contextmanager
def get_connection() -> Iterator[Connection]:
    settings = get_settings()
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is required for database-backed catalog operations")

    with Connection.connect(settings.database_url, row_factory=dict_row) as conn:
        yield conn

