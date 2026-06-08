import json
from pathlib import Path

from app.catalog.material_bank_import import (
    build_catalog_manifest,
    load_category_plan,
    parse_product_sitemap,
    parse_sitemap_index,
    score_product_for_category,
)


def test_load_category_plan_contains_demo_scope():
    plan = load_category_plan(
        Path("..") / "data" / "catalog" / "material-bank-demo-categories.json"
    )

    assert [category.name for category in plan.categories] == [
        "Tile",
        "Paints",
        "Surfaces",
        "Flooring",
        "Textiles",
        "Leather",
        "Wallcovering",
        "Masonry & Stone",
        "Paneling",
        "Bathroom",
        "Kitchen",
        "Hardware",
        "Lighting",
        "Furniture",
    ]
    assert plan.default_per_category == 50


def test_parse_sitemap_index_reads_child_urls():
    sitemap_index = """<?xml version="1.0" encoding="UTF-8"?>
    <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <sitemap><loc>https://www.materialbank.com/media/sitemap-1-1.xml</loc></sitemap>
      <sitemap><loc>https://www.materialbank.com/media/sitemap-1-2.xml</loc></sitemap>
    </sitemapindex>
    """

    assert parse_sitemap_index(sitemap_index) == [
        "https://www.materialbank.com/media/sitemap-1-1.xml",
        "https://www.materialbank.com/media/sitemap-1-2.xml",
    ]


def test_parse_product_sitemap_keeps_only_product_rows_with_images():
    product_sitemap = """<?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
            xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">
      <url>
        <loc>https://www.materialbank.com/categories/materials/tile</loc>
      </url>
      <url>
        <loc>https://www.materialbank.com/clay-imports-terracotta-field-tile-123456</loc>
        <lastmod>2026-06-07T09:12:32+00:00</lastmod>
        <image:image>
          <image:loc>https://materialbank-cdn.freetls.fastly.net/media/catalog/product/base_image/1/1001.jpg?quality=80&amp;width=</image:loc>
          <image:title>Terracotta Field Tile</image:title>
        </image:image>
      </url>
    </urlset>
    """

    products = parse_product_sitemap(product_sitemap)

    assert len(products) == 1
    assert products[0].image_url.endswith("/1001.jpg")
    assert products[0].image_title == "Terracotta Field Tile"
    assert products[0].lastmod == "2026-06-07T09:12:32+00:00"


def test_build_catalog_manifest_assigns_products_to_best_category(tmp_path):
    plan_path = tmp_path / "categories.json"
    plan_path.write_text(
        json.dumps(
            {
                "source": "test",
                "default_per_category": 2,
                "categories": [
                    {
                        "group": "Materials",
                        "name": "Tile",
                        "taxonomy_path": ["Materials", "Tile"],
                        "material_family": "tile",
                        "aliases": ["tile", "terracotta"],
                    },
                    {
                        "group": "FF&E",
                        "name": "Lighting",
                        "taxonomy_path": ["FF&E", "Lighting"],
                        "material_family": "lighting",
                        "aliases": ["pendant", "sconce", "light"],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    plan = load_category_plan(plan_path)
    products = parse_product_sitemap(
        """<?xml version="1.0" encoding="UTF-8"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
                xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">
          <url>
            <loc>https://www.materialbank.com/clay-imports-terracotta-field-tile-123456</loc>
            <image:image>
              <image:loc>https://materialbank-cdn.freetls.fastly.net/media/catalog/product/base_image/1/1001.jpg?quality=80</image:loc>
              <image:title>Terracotta Field Tile</image:title>
            </image:image>
          </url>
          <url>
            <loc>https://www.materialbank.com/modern-forms-brass-pendant-light-789012?activeChild=333</loc>
            <image:image>
              <image:loc>https://materialbank-cdn.freetls.fastly.net/media/catalog/product/base_image/1/2002.jpg?quality=80</image:loc>
              <image:title>Brass Pendant Light</image:title>
            </image:image>
          </url>
        </urlset>
        """
    )

    manifest = build_catalog_manifest(products, plan)

    assert len(manifest.items) == 2
    tile_item = manifest.items[0]
    lighting_item = manifest.items[1]
    assert tile_item.manufacturer == "Clay Imports"
    assert tile_item.name == "Terracotta Field Tile"
    assert tile_item.material_family == "tile"
    assert tile_item.metadata["source_category"] == "Tile"
    assert tile_item.image_object_key.endswith("clay-imports-terracotta-field-tile-1001.jpg")
    assert lighting_item.manufacturer == "Modern Forms"
    assert lighting_item.metadata["source_category"] == "Lighting"


def test_score_product_for_category_does_not_match_textile_as_tile(tmp_path):
    plan_path = tmp_path / "categories.json"
    plan_path.write_text(
        json.dumps(
            {
                "categories": [
                    {
                        "group": "Materials",
                        "name": "Tile",
                        "taxonomy_path": ["Materials", "Tile"],
                        "material_family": "tile",
                        "aliases": ["tile"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    category = load_category_plan(plan_path).categories[0]
    product = parse_product_sitemap(
        """<?xml version="1.0" encoding="UTF-8"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
                xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">
          <url>
            <loc>https://www.materialbank.com/kravet-contract-woven-textile-123456</loc>
            <image:image>
              <image:loc>https://materialbank-cdn.freetls.fastly.net/media/catalog/product/base_image/1/1001.jpg</image:loc>
              <image:title>Woven Textile</image:title>
            </image:image>
          </url>
        </urlset>
        """
    )[0]

    assert score_product_for_category(product, category) == 0
