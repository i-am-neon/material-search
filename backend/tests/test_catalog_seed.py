import json

import pytest

from app.catalog.load_seed import load_manifest


def test_load_manifest_validates_seed_items(tmp_path):
    manifest_path = tmp_path / "catalog.json"
    manifest_path.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "manufacturer": "Interface",
                        "name": "Hard Truth - Linen",
                        "material_family": "carpet",
                        "image_object_key": "catalog/interface/hard-truth-linen.jpg",
                        "image_url": "https://materialbank-cdn.freetls.fastly.net/media/catalog/product/base_image/112/102351975.jpg",
                        "metadata": {
                            "image_kind": "square_material_swatch",
                            "visual_tags": ["tufted", "textured loop"],
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    manifest = load_manifest(manifest_path)

    assert len(manifest.items) == 1
    assert manifest.items[0].manufacturer == "Interface"
    assert manifest.items[0].metadata["image_kind"] == "square_material_swatch"


def test_load_manifest_rejects_missing_image_object_key(tmp_path):
    manifest_path = tmp_path / "catalog.json"
    manifest_path.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "manufacturer": "Interface",
                        "name": "Hard Truth - Linen",
                        "material_family": "carpet",
                        "image_url": "https://example.com/swatch.jpg",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="image_object_key"):
        load_manifest(manifest_path)
