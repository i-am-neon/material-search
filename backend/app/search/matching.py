import json
import re
from typing import Any

import httpx

from app.catalog.repository import CatalogRepository
from app.catalog.schemas import CatalogItem, CatalogMatch
from app.model_services.embeddings import EmbeddingClient, ImageEmbedding
from app.search.schemas import RankedRegionMatch, RegionMatchRequest, RegionMatchSet

_CATEGORY_CANDIDATE_MULTIPLIER = 4

_CATEGORY_ALIASES: tuple[tuple[set[str], set[str]], ...] = (
    (
        {"carpet", "rug", "broadloom"},
        {"carpet", "entry carpet", "modular carpet", "entrance carpet", "rug", "broadloom"},
    ),
    (
        {"shade", "window covering", "window treatment"},
        {"shade textile", "window covering", "shade fabric"},
    ),
    (
        {"upholstery", "textile", "fabric", "woven"},
        {"textile", "upholstery", "woven", "fabric"},
    ),
    (
        {"tile", "porcelain", "ceramic"},
        {"tile", "porcelain", "ceramic"},
    ),
    (
        {"wood", "hardwood", "oak", "laminate", "woodgrain", "veneer"},
        {"wood", "hardwood", "oak", "laminate", "woodgrain", "veneer", "high pressure laminate"},
    ),
    (
        {"stone", "marble", "granite", "limestone", "travertine"},
        {"stone", "marble", "granite", "limestone", "travertine"},
    ),
    (
        {"wallcovering", "wall covering", "wallpaper"},
        {"wallcovering", "wall covering", "wallpaper"},
    ),
)


class RegionMatcher:
    def __init__(self, repository: CatalogRepository, embedding_client: EmbeddingClient):
        self.repository = repository
        self.embedding_client = embedding_client

    def match_region(self, request: RegionMatchRequest) -> RegionMatchSet:
        try:
            embedding = self.embed_region(request)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 429:
                raise
            return self.match_fallback(request)
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
        model_id = embedding.model_id
        dimensions = embedding.dimensions
        category_terms = _category_terms_for_hint(request.material_filter_hint)
        search_limit = _search_limit_for_category_filter(
            limit=request.limit,
            category_terms=category_terms,
        )
        try:
            matches = self.repository.search_by_embedding(
                embedding=embedding.embedding,
                model_id=embedding.model_id,
                limit=search_limit,
                min_similarity=request.min_similarity,
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 429:
                raise
            matches = _fallback_catalog_matches(
                repository=self.repository,
                request=request,
                limit=search_limit,
            )
        matches = _filter_matches_by_category(matches, category_terms)[: request.limit]
        return _build_match_set(
            request=request,
            model_id=model_id,
            dimensions=dimensions,
            matches=matches,
        )

    def match_fallback(self, request: RegionMatchRequest) -> RegionMatchSet:
        category_terms = _category_terms_for_hint(request.material_filter_hint)
        search_limit = _search_limit_for_category_filter(
            limit=request.limit,
            category_terms=category_terms,
        )
        matches = _fallback_catalog_matches(
            repository=self.repository,
            request=request,
            limit=search_limit,
        )
        matches = _filter_matches_by_category(matches, category_terms)[: request.limit]
        return _build_match_set(
            request=request,
            model_id=request.model_id,
            dimensions=request.dimensions,
            matches=matches,
        )


def _build_match_set(
    *, request: RegionMatchRequest, model_id: str, dimensions: int, matches: list[CatalogMatch]
) -> RegionMatchSet:
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


def _search_limit_for_category_filter(
    *, limit: int, category_terms: set[str] | None
) -> int:
    if not category_terms:
        return limit
    return min(100, limit * _CATEGORY_CANDIDATE_MULTIPLIER)


def _filter_matches_by_category(
    matches: list[CatalogMatch], category_terms: set[str] | None
) -> list[CatalogMatch]:
    if not category_terms:
        return matches

    filtered = [match for match in matches if _catalog_item_matches(match.item, category_terms)]
    return filtered or matches


def _category_terms_for_hint(hint: str | None) -> set[str] | None:
    if not hint:
        return None

    normalized_hint = _normalize_term(hint)
    for hint_terms, category_terms in _CATEGORY_ALIASES:
        if any(term in normalized_hint for term in hint_terms):
            return category_terms
    return None


def _catalog_item_matches(item: CatalogItem, category_terms: set[str]) -> bool:
    item_terms = {_normalize_term(item.material_family)}
    item_terms.update(_metadata_material_terms(item.metadata))
    return any(term in category_terms for term in item_terms)


def _metadata_material_terms(metadata: dict[str, Any]) -> set[str]:
    values = metadata.get("materials") or []
    if isinstance(values, str):
        values = [values]
    if not isinstance(values, list):
        return set()
    return {_normalize_term(value) for value in values if isinstance(value, str)}


def _normalize_term(value: str | None) -> str:
    return (value or "").lower().replace("_", " ").replace("-", " ").strip()


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
    *, repository: CatalogRepository, request: RegionMatchRequest, limit: int
) -> list[CatalogMatch]:
    items = repository.list_items(limit=max(limit * 4, limit), offset=0)
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
    ][:limit]


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
