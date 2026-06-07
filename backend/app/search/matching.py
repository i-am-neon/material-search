from app.catalog.repository import CatalogRepository
from app.model_services.embeddings import EmbeddingClient, ImageEmbedding
from app.search.schemas import RankedRegionMatch, RegionMatchRequest, RegionMatchSet


class RegionMatcher:
    def __init__(self, repository: CatalogRepository, embedding_client: EmbeddingClient):
        self.repository = repository
        self.embedding_client = embedding_client

    def match_region(self, request: RegionMatchRequest) -> RegionMatchSet:
        embedding = self.embed_region(request)
        return self.match_embedding(request, embedding)

    def embed_region(self, request: RegionMatchRequest) -> ImageEmbedding:
        return self.embedding_client.embed_image(
            image_object_key=request.crop_object_key,
            image_url=str(request.crop_url) if request.crop_url else None,
            model_id=request.model_id,
            dimensions=request.dimensions,
        )

    def match_embedding(
        self, request: RegionMatchRequest, embedding: ImageEmbedding
    ) -> RegionMatchSet:
        _validate_embedding(embedding, request)

        matches = self.repository.search_by_embedding(
            embedding=embedding.embedding,
            model_id=embedding.model_id,
            limit=request.limit,
            min_similarity=request.min_similarity,
        )
        return RegionMatchSet(
            region_id=request.region_id,
            crop_object_key=request.crop_object_key,
            crop_url=request.crop_url,
            model_id=embedding.model_id,
            dimensions=embedding.dimensions,
            matches=[
                RankedRegionMatch(region_id=request.region_id, rank=rank, match=match)
                for rank, match in enumerate(matches, start=1)
            ],
        )


def _validate_embedding(embedding: ImageEmbedding, request: RegionMatchRequest) -> None:
    if embedding.model_id != request.model_id:
        raise ValueError(
            f"Embedding service returned model_id={embedding.model_id!r}, "
            f"expected {request.model_id!r}"
        )
    if embedding.dimensions != request.dimensions:
        raise ValueError(
            f"Embedding service returned dimensions={embedding.dimensions}, "
            f"expected {request.dimensions}"
        )
    if len(embedding.embedding) != request.dimensions:
        raise ValueError(
            f"Embedding length {len(embedding.embedding)} "
            f"does not match dimensions {request.dimensions}"
        )
