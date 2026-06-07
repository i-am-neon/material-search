import argparse
import json
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from time import sleep
from urllib.parse import parse_qs, urlparse
from xml.etree import ElementTree

import httpx
from pydantic import BaseModel, Field, ValidationError

from app.catalog.schemas import CatalogItemCreate

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CATEGORY_PLAN_PATH = REPO_ROOT / "data" / "catalog" / "material-bank-demo-categories.json"
DEFAULT_OUTPUT_PATH = REPO_ROOT / "data" / "catalog" / "material-bank-public-demo-seed.json"
DEFAULT_SITEMAP_INDEX_URL = "https://www.materialbank.com/media/sitemap.xml"
USER_AGENT = "material-search-demo-catalog-importer/0.1"

SITEMAP_NS = {
    "sm": "http://www.sitemaps.org/schemas/sitemap/0.9",
    "image": "http://www.google.com/schemas/sitemap-image/1.1",
}
PRODUCT_PATH_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*-\d+$")
TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


class MaterialBankCategory(BaseModel):
    group: str = Field(min_length=1)
    name: str = Field(min_length=1)
    taxonomy_path: list[str] = Field(min_length=1)
    material_family: str = Field(min_length=1)
    aliases: list[str] = Field(default_factory=list)
    per_category: int | None = Field(default=None, ge=1, le=500)


class MaterialBankCategoryPlan(BaseModel):
    source: str = Field(default="material_bank_public_sitemap")
    default_per_category: int = Field(default=50, ge=1, le=500)
    categories: list[MaterialBankCategory] = Field(min_length=1)


class CatalogSeedManifest(BaseModel):
    items: list[CatalogItemCreate] = Field(default_factory=list)


@dataclass(frozen=True)
class SitemapProduct:
    source_url: str
    image_url: str
    image_title: str
    lastmod: str | None
    source_order: int


@dataclass(frozen=True)
class ScoredProduct:
    product: SitemapProduct
    category: MaterialBankCategory
    score: int


def load_category_plan(path: Path) -> MaterialBankCategoryPlan:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path} is not valid JSON: {exc}") from exc

    try:
        return MaterialBankCategoryPlan.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(f"{path} does not match the category plan schema:\n{exc}") from exc


def parse_sitemap_index(xml_text: str) -> list[str]:
    root = ElementTree.fromstring(xml_text)
    sitemap_urls = [
        loc.text.strip()
        for loc in root.findall("sm:sitemap/sm:loc", SITEMAP_NS)
        if loc.text and loc.text.strip()
    ]
    if not sitemap_urls:
        raise ValueError("Sitemap index did not contain child sitemap URLs.")
    return sitemap_urls


def parse_product_sitemap(xml_text: str, *, start_order: int = 0) -> list[SitemapProduct]:
    root = ElementTree.fromstring(xml_text)
    products: list[SitemapProduct] = []

    for source_order, url_node in enumerate(root.findall("sm:url", SITEMAP_NS), start=start_order):
        source_url = _node_text(url_node, "sm:loc")
        if not source_url or not _looks_like_product_url(source_url):
            continue

        image_node = url_node.find("image:image", SITEMAP_NS)
        if image_node is None:
            continue

        image_url = _node_text(image_node, "image:loc")
        if not image_url:
            continue

        image_title = _node_text(image_node, "image:title") or _name_from_slug(source_url)
        products.append(
            SitemapProduct(
                source_url=source_url,
                image_url=_without_query(image_url),
                image_title=_clean_whitespace(image_title),
                lastmod=_node_text(url_node, "sm:lastmod"),
                source_order=source_order,
            )
        )

    return products


def score_product_for_category(product: SitemapProduct, category: MaterialBankCategory) -> int:
    text = " ".join(
        [
            urlparse(product.source_url).path.replace("-", " "),
            product.image_title,
        ]
    ).lower()
    text_tokens = set(_tokens(text))
    score = 0

    for term in _category_terms(category):
        term_text = term.lower().replace("-", " ").strip()
        term_tokens = _tokens(term_text)
        if not term_tokens:
            continue
        if len(term_tokens) > 1 and term_text in text:
            score += 5
        score += 2 * sum(1 for token in term_tokens if token in text_tokens)

    return score


def build_catalog_manifest(
    products: Iterable[SitemapProduct],
    plan: MaterialBankCategoryPlan,
    *,
    per_category: int | None = None,
) -> CatalogSeedManifest:
    buckets: dict[str, list[ScoredProduct]] = {category.name: [] for category in plan.categories}

    for product in products:
        scored = [
            ScoredProduct(product=product, category=category, score=score)
            for category in plan.categories
            if (score := score_product_for_category(product, category)) > 0
        ]
        if not scored:
            continue

        best = max(
            scored,
            key=lambda candidate: (candidate.score, -plan.categories.index(candidate.category)),
        )
        buckets[best.category.name].append(best)

    items: list[CatalogItemCreate] = []
    seen_images: set[str] = set()
    seen_source_urls: set[str] = set()
    item_name_counts: dict[tuple[str, str, str], int] = {}

    for category in plan.categories:
        target = per_category or category.per_category or plan.default_per_category
        ranked = sorted(
            buckets[category.name],
            key=lambda candidate: (-candidate.score, candidate.product.source_order),
        )
        category_rank = 0

        for candidate in ranked:
            product = candidate.product
            dedupe_url = _canonical_source_url(product.source_url)
            if product.image_url in seen_images or dedupe_url in seen_source_urls:
                continue

            category_rank += 1
            seen_images.add(product.image_url)
            seen_source_urls.add(dedupe_url)
            items.append(
                _catalog_item_from_product(
                    product,
                    category=category,
                    rank=category_rank,
                    score=candidate.score,
                    item_name_counts=item_name_counts,
                )
            )

            if category_rank >= target:
                break

    return CatalogSeedManifest(items=items)


def fetch_material_bank_products(
    *,
    sitemap_index_url: str = DEFAULT_SITEMAP_INDEX_URL,
    max_sitemaps: int | None = None,
    timeout_seconds: float = 20.0,
    request_pause_seconds: float = 0.05,
) -> list[SitemapProduct]:
    headers = {"User-Agent": USER_AGENT}
    products: list[SitemapProduct] = []
    next_order = 0

    with httpx.Client(headers=headers, follow_redirects=True, timeout=timeout_seconds) as client:
        sitemap_index = client.get(sitemap_index_url)
        sitemap_index.raise_for_status()
        sitemap_urls = parse_sitemap_index(sitemap_index.text)
        if max_sitemaps is not None:
            sitemap_urls = sitemap_urls[:max_sitemaps]

        for index, sitemap_url in enumerate(sitemap_urls, start=1):
            response = client.get(sitemap_url)
            response.raise_for_status()
            page_products = parse_product_sitemap(response.text, start_order=next_order)
            products.extend(page_products)
            next_order += len(page_products)
            print(f"Fetched sitemap {index}/{len(sitemap_urls)}: {len(page_products)} products")
            if request_pause_seconds > 0:
                sleep(request_pause_seconds)

    return products


def write_manifest(manifest: CatalogSeedManifest, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(manifest.model_dump(mode="json"), indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )


def category_counts(manifest: CatalogSeedManifest) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in manifest.items:
        category_name = str(item.metadata.get("source_category", "Uncategorized"))
        counts[category_name] = counts.get(category_name, 0) + 1
    return counts


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build a demo catalog seed from Material Bank's public product sitemap."
    )
    parser.add_argument(
        "--category-plan",
        type=Path,
        default=DEFAULT_CATEGORY_PLAN_PATH,
        help="Path to the category scope JSON file.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Path to write the generated catalog seed manifest.",
    )
    parser.add_argument(
        "--per-category",
        type=int,
        default=None,
        help="Override the category plan's per-category item limit.",
    )
    parser.add_argument(
        "--sitemap-index-url",
        default=DEFAULT_SITEMAP_INDEX_URL,
        help="Material Bank sitemap index URL.",
    )
    parser.add_argument(
        "--max-sitemaps",
        type=int,
        default=None,
        help="Limit child sitemaps fetched; useful for quick smoke tests.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=20.0,
        help="HTTP timeout for sitemap requests.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch and summarize without writing the manifest.",
    )
    args = parser.parse_args(argv)

    plan = load_category_plan(args.category_plan)
    products = fetch_material_bank_products(
        sitemap_index_url=args.sitemap_index_url,
        max_sitemaps=args.max_sitemaps,
        timeout_seconds=args.timeout_seconds,
    )
    manifest = build_catalog_manifest(products, plan, per_category=args.per_category)

    print(f"Matched catalog items: {len(manifest.items)}")
    for category in plan.categories:
        count = category_counts(manifest).get(category.name, 0)
        target = args.per_category or category.per_category or plan.default_per_category
        print(f"- {category.name}: {count}/{target}")

    if args.dry_run:
        return 0

    write_manifest(manifest, args.output)
    print(f"Wrote {args.output}")
    return 0


def _catalog_item_from_product(
    product: SitemapProduct,
    *,
    category: MaterialBankCategory,
    rank: int,
    score: int,
    item_name_counts: dict[tuple[str, str, str], int],
) -> CatalogItemCreate:
    manufacturer = _manufacturer_from_slug(product.source_url, product.image_title)
    name = product.image_title or _name_from_slug(product.source_url)
    dedupe_key = (category.name, manufacturer, name)
    item_name_counts[dedupe_key] = item_name_counts.get(dedupe_key, 0) + 1
    if item_name_counts[dedupe_key] > 1:
        active_child = parse_qs(urlparse(product.source_url).query).get("activeChild", [""])[0]
        suffix = active_child or str(item_name_counts[dedupe_key])
        name = f"{name} - Variant {suffix}"

    return CatalogItemCreate(
        manufacturer=manufacturer,
        name=name,
        material_family=category.material_family,
        image_object_key=_image_object_key(
            product,
            category=category,
            manufacturer=manufacturer,
            name=name,
        ),
        image_url=product.image_url,
        metadata={
            "source_platform": "material_bank",
            "source_url": product.source_url,
            "source_category_group": category.group,
            "source_category": category.name,
            "source_taxonomy_path": " > ".join(category.taxonomy_path),
            "source_rank": rank,
            "source_match_score": score,
            "source_lastmod": product.lastmod,
            "import_strategy": "public_sitemap_category_terms",
            "image_kind": "public_catalog_product_image",
            "materials": _metadata_materials(category),
            "visual_tags": _visual_tags(category),
        },
    )


def _category_terms(category: MaterialBankCategory) -> list[str]:
    return [category.name, category.material_family, *category.aliases]


def _metadata_materials(category: MaterialBankCategory) -> list[str]:
    return list(
        dict.fromkeys([category.material_family, category.name.lower(), *category.aliases[:4]])
    )


def _visual_tags(category: MaterialBankCategory) -> list[str]:
    return list(
        dict.fromkeys([category.name.lower(), category.material_family, *category.aliases[:6]])
    )


def _node_text(node: ElementTree.Element, path: str) -> str | None:
    child = node.find(path, SITEMAP_NS)
    if child is None or child.text is None:
        return None
    return _clean_whitespace(child.text)


def _looks_like_product_url(source_url: str) -> bool:
    parsed = urlparse(source_url)
    if parsed.netloc != "www.materialbank.com":
        return False
    path = parsed.path.strip("/")
    if "/" in path:
        return False
    return bool(PRODUCT_PATH_PATTERN.match(path))


def _catalog_slug(source_url: str) -> str:
    return urlparse(source_url).path.strip("/")


def _name_from_slug(source_url: str) -> str:
    slug = re.sub(r"-\d+$", "", _catalog_slug(source_url))
    return _title_from_slug(slug)


def _manufacturer_from_slug(source_url: str, image_title: str) -> str:
    slug = re.sub(r"-\d+$", "", _catalog_slug(source_url))
    slug_tokens = slug.split("-")
    title_tokens = _slugify(image_title).split("-") if image_title else []

    if title_tokens and len(slug_tokens) > len(title_tokens):
        suffix = slug_tokens[-len(title_tokens) :]
        if suffix == title_tokens:
            manufacturer_tokens = slug_tokens[: -len(title_tokens)]
            return _title_from_slug("-".join(manufacturer_tokens))

    return _title_from_slug("-".join(slug_tokens[:2] or ["Material", "Bank"]))


def _image_object_key(
    product: SitemapProduct,
    *,
    category: MaterialBankCategory,
    manufacturer: str,
    name: str,
) -> str:
    parsed_image = urlparse(product.image_url)
    extension = Path(parsed_image.path).suffix or ".jpg"
    source_id_match = re.search(r"(\d+)(?:\.\w+)?$", parsed_image.path)
    source_id = (
        source_id_match.group(1)
        if source_id_match
        else _slugify(_catalog_slug(product.source_url))
    )
    return (
        "catalog/material-bank-public/"
        f"{_slugify(category.name)}/"
        f"{_slugify(manufacturer)}-{_slugify(name)}-{source_id}{extension}"
    )


def _canonical_source_url(source_url: str) -> str:
    parsed = urlparse(source_url)
    active_child = parse_qs(parsed.query).get("activeChild", [""])[0]
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}?activeChild={active_child}"


def _without_query(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"


def _clean_whitespace(value: str) -> str:
    return " ".join(value.split())


def _tokens(value: str) -> list[str]:
    return TOKEN_PATTERN.findall(value.lower())


def _slugify(value: str) -> str:
    return "-".join(_tokens(value))


def _title_from_slug(value: str) -> str:
    return " ".join(
        token.upper() if token.isdigit() else token.capitalize() for token in value.split("-")
    )


if __name__ == "__main__":
    raise SystemExit(main())
