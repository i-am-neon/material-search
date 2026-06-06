import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError

from app.catalog.repository import PostgresCatalogRepository
from app.catalog.schemas import CatalogItemCreate
from app.db import get_connection

DEFAULT_MANIFEST_PATH = (
    Path(__file__).resolve().parents[3] / "data" / "catalog" / "material-bank-style-seed.json"
)


class CatalogSeedManifest(BaseModel):
    items: list[CatalogItemCreate] = Field(min_length=1)


def load_manifest(path: Path) -> CatalogSeedManifest:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path} is not valid JSON: {exc}") from exc

    try:
        return CatalogSeedManifest.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(f"{path} does not match the catalog seed schema:\n{exc}") from exc


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Load the one-time starter catalog seed.")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST_PATH,
        help="Path to a catalog seed JSON manifest.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate the manifest and print the item count without inserting rows.",
    )
    args = parser.parse_args(argv)

    manifest = load_manifest(args.manifest)
    print(f"Catalog seed items: {len(manifest.items)}")

    if args.dry_run:
        return 0

    with get_connection() as conn:
        repository = PostgresCatalogRepository(conn)
        for index, item in enumerate(manifest.items, start=1):
            created = repository.create_item(item)
            print(f"Inserted {index}: {created.manufacturer} / {created.name} ({created.id})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
