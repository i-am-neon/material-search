from io import BytesIO

from PIL import Image, ImageDraw

from app.catalog.filter_manifest import analyze_image, filter_manifest, is_paint_object_photo
from app.catalog.load_seed import CatalogSeedManifest
from app.catalog.schemas import CatalogItemCreate


def test_paint_object_photo_detects_can_on_white_background():
    image = Image.new("RGB", (256, 256), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((70, 55, 185, 215), fill=(70, 70, 78), outline=(20, 20, 20), width=3)
    draw.rectangle((83, 105, 172, 160), fill=(240, 240, 240), outline=(10, 10, 10), width=2)
    for y in range(112, 154, 8):
        draw.line((92, y, 162, y), fill=(30, 30, 30), width=2)

    assert is_paint_object_photo(analyze_image(_image_bytes(image)))


def test_paint_object_photo_keeps_flat_color_swatch():
    image = Image.new("RGB", (256, 256), (180, 138, 96))

    assert not is_paint_object_photo(analyze_image(_image_bytes(image)))


def test_filter_manifest_removes_paint_object_photos():
    can = Image.new("RGB", (256, 256), "white")
    draw = ImageDraw.Draw(can)
    draw.rectangle((70, 55, 185, 215), fill=(70, 70, 78), outline=(20, 20, 20), width=3)
    draw.rectangle((83, 105, 172, 160), fill=(240, 240, 240), outline=(10, 10, 10), width=2)
    swatch = Image.new("RGB", (256, 256), (52, 83, 67))
    images = {
        "https://example.com/can.jpg": _image_bytes(can),
        "https://example.com/swatch.jpg": _image_bytes(swatch),
    }
    manifest = CatalogSeedManifest(
        items=[
            _item("Paint Can", "https://example.com/can.jpg"),
            _item("Pine - Paint Finish", "https://example.com/swatch.jpg"),
        ]
    )

    result = filter_manifest(manifest, fetch_image=lambda url: images[url])

    assert result.removed["paint_object_photo"] == 1
    assert [item.name for item in result.manifest.items] == ["Pine - Paint Finish"]


def _item(name: str, image_url: str) -> CatalogItemCreate:
    return CatalogItemCreate(
        manufacturer="Maker",
        name=name,
        material_family="paint",
        image_object_key=f"catalog/maker/{name}.jpg",
        image_url=image_url,
        metadata={"source_category": "Paints"},
    )


def _image_bytes(image: Image.Image) -> bytes:
    output = BytesIO()
    image.save(output, format="JPEG")
    return output.getvalue()
