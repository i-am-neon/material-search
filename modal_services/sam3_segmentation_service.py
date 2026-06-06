import os
from functools import lru_cache
from io import BytesIO
from urllib.parse import quote

import modal

MODEL_ID = "facebook/sam3"

image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("git")
    .pip_install(
        "einops==0.8.1",
        "fastapi[standard]==0.124.4",
        "httpx==0.28.1",
        "pillow==12.0.0",
        "setuptools<81",
        "torch==2.10.0",
        "torchvision",
        "git+https://github.com/facebookresearch/sam3.git",
    )
)

app = modal.App("material-search-sam3-segmentation")


@lru_cache(maxsize=1)
def get_model():
    import torch
    from sam3.model_builder import build_sam3_image_model

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = build_sam3_image_model(device=device)
    return model, device


def resolve_image_request(image_object_key: str | None, image_url: str | None) -> tuple[str, dict]:
    if image_url:
        return image_url, {}

    if not image_object_key:
        raise ValueError("Either image_url or image_object_key is required")

    supabase_url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    bucket = os.environ.get("SAM3_IMAGE_BUCKET", "uploaded-images")
    service_role_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not supabase_url:
        raise ValueError("SUPABASE_URL is required when image_url is not provided")

    key = quote(image_object_key.lstrip("/"), safe="/")
    headers = {}
    if service_role_key:
        url = f"{supabase_url}/storage/v1/object/{bucket}/{key}"
        headers["Authorization"] = f"Bearer {service_role_key}"
    else:
        url = f"{supabase_url}/storage/v1/object/public/{bucket}/{key}"
    return url, headers


def load_image(image_object_key: str | None, image_url: str | None):
    import httpx
    from PIL import Image

    url, headers = resolve_image_request(image_object_key, image_url)
    response = httpx.get(url, headers=headers, timeout=30.0, follow_redirects=True)
    response.raise_for_status()
    return Image.open(BytesIO(response.content)).convert("RGB")


def encode_uncompressed_rle(mask) -> dict:
    import numpy as np

    array = np.asarray(mask, dtype=np.uint8)
    height, width = array.shape
    pixels = array.reshape(-1)
    counts: list[int] = []
    current = 0
    run_length = 0
    for value in pixels:
        value = int(value)
        if value == current:
            run_length += 1
        else:
            counts.append(run_length)
            current = value
            run_length = 1
    counts.append(run_length)
    return {"format": "uncompressed_rle", "size": [height, width], "counts": counts}


def clamp_box(box: list[float], width: int, height: int) -> list[float]:
    x0, y0, x1, y1 = box
    return [
        max(0.0, min(float(width), float(x0))),
        max(0.0, min(float(height), float(y0))),
        max(0.0, min(float(width), float(x1))),
        max(0.0, min(float(height), float(y1))),
    ]


@app.function(
    image=image,
    gpu="T4",
    timeout=300,
    scaledown_window=300,
    secrets=[
        modal.Secret.from_name(
            "material-search-sam3-env",
            required_keys=["HF_TOKEN"],
        )
    ],
)
@modal.asgi_app()
def fastapi_app():
    import torch
    from fastapi import FastAPI, HTTPException
    from pydantic import BaseModel, Field
    from sam3.model.sam3_image_processor import Sam3Processor

    api = FastAPI(title="Material Search SAM3 Segmentation Service")

    class SegmentImageRequest(BaseModel):
        image_object_key: str | None = None
        image_url: str | None = None
        prompt: str = Field(min_length=1)
        confidence_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
        max_regions: int = Field(default=20, ge=1, le=100)
        include_masks: bool = False

    @api.get("/healthz")
    def healthcheck() -> dict[str, str]:
        return {"status": "ok", "model_id": MODEL_ID}

    @api.post("/segment-image")
    def segment_image(request: SegmentImageRequest) -> dict:
        try:
            pil_image = load_image(request.image_object_key, request.image_url)
            width, height = pil_image.size
            model, device = get_model()
            processor = Sam3Processor(
                model,
                device=device,
                confidence_threshold=request.confidence_threshold,
            )
            state = processor.set_image(pil_image)
            output = processor.set_text_prompt(prompt=request.prompt, state=state)

            scores = output["scores"].detach().cpu().float()
            boxes = output["boxes"].detach().cpu().float()
            masks = output["masks"].detach().cpu() if request.include_masks else None
            order = torch.argsort(scores, descending=True)[: request.max_regions]

            regions = []
            for output_index, tensor_index in enumerate(order.tolist()):
                region = {
                    "id": f"sam3_region_{output_index}",
                    "prompt": request.prompt,
                    "score": float(scores[tensor_index].item()),
                    "box_xyxy": clamp_box(boxes[tensor_index].tolist(), width, height),
                }
                if masks is not None:
                    mask = masks[tensor_index].squeeze().numpy()
                    region["mask"] = encode_uncompressed_rle(mask)
                regions.append(region)
        except Exception as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        return {
            "model_id": MODEL_ID,
            "image_width": width,
            "image_height": height,
            "prompt": request.prompt,
            "regions": regions,
        }

    return api
