from fastapi.testclient import TestClient

from app.main import create_app
from app.model_services.factory import get_sam3_client
from app.model_services.segmentation import SegmentationRegion, SegmentationResult


class FakeSam3Client:
    def __init__(self):
        self.calls: list[dict] = []

    def segment_image(self, **kwargs) -> SegmentationResult:
        self.calls.append(kwargs)
        return SegmentationResult(
            model_id="facebook/sam3",
            image_width=320,
            image_height=240,
            prompt=kwargs["prompt"],
            regions=[
                SegmentationRegion(
                    id="sam3_region_0",
                    prompt=kwargs["prompt"],
                    score=0.93,
                    box_xyxy=[1.0, 2.0, 101.0, 122.0],
                )
            ],
        )


def test_raw_sam3_playground_endpoint_returns_direct_segmentation():
    app = create_app()
    sam3_client = FakeSam3Client()
    app.dependency_overrides[get_sam3_client] = lambda: sam3_client

    response = TestClient(app).post(
        "/dev/sam3/segment",
        json={
            "image_object_key": "uploads/run/reference.jpg",
            "prompt": "green upholstery",
            "confidence_threshold": 0.42,
            "max_regions": 3,
            "include_masks": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["model_id"] == "facebook/sam3"
    assert payload["image_width"] == 320
    assert payload["regions"][0]["id"] == "sam3_region_0"
    assert sam3_client.calls == [
        {
            "prompt": "green upholstery",
            "image_object_key": "uploads/run/reference.jpg",
            "image_url": None,
            "confidence_threshold": 0.42,
            "max_regions": 3,
            "include_masks": True,
        }
    ]


def test_raw_sam3_playground_endpoint_requires_image_source():
    app = create_app()
    app.dependency_overrides[get_sam3_client] = lambda: FakeSam3Client()

    response = TestClient(app).post(
        "/dev/sam3/segment",
        json={"prompt": "chair"},
    )

    assert response.status_code == 422
