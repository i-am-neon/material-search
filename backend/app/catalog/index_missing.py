import argparse
from collections.abc import Sequence

from app.catalog.enrichment import CatalogEnricher
from app.catalog.repository import PostgresCatalogRepository
from app.catalog.schemas import CatalogEmbeddingJob
from app.core.config import get_settings
from app.db import get_connection
from app.model_services.factory import get_embedding_client


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Index catalog items missing image embeddings.")
    parser.add_argument("--batch-size", type=int, default=25, help="Items to enrich per DB batch.")
    parser.add_argument(
        "--max-items",
        type=int,
        default=0,
        help="Maximum items to enrich before exiting. Use 0 for no cap.",
    )
    args = parser.parse_args(argv)

    if args.batch_size < 1:
        parser.error("--batch-size must be at least 1")
    if args.max_items < 0:
        parser.error("--max-items must be 0 or greater")

    settings = get_settings()
    processed = 0

    with get_connection() as conn:
        repository = PostgresCatalogRepository(conn)
        client = get_embedding_client()
        enricher = CatalogEnricher(repository, client)
        remaining = repository.count_items_missing_embedding(
            model_id=settings.embedding_model_id,
            dimensions=settings.embedding_dimensions,
        )
        print(f"Missing catalog embeddings: {remaining}")

        while remaining > 0:
            if args.max_items and processed >= args.max_items:
                break

            batch_limit = args.batch_size
            if args.max_items:
                batch_limit = min(batch_limit, args.max_items - processed)

            items = repository.list_items_missing_embedding(
                model_id=settings.embedding_model_id,
                dimensions=settings.embedding_dimensions,
                limit=batch_limit,
            )
            if not items:
                break

            for item in items:
                job = CatalogEmbeddingJob(
                    catalog_item_id=item.id,
                    model_id=settings.embedding_model_id,
                    dimensions=settings.embedding_dimensions,
                )
                enricher.enrich_item(job)
                processed += 1
                print(f"Indexed {processed}: {item.id} {item.manufacturer} / {item.name}")

            remaining = repository.count_items_missing_embedding(
                model_id=settings.embedding_model_id,
                dimensions=settings.embedding_dimensions,
            )
            print(f"Remaining catalog embeddings: {remaining}")

    print(f"Indexed catalog embeddings: {processed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

