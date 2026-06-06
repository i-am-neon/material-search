from PIL import Image

from app.model_services.segmentation import SegmentationRegion, SegmentationResult
from app.search.artifacts import crop_region_image


def test_model_smoke_eval_region_and_crop_invariants_for_obvious_target():
    image = Image.new("RGB", (200, 120), "white")
    region = SegmentationRegion(
        id="sam3_region_0",
        prompt="green woven chair upholstery",
        score=0.87,
        box_xyxy=[40.0, 20.0, 140.0, 100.0],
    )
    segmentation = SegmentationResult(
        model_id="facebook/sam3",
        image_width=image.width,
        image_height=image.height,
        prompt=region.prompt,
        regions=[region],
    )

    crop = crop_region_image(
        image=image,
        region=segmentation.regions[0],
        image_width=segmentation.image_width,
        image_height=segmentation.image_height,
    )

    assert segmentation.regions[0].score >= 0.5
    assert 16 <= crop.width <= image.width
    assert 16 <= crop.height <= image.height
    assert crop.width * crop.height >= 1024
