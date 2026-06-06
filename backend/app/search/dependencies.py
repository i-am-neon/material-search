from collections.abc import Iterator

from app.db import get_connection
from app.search.repository import PostgresSearchRunRepository, SearchRunRepository


def get_search_run_repository() -> Iterator[SearchRunRepository]:
    with get_connection() as conn:
        yield PostgresSearchRunRepository(conn)
