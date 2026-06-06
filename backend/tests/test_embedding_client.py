import pytest

from app.model_services.embeddings import ImageEmbedding


def test_image_embedding_requires_values():
    with pytest.raises(ValueError):
        ImageEmbedding(model_id="model", dimensions=1152, embedding=[])

