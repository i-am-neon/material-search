import argparse
import html
import json
from collections import Counter, defaultdict
from collections.abc import Sequence
from pathlib import Path

from app.catalog.load_seed import DEFAULT_MANIFEST_PATH, load_manifest
from app.catalog.schemas import CatalogItemCreate

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DEMO_MANIFEST_PATH = REPO_ROOT / "data" / "catalog" / "material-bank-public-demo-seed.json"
DEFAULT_GALLERY_PATH = REPO_ROOT / "data" / "catalog" / "material-bank-public-demo-gallery.html"


def build_gallery_html(items: list[CatalogItemCreate], *, title: str) -> str:
    category_counts = Counter(_category_name(item) for item in items)
    categories = sorted(category_counts)
    payload = [_gallery_item_payload(item) for item in items]

    return "\n".join(
        [
            "<!doctype html>",
            '<html lang="en">',
            "<head>",
            '<meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            f"<title>{html.escape(title)}</title>",
            "<style>",
            _css(),
            "</style>",
            "</head>",
            "<body>",
            "<header>",
            f"<h1>{html.escape(title)}</h1>",
            (
                f"<p>{len(items)} catalog images across {len(categories)} categories. "
                "Use search or category filters to review scrape quality "
                "before loading/indexing.</p>"
            ),
            '<div class="controls">',
            (
                '<input id="search" type="search" '
                'placeholder="Search name, manufacturer, category..." autocomplete="off">'
            ),
            '<select id="category">',
            '<option value="">All categories</option>',
            *[
                (
                    f'<option value="{html.escape(category)}">'
                    f"{html.escape(category)} ({category_counts[category]})"
                    "</option>"
                )
                for category in categories
            ],
            "</select>",
            "</div>",
            '<div id="summary" class="summary"></div>',
            "</header>",
            '<main id="grid" class="grid"></main>',
            '<script type="application/json" id="items-data">',
            html.escape(json.dumps(payload), quote=False),
            "</script>",
            "<script>",
            _javascript(),
            "</script>",
            "</body>",
            "</html>",
        ]
    )


def write_gallery(items: list[CatalogItemCreate], *, output_path: Path, title: str) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(build_gallery_html(items, title=title), encoding="utf-8")


def category_counts(items: list[CatalogItemCreate]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for item in items:
        counts[_category_name(item)] += 1
    return dict(sorted(counts.items()))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a scan-friendly catalog image gallery.")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=(
            DEFAULT_DEMO_MANIFEST_PATH
            if DEFAULT_DEMO_MANIFEST_PATH.exists()
            else DEFAULT_MANIFEST_PATH
        ),
        help="Path to a catalog seed JSON manifest.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_GALLERY_PATH,
        help="Path to write the generated HTML gallery.",
    )
    parser.add_argument(
        "--title",
        default="Material Bank demo catalog gallery",
        help="Gallery page title.",
    )
    args = parser.parse_args(argv)

    manifest = load_manifest(args.manifest)
    write_gallery(manifest.items, output_path=args.output, title=args.title)

    print(f"Catalog gallery items: {len(manifest.items)}")
    for category, count in category_counts(manifest.items).items():
        print(f"- {category}: {count}")
    print(f"Wrote {args.output}")
    return 0


def _gallery_item_payload(item: CatalogItemCreate) -> dict[str, str]:
    category = _category_name(item)
    return {
        "category": category,
        "manufacturer": item.manufacturer,
        "name": item.name,
        "family": item.material_family or "",
        "imageUrl": str(item.image_url) if item.image_url else "",
        "productUrl": str(item.metadata.get("source_url", "")),
        "rank": str(item.metadata.get("source_rank", "")),
        "searchText": " ".join(
            [
                category,
                item.manufacturer,
                item.name,
                item.material_family or "",
                " ".join(str(tag) for tag in item.metadata.get("visual_tags", [])),
            ]
        ).lower(),
    }


def _category_name(item: CatalogItemCreate) -> str:
    return str(item.metadata.get("source_category") or item.material_family or "Uncategorized")


def _css() -> str:
    return """
:root {
  color-scheme: light;
  --bg: #f5f3ee;
  --panel: #ffffff;
  --line: #ded8ce;
  --ink: #171717;
  --muted: #625d53;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--ink);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
header {
  position: sticky;
  top: 0;
  z-index: 2;
  padding: 18px 24px;
  border-bottom: 1px solid var(--line);
  background: rgba(245, 243, 238, 0.94);
  backdrop-filter: blur(8px);
}
h1 {
  margin: 0 0 4px;
  font-size: 22px;
  line-height: 1.2;
}
p {
  margin: 0;
  color: var(--muted);
}
.controls {
  display: grid;
  grid-template-columns: minmax(220px, 1fr) minmax(180px, 260px);
  gap: 10px;
  margin-top: 14px;
}
input,
select {
  width: 100%;
  min-height: 40px;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: #fff;
  color: var(--ink);
  font: inherit;
  padding: 8px 10px;
}
.summary {
  margin-top: 10px;
  color: var(--muted);
  font-size: 13px;
}
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 16px;
  padding: 20px 24px 32px;
}
.card {
  display: block;
  overflow: hidden;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--panel);
  color: inherit;
  text-decoration: none;
}
.image-wrap {
  display: flex;
  align-items: center;
  justify-content: center;
  aspect-ratio: 1 / 1;
  background: #ebe6dc;
}
.image-wrap img {
  width: 100%;
  height: 100%;
  object-fit: contain;
}
.meta {
  padding: 12px;
}
.category {
  color: #766f63;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}
.name {
  margin-top: 5px;
  font-size: 15px;
  line-height: 1.25;
}
.manufacturer {
  margin-top: 6px;
  color: var(--muted);
  font-size: 13px;
}
.rank {
  margin-top: 8px;
  color: var(--muted);
  font-size: 12px;
}
@media (max-width: 640px) {
  header { padding: 16px; }
  .controls { grid-template-columns: 1fr; }
  .grid {
    grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
    padding: 16px;
  }
}
""".strip()


def _javascript() -> str:
    return """
const items = JSON.parse(document.getElementById("items-data").textContent);
const grid = document.getElementById("grid");
const summary = document.getElementById("summary");
const search = document.getElementById("search");
const category = document.getElementById("category");

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function render() {
  const query = search.value.trim().toLowerCase();
  const selectedCategory = category.value;
  const visibleItems = items.filter((item) => {
    const matchesCategory = !selectedCategory || item.category === selectedCategory;
    const matchesQuery = !query || item.searchText.includes(query);
    return matchesCategory && matchesQuery;
  });

  summary.textContent = `${visibleItems.length} visible of ${items.length} total`;
  grid.innerHTML = visibleItems.map((item) => `
    <a class="card"
       href="${escapeHtml(item.productUrl || item.imageUrl)}"
       target="_blank"
       rel="noreferrer">
      <div class="image-wrap">
        <img src="${escapeHtml(item.imageUrl)}" alt="${escapeHtml(item.name)}" loading="lazy">
      </div>
      <div class="meta">
        <div class="category">${escapeHtml(item.category)}</div>
        <div class="name">${escapeHtml(item.name)}</div>
        <div class="manufacturer">${escapeHtml(item.manufacturer)}</div>
        <div class="rank">Rank ${escapeHtml(item.rank || "-")} · ${escapeHtml(item.family)}</div>
      </div>
    </a>
  `).join("");
}

search.addEventListener("input", render);
category.addEventListener("change", render);
render();
""".strip()


if __name__ == "__main__":
    raise SystemExit(main())
