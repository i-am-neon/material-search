import argparse
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

import httpx

from app.core.config import get_settings

DEFAULT_SAM3_IMAGE_URL = (
    "https://raw.githubusercontent.com/facebookresearch/sam3/main/assets/images/test_image.jpg"
)
DEFAULT_EMBEDDING_IMAGE_URL = DEFAULT_SAM3_IMAGE_URL

ServiceName = Literal["sam3", "embedding"]


@dataclass(frozen=True)
class WarmupResult:
    service: ServiceName
    endpoint: str
    elapsed_seconds: float
    summary: dict[str, Any]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Warm Modal model containers by making real inference requests."
    )
    parser.add_argument(
        "--service",
        choices=["all", "sam3", "embedding"],
        default="all",
        help="Which Modal service to warm. Defaults to both configured services.",
    )
    parser.add_argument(
        "--repeat",
        type=int,
        default=1,
        help="Number of warmup rounds to run. Use more than 1 to keep containers warm.",
    )
    parser.add_argument(
        "--interval-seconds",
        type=float,
        default=30.0,
        help="Delay between repeated warmup rounds.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=300.0,
        help="HTTP timeout for each inference request.",
    )
    parser.add_argument("--sam3-image-url", default=DEFAULT_SAM3_IMAGE_URL)
    parser.add_argument("--sam3-prompt", default="shoe")
    parser.add_argument("--embedding-image-url", default=DEFAULT_EMBEDDING_IMAGE_URL)
    return parser.parse_args()


def warm_sam3(
    *,
    base_url: str,
    image_url: str = DEFAULT_SAM3_IMAGE_URL,
    prompt: str = "shoe",
    timeout_seconds: float = 300.0,
    post: Callable[..., httpx.Response] = httpx.post,
) -> WarmupResult:
    endpoint = f"{base_url.rstrip('/')}/segment-image"
    started = time.perf_counter()
    response = post(
        endpoint,
        json={
            "image_url": image_url,
            "prompt": prompt,
            "confidence_threshold": 0.2,
            "max_regions": 1,
            "include_masks": False,
        },
        timeout=timeout_seconds,
        follow_redirects=True,
    )
    response.raise_for_status()
    elapsed = time.perf_counter() - started
    payload = response.json()
    regions = payload.get("regions") or []
    return WarmupResult(
        service="sam3",
        endpoint=endpoint,
        elapsed_seconds=elapsed,
        summary={
            "model_id": payload.get("model_id"),
            "image_width": payload.get("image_width"),
            "image_height": payload.get("image_height"),
            "region_count": len(regions),
            "top_score": regions[0].get("score") if regions else None,
        },
    )


def warm_embedding(
    *,
    base_url: str,
    image_url: str = DEFAULT_EMBEDDING_IMAGE_URL,
    model_id: str,
    dimensions: int,
    timeout_seconds: float = 300.0,
    post: Callable[..., httpx.Response] = httpx.post,
) -> WarmupResult:
    endpoint = f"{base_url.rstrip('/')}/embed-image"
    started = time.perf_counter()
    response = post(
        endpoint,
        json={
            "image_url": image_url,
            "model_id": model_id,
            "dimensions": dimensions,
        },
        timeout=timeout_seconds,
    )
    response.raise_for_status()
    elapsed = time.perf_counter() - started
    payload = response.json()
    embedding = payload.get("embedding") or []
    return WarmupResult(
        service="embedding",
        endpoint=endpoint,
        elapsed_seconds=elapsed,
        summary={
            "model_id": payload.get("model_id"),
            "dimensions": payload.get("dimensions"),
            "embedding_length": len(embedding),
        },
    )


def selected_services(service: str) -> set[ServiceName]:
    if service == "all":
        return {"sam3", "embedding"}
    if service == "sam3":
        return {"sam3"}
    if service == "embedding":
        return {"embedding"}
    raise ValueError(f"Unsupported service {service!r}")


def main() -> None:
    args = parse_args()
    if args.repeat < 1:
        raise SystemExit("--repeat must be at least 1")
    if args.interval_seconds < 0:
        raise SystemExit("--interval-seconds must be non-negative")

    settings = get_settings()
    requested = selected_services(args.service)
    runnable: list[ServiceName] = []

    if "sam3" in requested:
        if settings.sam3_service_url is None:
            print("Skipping SAM3: SAM3_SERVICE_URL is not configured.")
        else:
            runnable.append("sam3")

    if "embedding" in requested:
        if settings.embedding_service_url is None:
            print("Skipping embedding: EMBEDDING_SERVICE_URL is not configured.")
        else:
            runnable.append("embedding")

    if not runnable:
        raise SystemExit("No configured Modal services to warm.")

    for round_index in range(args.repeat):
        if args.repeat > 1:
            print(f"Warmup round {round_index + 1}/{args.repeat}")

        for service in runnable:
            if service == "sam3":
                result = warm_sam3(
                    base_url=str(settings.sam3_service_url),
                    image_url=args.sam3_image_url,
                    prompt=args.sam3_prompt,
                    timeout_seconds=args.timeout_seconds,
                )
            else:
                result = warm_embedding(
                    base_url=str(settings.embedding_service_url),
                    image_url=args.embedding_image_url,
                    model_id=settings.embedding_model_id,
                    dimensions=settings.embedding_dimensions,
                    timeout_seconds=args.timeout_seconds,
                )
            print(format_result(result))

        if round_index < args.repeat - 1:
            time.sleep(args.interval_seconds)


def format_result(result: WarmupResult) -> str:
    summary = ", ".join(f"{key}={value}" for key, value in result.summary.items())
    return (
        f"Warmed {result.service} via {result.endpoint} "
        f"in {result.elapsed_seconds:.1f}s ({summary})"
    )


if __name__ == "__main__":
    main()
