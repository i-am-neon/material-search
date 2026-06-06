import pytest

from app.model_services.segmentation import HttpSam3Client, SegmentationRegion


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
