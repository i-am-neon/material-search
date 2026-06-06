import argparse
import json

from app.model_services.factory import get_sam3_client

DEFAULT_SMOKE_IMAGE_URL = (
    "https://raw.githubusercontent.com/facebookresearch/sam3/main/assets/images/test_image.jpg"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Call the configured SAM3 service.")
    parser.add_argument("--image-url", default=DEFAULT_SMOKE_IMAGE_URL)
    parser.add_argument("--image-object-key", default=None)
    parser.add_argument("--prompt", default="shoe")
    parser.add_argument("--confidence-threshold", type=float, default=0.5)
    parser.add_argument("--max-regions", type=int, default=20)
    parser.add_argument("--include-masks", action="store_true")
    parser.add_argument("--min-regions", type=int, default=1)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = get_sam3_client().segment_image(
        prompt=args.prompt,
        image_object_key=args.image_object_key,
        image_url=args.image_url,
        confidence_threshold=args.confidence_threshold,
        max_regions=args.max_regions,
        include_masks=args.include_masks,
    )
    if len(result.regions) < args.min_regions:
        raise RuntimeError(
            f"SAM3 smoke expected at least {args.min_regions} region(s), got {len(result.regions)}"
        )
    print(
        json.dumps(
            {
                "model_id": result.model_id,
                "prompt": result.prompt,
                "image_width": result.image_width,
                "image_height": result.image_height,
                "region_count": len(result.regions),
                "top_region": result.regions[0].model_dump(exclude={"mask"})
                if result.regions
                else None,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
