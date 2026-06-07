from app.catalog.build_gallery import build_gallery_html, category_counts, write_gallery
from app.catalog.schemas import CatalogItemCreate


def test_build_gallery_html_contains_filterable_catalog_items():
    items = [
        CatalogItemCreate(
            manufacturer="Tilebar",
            name="Nabi Valor Ceramic Mosaic Tile",
            material_family="tile",
            image_object_key="catalog/tilebar/nabi.jpg",
            image_url="https://example.com/nabi.jpg",
            metadata={
                "source_url": "https://www.materialbank.com/tilebar-nabi-123",
                "source_category": "Tile",
                "source_rank": 1,
                "visual_tags": ["ceramic", "mosaic"],
            },
        )
    ]

    html = build_gallery_html(items, title="Demo Gallery")

    assert "Demo Gallery" in html
    assert "Nabi Valor Ceramic Mosaic Tile" in html
    assert "Tilebar" in html
    assert "Tile (1)" in html
    assert "items-data" in html


def test_write_gallery_writes_html_file(tmp_path):
    output_path = tmp_path / "gallery.html"
    items = [
        CatalogItemCreate(
            manufacturer="Sherwin Williams",
            name="Chalky Finish Paint",
            material_family="paint",
            image_object_key="catalog/sherwin/chalky.jpg",
            image_url="https://example.com/chalky.jpg",
            metadata={"source_category": "Paints"},
        )
    ]

    write_gallery(items, output_path=output_path, title="Paint Gallery")

    assert output_path.read_text(encoding="utf-8").startswith("<!doctype html>")


def test_category_counts_uses_source_category_before_material_family():
    items = [
        CatalogItemCreate(
            manufacturer="Maker",
            name="Name",
            material_family="tile",
            image_object_key="catalog/maker/name.jpg",
            image_url="https://example.com/name.jpg",
            metadata={"source_category": "Tile"},
        ),
        CatalogItemCreate(
            manufacturer="Maker",
            name="Name 2",
            material_family="tile",
            image_object_key="catalog/maker/name-2.jpg",
            image_url="https://example.com/name-2.jpg",
            metadata={},
        ),
    ]

    assert category_counts(items) == {"Tile": 1, "tile": 1}
