from collections.abc import Iterator

from app.catalog.repository import CatalogRepository, PostgresCatalogRepository
from app.db import get_connection


def get_catalog_repository() -> Iterator[CatalogRepository]:
    with get_connection() as conn:
        yield PostgresCatalogRepository(conn)

