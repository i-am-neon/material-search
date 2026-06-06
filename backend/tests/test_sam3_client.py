import pytest

from app.model_services.segmentation import (
    HttpSam3Client,
    SegmentationRegion,
)


def test_segmentation_region_requires_box_coordinates():
    with pytest.raises(ValueError):
        SegmentationRegion(id="region-1", prompt="chair", score=0.9, box_xyxy=[1.0, 2.0])


def test_http_sam3_client_posts_segment_request(monkeypatch):
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "model_id": "facebook/sam3",
                "image_width": 640,
                "image_height": 480,
                "prompt": "shoe",
                "regions": [
                    {
                        "id": "sam3_region_0",
                        "prompt": "shoe",
                        "score": 0.91,
                        "box_xyxy": [10.0, 12.0, 100.0, 120.0],
                    }
                ],
            }

    def fake_post(url, *, json, timeout, follow_redirects):
        captured["url"] = url
        captured["json"] = json
        captured["timeout"] = timeout
        captured["follow_redirects"] = follow_redirects
        return FakeResponse()

    monkeypatch.setattr("app.model_services.segmentation.httpx.post", fake_post)

    result = HttpSam3Client("https://sam3.example.com").segment_image(
        prompt="shoe",
        image_url="https://example.com/image.jpg",
        confidence_threshold=0.4,
        max_regions=3,
    )

    assert captured["url"] == "https://sam3.example.com/segment-image"
    assert captured["follow_redirects"] is True
    assert captured["json"] == {
        "prompt": "shoe",
        "image_object_key": None,
        "image_url": "https://example.com/image.jpg",
        "confidence_threshold": 0.4,
        "max_regions": 3,
        "include_masks": False,
    }
    assert result.regions[0].score == 0.91


def test_http_sam3_client_signs_uploaded_object_keys(monkeypatch):
    calls = []

    class FakeResponse:
        def __init__(self, payload):
            self.payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self.payload

    def fake_post(url, **kwargs):
        calls.append({"url": url, **kwargs})
        if "/storage/v1/object/sign/" in url:
            return FakeResponse(
                {"signedURL": "/object/sign/uploaded-images/uploads/run/ref.png?t=1"}
            )
        return FakeResponse(
            {
                "model_id": "facebook/sam3",
                "image_width": 640,
                "image_height": 480,
                "prompt": "green upholstery",
                "regions": [
                    {
                        "id": "sam3_region_0",
                        "prompt": "green upholstery",
                        "score": 0.91,
                        "box_xyxy": [10.0, 12.0, 100.0, 120.0],
                    }
                ],
            }
        )

    monkeypatch.setattr("app.model_services.segmentation.httpx.post", fake_post)

    HttpSam3Client(
        "https://sam3.example.com",
        supabase_url="https://project.supabase.co",
        service_role_key="service-role",
    ).segment_image(
        prompt="green upholstery",
        image_object_key="uploads/run/ref.png",
    )

    assert calls[0]["url"] == (
        "https://project.supabase.co/storage/v1/object/sign/"
        "uploaded-images/uploads/run/ref.png"
    )
    assert calls[0]["headers"]["authorization"] == "Bearer service-role"
    assert calls[1]["url"] == "https://sam3.example.com/segment-image"
    assert calls[1]["json"]["image_object_key"] is None
    assert calls[1]["json"]["image_url"] == (
        "https://project.supabase.co/storage/v1"
        "/object/sign/uploaded-images/uploads/run/ref.png?t=1"
    )


def test_http_sam3_client_rejects_wrong_model(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "model_id": "not-sam3",
                "image_width": 640,
                "image_height": 480,
                "prompt": "shoe",
                "regions": [],
            }

    monkeypatch.setattr(
        "app.model_services.segmentation.httpx.post",
        lambda *args, **kwargs: FakeResponse(),
    )

    with pytest.raises(ValueError, match="model_id"):
        HttpSam3Client("https://sam3.example.com").segment_image(
            prompt="shoe",
            image_url="https://example.com/image.jpg",
        )


def test_http_sam3_client_rejects_too_many_regions(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "model_id": "facebook/sam3",
                "image_width": 640,
                "image_height": 480,
                "prompt": "shoe",
                "regions": [
                    {
                        "id": "sam3_region_0",
                        "prompt": "shoe",
                        "score": 0.91,
                        "box_xyxy": [10.0, 12.0, 100.0, 120.0],
                    },
                    {
                        "id": "sam3_region_1",
                        "prompt": "shoe",
                        "score": 0.88,
                        "box_xyxy": [110.0, 12.0, 200.0, 120.0],
                    },
                ],
            }

    monkeypatch.setattr(
        "app.model_services.segmentation.httpx.post",
        lambda *args, **kwargs: FakeResponse(),
    )

    with pytest.raises(ValueError, match="expected at most 1"):
        HttpSam3Client("https://sam3.example.com").segment_image(
            prompt="shoe",
            image_url="https://example.com/image.jpg",
            max_regions=1,
        )
