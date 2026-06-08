from argparse import Namespace

import pytest

from app.model_services.warmup import (
    apply_defaults,
    format_result,
    selected_services,
    warm_embeddings_concurrently,
    warm_embedding,
    warm_sam3,
)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def test_warm_sam3_posts_minimal_inference_request(monkeypatch):
    captured = {}
    monkeypatch.setattr("app.model_services.warmup.time.perf_counter", iter([10.0, 12.5]).__next__)

    def fake_post(url, *, json, timeout, follow_redirects):
        captured["url"] = url
        captured["json"] = json
        captured["timeout"] = timeout
        captured["follow_redirects"] = follow_redirects
        return FakeResponse(
            {
                "model_id": "facebook/sam3",
                "image_width": 640,
                "image_height": 480,
                "regions": [{"score": 0.91}],
            }
        )

    result = warm_sam3(
        base_url="https://sam3.example.com/",
        image_url="https://example.com/source.jpg",
        prompt="chair",
        timeout_seconds=123.0,
        post=fake_post,
    )

    assert captured == {
        "url": "https://sam3.example.com/segment-image",
        "json": {
            "image_url": "https://example.com/source.jpg",
            "prompt": "chair",
            "confidence_threshold": 0.2,
            "max_regions": 1,
            "include_masks": False,
        },
        "timeout": 123.0,
        "follow_redirects": True,
    }
    assert result.service == "sam3"
    assert result.elapsed_seconds == 2.5
    assert result.summary["region_count"] == 1
    assert result.summary["top_score"] == 0.91


def test_warm_embedding_posts_minimal_inference_request(monkeypatch):
    captured = {}
    monkeypatch.setattr("app.model_services.warmup.time.perf_counter", iter([1.0, 4.0]).__next__)

    def fake_post(url, *, json, timeout):
        captured["url"] = url
        captured["json"] = json
        captured["timeout"] = timeout
        return FakeResponse(
            {
                "model_id": "siglip-test",
                "dimensions": 3,
                "embedding": [0.1, 0.2, 0.3],
            }
        )

    result = warm_embedding(
        base_url="https://embedding.example.com/",
        image_url="https://example.com/source.jpg",
        model_id="siglip-test",
        dimensions=3,
        timeout_seconds=45.0,
        post=fake_post,
    )

    assert captured == {
        "url": "https://embedding.example.com/embed-image",
        "json": {
            "image_url": "https://example.com/source.jpg",
            "model_id": "siglip-test",
            "dimensions": 3,
        },
        "timeout": 45.0,
    }
    assert result.service == "embedding"
    assert result.elapsed_seconds == 3.0
    assert result.summary["embedding_length"] == 3


def test_demo_defaults_warm_parallel_embedding_containers():
    args = Namespace(
        demo=True,
        service=None,
        repeat=None,
        interval_seconds=None,
        embedding_concurrency=None,
    )

    apply_defaults(args)

    assert args.service == "all"
    assert args.repeat == 2
    assert args.interval_seconds == 5.0
    assert args.embedding_concurrency == 3


def test_warm_embeddings_concurrently_posts_one_request_per_worker():
    captured = []

    def fake_post(url, *, json, timeout):
        captured.append((url, json, timeout))
        return FakeResponse(
            {
                "model_id": "siglip-test",
                "dimensions": 3,
                "embedding": [0.1, 0.2, 0.3],
            }
        )

    results = warm_embeddings_concurrently(
        concurrency=3,
        base_url="https://embedding.example.com/",
        image_url="https://example.com/source.jpg",
        model_id="siglip-test",
        dimensions=3,
        timeout_seconds=45.0,
        post=fake_post,
    )

    assert len(results) == 3
    assert len(captured) == 3
    assert all(result.summary["embedding_length"] == 3 for result in results)


@pytest.mark.parametrize(
    ("choice", "expected"),
    [
        ("all", {"sam3", "embedding"}),
        ("sam3", {"sam3"}),
        ("embedding", {"embedding"}),
    ],
)
def test_selected_services(choice, expected):
    assert selected_services(choice) == expected


def test_format_result_keeps_embedding_vector_out_of_output():
    output = format_result(
        warm_embedding(
            base_url="https://embedding.example.com",
            image_url="https://example.com/source.jpg",
            model_id="siglip-test",
            dimensions=3,
            post=lambda *args, **kwargs: FakeResponse(
                {
                    "model_id": "siglip-test",
                    "dimensions": 3,
                    "embedding": [0.1, 0.2, 0.3],
                }
            ),
        )
    )

    assert "embedding_length=3" in output
    assert "[0.1" not in output
