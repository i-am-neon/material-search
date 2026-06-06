from abc import ABC, abstractmethod
from typing import Any
from uuid import UUID

from psycopg import Connection
from psycopg.types.json import Jsonb

from app.catalog.schemas import CatalogItem, CatalogItemCreate, CatalogMatch


class CatalogRepository(ABC):
    @abstractmethod
    def create_item(self, item: CatalogItemCreate) -> CatalogItem:
        raise NotImplementedError

    @abstractmethod
    def list_items(self, limit: int = 100, offset: int = 0) -> list[CatalogItem]:
        raise NotImplementedError

    @abstractmethod
    def get_item(self, catalog_item_id: UUID) -> CatalogItem | None:
        raise NotImplementedError

    @abstractmethod
    def list_items_missing_embedding(
        self, *, model_id: str, dimensions: int, limit: int = 500
    ) -> list[CatalogItem]:
        raise NotImplementedError

    @abstractmethod
    def count_items_missing_embedding(self, *, model_id: str, dimensions: int) -> int:
        raise NotImplementedError

    @abstractmethod
    def upsert_embedding(
        self, *, catalog_item_id: UUID, model_id: str, dimensions: int, embedding: list[float]
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def search_by_embedding(
        self, *, embedding: list[float], model_id: str, limit: int, min_similarity: float
    ) -> list[CatalogMatch]:
        raise NotImplementedError


class PostgresCatalogRepository(CatalogRepository):
    def __init__(self, conn: Connection):
        self.conn = conn

    def create_item(self, item: CatalogItemCreate) -> CatalogItem:
        row = self.conn.execute(
            """
            insert into catalog_items (
              manufacturer,
              name,
              material_family,
              image_object_key,
              image_url,
              metadata
            )
            values (%s, %s, %s, %s, %s, %s::jsonb)
            returning *
            """,
            (
                item.manufacturer,
                item.name,
                item.material_family,
                item.image_object_key,
                str(item.image_url) if item.image_url else None,
                Jsonb(item.metadata),
            ),
        ).fetchone()
        self.conn.commit()
        return CatalogItem.model_validate(row)

    def list_items(self, limit: int = 100, offset: int = 0) -> list[CatalogItem]:
        rows = self.conn.execute(
            """
            select *
            from catalog_items
            order by created_at desc
            limit %s offset %s
            """,
            (limit, offset),
        ).fetchall()
        return [CatalogItem.model_validate(row) for row in rows]

    def get_item(self, catalog_item_id: UUID) -> CatalogItem | None:
        row = self.conn.execute(
            "select * from catalog_items where id = %s",
            (catalog_item_id,),
        ).fetchone()
        return CatalogItem.model_validate(row) if row else None

    def list_items_missing_embedding(
        self, *, model_id: str, dimensions: int, limit: int = 500
    ) -> list[CatalogItem]:
        rows = self.conn.execute(
            """
            select ci.*
            from catalog_items ci
            left join catalog_item_embeddings cie
              on cie.catalog_item_id = ci.id
             and cie.model_id = %s
             and cie.dimensions = %s
            where cie.catalog_item_id is null
            order by ci.created_at asc
            limit %s
            """,
            (model_id, dimensions, limit),
        ).fetchall()
        return [CatalogItem.model_validate(row) for row in rows]

    def count_items_missing_embedding(self, *, model_id: str, dimensions: int) -> int:
        row = self.conn.execute(
            """
            select count(*) as count
            from catalog_items ci
            left join catalog_item_embeddings cie
              on cie.catalog_item_id = ci.id
             and cie.model_id = %s
             and cie.dimensions = %s
            where cie.catalog_item_id is null
            """,
            (model_id, dimensions),
        ).fetchone()
        return int(row["count"])

    def upsert_embedding(
        self, *, catalog_item_id: UUID, model_id: str, dimensions: int, embedding: list[float]
    ) -> None:
        self.conn.execute(
            """
            insert into catalog_embedding_models (id, dimensions)
            values (%s, %s)
            on conflict (id) do update
            set dimensions = excluded.dimensions
            """,
            (model_id, dimensions),
        )
        self.conn.execute(
            """
            insert into catalog_item_embeddings (
              catalog_item_id,
              model_id,
              dimensions,
              embedding
            )
            values (%s, %s, %s, %s::vector)
            on conflict (catalog_item_id, model_id) do update
            set dimensions = excluded.dimensions,
                embedding = excluded.embedding,
                created_at = now()
            """,
            (catalog_item_id, model_id, dimensions, _vector_literal(embedding)),
        )
        self.conn.commit()

    def search_by_embedding(
        self, *, embedding: list[float], model_id: str, limit: int, min_similarity: float
    ) -> list[CatalogMatch]:
        rows = self.conn.execute(
            """
            select *
            from match_catalog_items(%s::vector, %s, %s, %s)
            """,
            (_vector_literal(embedding), model_id, limit, min_similarity),
        ).fetchall()
        return [
            CatalogMatch(
                item=CatalogItem.model_validate(_catalog_item_from_match_row(row)),
                model_id=row["model_id"],
                similarity=row["similarity"],
            )
            for row in rows
        ]


def _vector_literal(values: list[float]) -> str:
    return "[" + ",".join(str(value) for value in values) + "]"


def _catalog_item_from_match_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["catalog_item_id"],
        "manufacturer": row["manufacturer"],
        "name": row["name"],
        "material_family": row["material_family"],
        "image_object_key": row["image_object_key"],
        "image_url": row["image_url"],
        "metadata": row["metadata"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
