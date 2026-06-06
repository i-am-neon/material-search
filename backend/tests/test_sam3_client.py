import httpx
import pytest

from app.model_services.segmentation import (
    FallbackSegmentationClient,
    GeminiBoxSegmentationClient,
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


def test_gemini_box_segmentation_client_returns_regions(monkeypatch):
    calls = []

    class FakeImageResponse:
        content = _png_bytes(width=640, height=480)
        headers = {"content-type": "image/png"}

        def raise_for_status(self):
            return None

    class FakeGeminiResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": (
                                        '{"regions":[{"id":"fabric","score":0.82,'
                                        '"box_xyxy":[10,20,300,220]}]}'
                                    )
                                }
                            ]
                        }
                    }
                ]
            }

    def fake_get(url, **kwargs):
        calls.append(("get", url, kwargs))
        return FakeImageResponse()

    def fake_post(url, **kwargs):
        calls.append(("post", url, kwargs))
        return FakeGeminiResponse()

    monkeypatch.setattr("app.model_services.segmentation.httpx.get", fake_get)
    monkeypatch.setattr("app.model_services.segmentation.httpx.post", fake_post)

    result = GeminiBoxSegmentationClient(api_key="gemini-key").segment_image(
        prompt="green upholstery",
        image_url="https://example.com/room.png",
        confidence_threshold=0.4,
        max_regions=2,
    )

    assert calls[0][0] == "get"
    assert calls[1][0] == "post"
    assert result.model_id == "gemini-3.5-flash-box-segmentation"
    assert result.image_width == 640
    assert result.image_height == 480
    assert result.regions[0].id == "fabric"
    assert result.regions[0].box_xyxy == [10.0, 20.0, 300.0, 220.0]


def test_fallback_segmentation_client_uses_gemini_on_sam3_429():
    class RateLimitedSam3Client:
        def segment_image(self, **kwargs):
            request = httpx.Request("POST", "https://sam3.example.com/segment-image")
            response = httpx.Response(
                429,
                request=request,
                text="modal-http: Webhook failed: workspace billing cycle spend limit reached",
            )
            raise httpx.HTTPStatusError(
                "Client error '429 Too Many Requests'",
                request=request,
                response=response,
            )

    class FallbackClient:
        def segment_image(self, **kwargs):
            return {
                "prompt": kwargs["prompt"],
                "image_object_key": kwargs["image_object_key"],
                "max_regions": kwargs["max_regions"],
            }

    result = FallbackSegmentationClient(
        primary=RateLimitedSam3Client(),
        fallback=FallbackClient(),
    ).segment_image(
        prompt="green upholstery",
        image_object_key="uploads/run/ref.png",
        max_regions=3,
    )

    assert result == {
        "prompt": "green upholstery",
        "image_object_key": "uploads/run/ref.png",
        "max_regions": 3,
    }


def _png_bytes(*, width: int, height: int) -> bytes:
    from io import BytesIO

    from PIL import Image

    buffer = BytesIO()
    Image.new("RGB", (width, height), color=(255, 255, 255)).save(buffer, format="PNG")
    return buffer.getvalue()
