import json
import re

import httpx

from app.catalog.repository import CatalogRepository
from app.catalog.schemas import CatalogItem, CatalogMatch
from app.model_services.embeddings import EmbeddingClient, ImageEmbedding
from app.search.schemas import RankedRegionMatch, RegionMatchRequest, RegionMatchSet


class RegionMatcher:
    def __init__(self, repository: CatalogRepository, embedding_client: EmbeddingClient):
        self.repository = repository
        self.embedding_client = embedding_client

    def match_region(self, request: RegionMatchRequest) -> RegionMatchSet:
        model_id = request.model_id
        dimensions = request.dimensions
        try:
            embedding = self.embedding_client.embed_image(
                image_object_key=request.crop_object_key,
                image_url=str(request.crop_url) if request.crop_url else None,
                model_id=request.model_id,
                dimensions=request.dimensions,
            )
            _validate_embedding(embedding, request)
            model_id = embedding.model_id
            dimensions = embedding.dimensions
            matches = self.repository.search_by_embedding(
                embedding=embedding.embedding,
                model_id=embedding.model_id,
                limit=request.limit,
                min_similarity=request.min_similarity,
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 429:
                raise
            matches = _fallback_catalog_matches(
                repository=self.repository,
                request=request,
            )
        return RegionMatchSet(
            region_id=request.region_id,
            crop_object_key=request.crop_object_key,
            crop_url=request.crop_url,
            model_id=model_id,
            dimensions=dimensions,
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


def _fallback_catalog_matches(
    *, repository: CatalogRepository, request: RegionMatchRequest
) -> list[CatalogMatch]:
    items = repository.list_items(limit=max(request.limit * 4, request.limit), offset=0)
    terms = {
        term
        for term in re.split(r"[^a-z0-9]+", request.region_id.lower())
        if len(term) >= 3 and term not in {"sam", "sam3", "region", "gemini", "coarse", "image"}
    }
    scored = [
        CatalogMatch(
            item=item,
            model_id=request.model_id,
            similarity=_catalog_keyword_score(item=item, terms=terms),
        )
        for item in items
    ]
    return [
        match
        for match in sorted(scored, key=lambda match: match.similarity, reverse=True)
        if match.similarity >= request.min_similarity
    ][: request.limit]


def _catalog_keyword_score(*, item: CatalogItem, terms: set[str]) -> float:
    if not terms:
        return 0.1
    haystack = " ".join(
        [
            item.manufacturer,
            item.name,
            item.material_family or "",
            json.dumps(item.metadata, sort_keys=True),
        ]
    ).lower()
    hits = sum(1 for term in terms if term in haystack)
    return 0.1 + (hits / len(terms))
