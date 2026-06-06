import pytest
from PIL import Image

from app.model_services.segmentation import SegmentationMask, SegmentationRegion
from app.search.artifacts import (
    SupabaseRegionArtifactStore,
    crop_region_image,
    decode_uncompressed_rle_mask,
)


def test_crop_region_image_uses_sam3_box():
    image = Image.new("RGB", (4, 4), "white")
    image.putpixel((1, 1), (255, 0, 0))
    image.putpixel((2, 2), (0, 0, 255))
    region = SegmentationRegion(
        id="sam3_region_0",
        prompt="fabric",
        score=0.9,
        box_xyxy=[1.0, 1.0, 3.0, 3.0],
    )

    crop = crop_region_image(image=image, region=region, image_width=4, image_height=4)

    assert crop.size == (2, 2)
    assert crop.getpixel((0, 0)) == (255, 0, 0)
    assert crop.getpixel((1, 1)) == (0, 0, 255)


def test_crop_region_image_applies_optional_mask():
    image = Image.new("RGB", (3, 1), "red")
    region = SegmentationRegion(
        id="sam3_region_0",
        prompt="fabric",
        score=0.9,
        box_xyxy=[0.0, 0.0, 3.0, 1.0],
        mask=SegmentationMask(format="uncompressed_rle", size=[1, 3], counts=[1, 1, 1]),
    )

    crop = crop_region_image(image=image, region=region, image_width=3, image_height=1)

    assert crop.getpixel((0, 0)) == (255, 255, 255)
    assert crop.getpixel((1, 0)) == (255, 0, 0)
    assert crop.getpixel((2, 0)) == (255, 255, 255)


def test_crop_region_image_rejects_empty_box():
    image = Image.new("RGB", (4, 4), "white")
    region = SegmentationRegion(
        id="sam3_region_0",
        prompt="fabric",
        score=0.9,
        box_xyxy=[2.0, 2.0, 2.0, 3.0],
    )

    with pytest.raises(ValueError, match="empty crop box"):
        crop_region_image(image=image, region=region, image_width=4, image_height=4)


def test_decode_uncompressed_rle_mask_rejects_wrong_pixel_count():
    mask = SegmentationMask(format="uncompressed_rle", size=[2, 2], counts=[1, 1])

    with pytest.raises(ValueError, match="expected 4"):
        decode_uncompressed_rle_mask(mask)


def test_supabase_signed_url_prefixes_storage_api_path(monkeypatch):
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "signedURL": "/object/sign/generated-artifacts/runs/run/regions/region/crop.jpg"
                "?token=redacted"
            }

    def fake_post(url, *, headers, json, timeout):
        captured["url"] = url
        captured["json"] = json
        return FakeResponse()

    monkeypatch.setattr("app.search.artifacts.httpx.post", fake_post)

    store = SupabaseRegionArtifactStore(
        supabase_url="https://project.supabase.co",
        service_role_key="service-key",
        uploaded_image_bucket="uploaded-images",
        generated_artifact_bucket="generated-artifacts",
    )

    signed_url = store._create_signed_url(
        bucket="generated-artifacts",
        object_key="runs/run/regions/region/crop.jpg",
    )

    assert captured["url"] == (
        "https://project.supabase.co/storage/v1/object/sign/generated-artifacts/"
        "runs/run/regions/region/crop.jpg"
    )
    assert captured["json"] == {"expiresIn": 3600}
    assert signed_url == (
        "https://project.supabase.co/storage/v1/object/sign/generated-artifacts/"
        "runs/run/regions/region/crop.jpg?token=redacted"
    )
