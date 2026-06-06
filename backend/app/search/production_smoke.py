import argparse
import json
from collections.abc import Sequence
from typing import Any

from app.catalog.repository import PostgresCatalogRepository
from app.core.config import Settings, get_settings
from app.db import get_connection
from app.model_services.factory import get_embedding_client, get_sam3_client
from app.model_services.sam3_smoke import DEFAULT_SMOKE_IMAGE_URL
from app.search.artifacts import get_region_artifact_store
from app.search.repository import PostgresSearchRunRepository
from app.search.schemas import SegmentMatchRequest, SegmentMatchResponse
from app.search.service import SegmentCatalogMatchService


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run a real Supabase + SAM3 + SigLIP + pgvector segment-match smoke."
    )
    parser.add_argument("--image-url", default=DEFAULT_SMOKE_IMAGE_URL)
    parser.add_argument("--image-object-key", default=None)
    parser.add_argument("--prompt", default="shoe")
    parser.add_argument("--confidence-threshold", type=float, default=0.5)
    parser.add_argument("--max-regions", type=int, default=1)
    parser.add_argument("--matches-per-region", type=int, default=3)
    parser.add_argument("--min-regions", type=int, default=1)
    parser.add_argument("--min-matches-per-region", type=int, default=1)
    parser.add_argument(
        "--min-similarity",
        type=float,
        default=-1.0,
        help="Use a low default so the smoke verifies integration, not match quality.",
    )
    parser.add_argument("--include-masks", action="store_true")
    args = parser.parse_args(argv)

    if args.image_object_key is None and args.image_url is None:
        parser.error("Either --image-object-key or --image-url is required")
    if args.max_regions < 1:
        parser.error("--max-regions must be at least 1")
    if args.matches_per_region < 1:
        parser.error("--matches-per-region must be at least 1")
    if args.min_regions < 1:
        parser.error("--min-regions must be at least 1")
    if args.min_matches_per_region < 0:
        parser.error("--min-matches-per-region must be at least 0")

    settings = get_settings()
    try:
        _validate_settings(settings)
    except RuntimeError as exc:
        parser.error(str(exc))
    request = SegmentMatchRequest(
        image_object_key=args.image_object_key,
        image_url=args.image_url,
        prompt=args.prompt,
        confidence_threshold=args.confidence_threshold,
        max_regions=args.max_regions,
        include_masks=args.include_masks,
        model_id=settings.embedding_model_id,
        dimensions=settings.embedding_dimensions,
        matches_per_region=args.matches_per_region,
        min_similarity=args.min_similarity,
    )

    with get_connection() as conn:
        catalog_repository = PostgresCatalogRepository(conn)
        embedded_count = _count_catalog_embeddings(
            conn,
            model_id=settings.embedding_model_id,
            dimensions=settings.embedding_dimensions,
        )
        if embedded_count == 0:
            raise RuntimeError(
                "Production smoke requires at least one catalog embedding. "
                "Run catalog-index-missing first."
            )

        response = SegmentCatalogMatchService(
            sam3_client=get_sam3_client(),
            artifact_store=get_region_artifact_store(),
            embedding_client=get_embedding_client(),
            catalog_repository=catalog_repository,
            search_run_repository=PostgresSearchRunRepository(conn),
        ).segment_and_match(request)

    _validate_response(
        response,
        min_regions=args.min_regions,
        min_matches_per_region=args.min_matches_per_region,
    )
    print(json.dumps(_summary(response, catalog_embeddings=embedded_count), indent=2))
    return 0


def _validate_settings(settings: Settings) -> None:
    missing = []
    if not settings.database_url:
        missing.append("DATABASE_URL")
    if settings.supabase_url is None:
        missing.append("SUPABASE_URL")
    if not settings.supabase_service_role_key:
        missing.append("SUPABASE_SERVICE_ROLE_KEY")
    if settings.sam3_service_url is None:
        missing.append("SAM3_SERVICE_URL")
    if settings.embedding_service_url is None:
        missing.append("EMBEDDING_SERVICE_URL")
    if missing:
        raise RuntimeError(
            "Production smoke requires real service configuration: " + ", ".join(missing)
        )


def _count_catalog_embeddings(conn, *, model_id: str, dimensions: int) -> int:
    row = conn.execute(
        """
        select count(*) as count
        from catalog_item_embeddings
        where model_id = %s
          and dimensions = %s
        """,
        (model_id, dimensions),
    ).fetchone()
    return int(row["count"])


def _validate_response(
    response: SegmentMatchResponse, *, min_regions: int, min_matches_per_region: int
) -> None:
    if len(response.regions) < min_regions:
        raise RuntimeError(
            f"Production smoke expected at least {min_regions} region(s), "
            f"got {len(response.regions)}"
        )
    sparse_regions = [
        region.region.id
        for region in response.regions
        if len(region.matches) < min_matches_per_region
    ]
    if sparse_regions:
        raise RuntimeError(
            "Production smoke expected at least "
            f"{min_matches_per_region} match(es) per region; sparse regions: {sparse_regions}"
        )


def _summary(response: SegmentMatchResponse, *, catalog_embeddings: int) -> dict[str, Any]:
    first_region = response.regions[0] if response.regions else None
    top_match = first_region.matches[0].match if first_region and first_region.matches else None
    return {
        "run_id": str(response.run_id),
        "prompt": response.prompt,
        "image_width": response.image_width,
        "image_height": response.image_height,
        "region_count": len(response.regions),
        "match_count": sum(len(region.matches) for region in response.regions),
        "catalog_embeddings": catalog_embeddings,
        "model_id": first_region.model_id if first_region else None,
        "dimensions": first_region.dimensions if first_region else None,
        "first_region": {
            "id": first_region.region.id,
            "score": first_region.region.score,
            "box_xyxy": first_region.region.box_xyxy,
            "crop_object_key": first_region.crop_object_key,
            "crop_width": first_region.crop_width,
            "crop_height": first_region.crop_height,
        }
        if first_region
        else None,
        "top_match": {
            "catalog_item_id": str(top_match.item.id),
            "manufacturer": top_match.item.manufacturer,
            "name": top_match.item.name,
            "material_family": top_match.item.material_family,
            "similarity": top_match.similarity,
        }
        if top_match
        else None,
    }


if __name__ == "__main__":
    raise SystemExit(main())
