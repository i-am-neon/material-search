import argparse
import json
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

import httpx
from PIL import Image, ImageFilter, ImageStat

from app.catalog.load_seed import CatalogSeedManifest, load_manifest
from app.catalog.material_bank_import import DEFAULT_OUTPUT_PATH as DEFAULT_RAW_MANIFEST_PATH

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CURATED_MANIFEST_PATH = (
    REPO_ROOT / "data" / "catalog" / "material-bank-public-demo-curated-seed.json"
)


@dataclass(frozen=True)
class ImageQuality:
    image: Image.Image
    white_ratio: float
    nonwhite_bbox_area: float
    edge_mean: float
    stddev_mean: float


@dataclass(frozen=True)
class FilterResult:
    manifest: CatalogSeedManifest
    removed: Counter[str]


ImageFetcher = Callable[[str], bytes]


def filter_manifest(
    manifest: CatalogSeedManifest,
    *,
    fetch_image: ImageFetcher,
    per_category: int | None = None,
) -> FilterResult:
    kept = []
    removed: Counter[str] = Counter()
    kept_by_category: Counter[str] = Counter()

    for item in manifest.items:
        category = _category_name(item)
        if per_category is not None and kept_by_category[category] >= per_category:
            removed["over_category_limit"] += 1
            continue

        image_url = str(item.image_url) if item.image_url else ""
        if not image_url:
            removed["missing_image_url"] += 1
            continue

        try:
            quality = analyze_image(fetch_image(image_url))
        except Exception:
            removed["invalid_or_unreachable_image"] += 1
            continue

        if category == "Paints" and is_paint_object_photo(quality):
            removed["paint_object_photo"] += 1
            continue

        kept.append(item)
        kept_by_category[category] += 1

    return FilterResult(manifest=CatalogSeedManifest(items=kept), removed=removed)


def analyze_image(image_bytes: bytes) -> ImageQuality:
    image = Image.open(BytesIO(image_bytes)).convert("RGB")
    sample = image.resize((128, 128))
    pixels = list(
        sample.get_flattened_data() if hasattr(sample, "get_flattened_data") else sample.getdata()
    )
    total_pixels = len(pixels)
    white_pixels = sum(1 for r, g, b in pixels if r > 240 and g > 240 and b > 240)

    nonwhite_mask = Image.new("L", sample.size)
    nonwhite_mask.putdata(
        [0 if r > 245 and g > 245 and b > 245 else 255 for r, g, b in pixels]
    )
    bbox = nonwhite_mask.getbbox()
    nonwhite_bbox_area = (
        0.0 if bbox is None else ((bbox[2] - bbox[0]) * (bbox[3] - bbox[1])) / total_pixels
    )

    edges = sample.convert("L").filter(ImageFilter.FIND_EDGES)
    return ImageQuality(
        image=image,
        white_ratio=white_pixels / total_pixels,
        nonwhite_bbox_area=nonwhite_bbox_area,
        edge_mean=ImageStat.Stat(edges).mean[0],
        stddev_mean=sum(ImageStat.Stat(sample).stddev) / 3,
    )


def is_paint_object_photo(quality: ImageQuality) -> bool:
    """Detect paint cans/product objects on a white background."""
    return (
        quality.white_ratio >= 0.45
        and 0.25 <= quality.nonwhite_bbox_area <= 0.75
        and quality.edge_mean >= 18
        and quality.stddev_mean >= 35
    )


def write_manifest(manifest: CatalogSeedManifest, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(manifest.model_dump(mode="json"), indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )


def category_counts(manifest: CatalogSeedManifest) -> dict[str, int]:
    return dict(Counter(_category_name(item) for item in manifest.items).most_common())


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Filter a scraped catalog manifest into a demo-safe curated manifest."
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_RAW_MANIFEST_PATH,
        help="Path to the raw catalog manifest.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_CURATED_MANIFEST_PATH,
        help="Path to write the curated catalog manifest.",
    )
    parser.add_argument(
        "--per-category",
        type=int,
        default=None,
        help="Optional cap after filtering.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Filter and summarize without writing the curated manifest.",
    )
    args = parser.parse_args(argv)

    raw_manifest = load_manifest(args.manifest)
    with httpx.Client(timeout=20, follow_redirects=True) as client:
        result = filter_manifest(
            raw_manifest,
            fetch_image=lambda url: _fetch_image(client, url),
            per_category=args.per_category,
        )

    print(f"Raw catalog items: {len(raw_manifest.items)}")
    print(f"Curated catalog items: {len(result.manifest.items)}")
    for reason, count in result.removed.most_common():
        print(f"- removed {reason}: {count}")
    for category, count in category_counts(result.manifest).items():
        print(f"- {category}: {count}")

    if args.dry_run:
        return 0

    write_manifest(result.manifest, args.output)
    print(f"Wrote {args.output}")
    return 0


def _fetch_image(client: httpx.Client, url: str) -> bytes:
    response = client.get(url)
    response.raise_for_status()
    if not response.headers.get("content-type", "").startswith("image/"):
        raise ValueError(f"{url} did not return image content.")
    return response.content


def _category_name(item) -> str:
    return str(item.metadata.get("source_category") or item.material_family or "Uncategorized")


if __name__ == "__main__":
    raise SystemExit(main())
