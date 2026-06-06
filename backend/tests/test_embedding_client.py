import pytest

from app.model_services.embeddings import HttpEmbeddingClient, ImageEmbedding


def test_image_embedding_requires_values():
    with pytest.raises(ValueError):
        ImageEmbedding(model_id="model", dimensions=1152, embedding=[])


def test_http_embedding_client_posts_image_request(monkeypatch):
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "model_id": "test-model",
                "dimensions": 3,
                "embedding": [0.1, 0.2, 0.3],
            }

    def fake_post(url, *, json, timeout):
        captured["url"] = url
        captured["json"] = json
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("app.model_services.embeddings.httpx.post", fake_post)

    embedding = HttpEmbeddingClient("https://embedding.example.com").embed_image(
        image_object_key="runs/run/regions/region/crop.jpg",
        image_url="https://example.com/crop.jpg",
        model_id="test-model",
        dimensions=3,
    )

    assert captured["url"] == "https://embedding.example.com/embed-image"
    assert captured["json"] == {
        "image_object_key": "runs/run/regions/region/crop.jpg",
        "image_url": "https://example.com/crop.jpg",
        "model_id": "test-model",
        "dimensions": 3,
    }
    assert captured["timeout"] == 60.0
    assert embedding.embedding == [0.1, 0.2, 0.3]


def test_http_embedding_client_rejects_contract_mismatch(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "model_id": "other-model",
                "dimensions": 3,
                "embedding": [0.1, 0.2, 0.3],
            }

    monkeypatch.setattr(
        "app.model_services.embeddings.httpx.post",
        lambda *args, **kwargs: FakeResponse(),
    )

    with pytest.raises(ValueError, match="model_id"):
        HttpEmbeddingClient("https://embedding.example.com").embed_image(
            image_object_key="runs/run/regions/region/crop.jpg",
            image_url=None,
            model_id="test-model",
            dimensions=3,
        )
