import os
from functools import lru_cache
from io import BytesIO

import modal

MODEL_ID = "google/siglip2-so400m-patch14-384"
DIMENSIONS = 1152

image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install(
        "accelerate==1.12.0",
        "fastapi[standard]==0.124.4",
        "httpx==0.28.1",
        "pillow==12.0.0",
        "torch==2.9.1",
        "transformers==4.57.3",
    )
)

app = modal.App("material-search-siglip-embeddings")


@lru_cache(maxsize=1)
def get_model():
    import torch
    from transformers import AutoImageProcessor, AutoModel

    device = "cuda" if torch.cuda.is_available() else "cpu"
    processor = AutoImageProcessor.from_pretrained(MODEL_ID)
    model = AutoModel.from_pretrained(MODEL_ID)
    model.to(device)
    model.eval()
    return processor, model, device


def resolve_image_url(image_object_key: str | None, image_url: str | None) -> str:
    if image_url:
        return image_url

    if not image_object_key:
        raise ValueError("Either image_url or image_object_key is required")

    supabase_url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    bucket = os.environ.get("CATALOG_IMAGE_BUCKET", "catalog-images")
    if not supabase_url:
        raise ValueError("SUPABASE_URL is required when image_url is not provided")

    key = image_object_key.lstrip("/")
    return f"{supabase_url}/storage/v1/object/public/{bucket}/{key}"


def load_image(image_url: str):
    import httpx
    from PIL import Image

    response = httpx.get(image_url, timeout=30.0, follow_redirects=True)
    response.raise_for_status()
    return Image.open(BytesIO(response.content)).convert("RGB")


def embed_pil_image(pil_image):
    import torch
    import torch.nn.functional as functional

    processor, model, device = get_model()
    inputs = processor(images=pil_image, return_tensors="pt")
    inputs = {key: value.to(device) for key, value in inputs.items()}

    with torch.no_grad():
        features = model.get_image_features(**inputs)
        features = functional.normalize(features, p=2, dim=-1)

    vector = features[0].detach().cpu().float().tolist()
    if len(vector) != DIMENSIONS:
        raise RuntimeError(f"Expected {DIMENSIONS} dimensions, got {len(vector)}")
    return vector


@app.function(
    image=image,
    gpu="T4",
    timeout=120,
    scaledown_window=60,
    secrets=[
        modal.Secret.from_name(
            "material-search-embedding-env",
            required_keys=["SUPABASE_URL", "CATALOG_IMAGE_BUCKET"],
        )
    ],
)
@modal.asgi_app()
def fastapi_app():
    from fastapi import FastAPI, HTTPException
    from pydantic import BaseModel

    api = FastAPI(title="Material Search Embedding Service")

    class EmbedImageRequest(BaseModel):
        image_object_key: str | None = None
        image_url: str | None = None
        model_id: str = MODEL_ID
        dimensions: int = DIMENSIONS

    @api.get("/healthz")
    def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    @api.post("/embed-image")
    def embed_image(request: EmbedImageRequest) -> dict:
        if request.model_id != MODEL_ID:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported model_id {request.model_id!r}; expected {MODEL_ID!r}",
            )
        if request.dimensions != DIMENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported dimensions {request.dimensions}; expected {DIMENSIONS}",
            )

        try:
            image_url = resolve_image_url(request.image_object_key, request.image_url)
            vector = embed_pil_image(load_image(image_url))
        except Exception as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        return {
            "model_id": MODEL_ID,
            "dimensions": DIMENSIONS,
            "embedding": vector,
        }

    return api

