from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.catalog.dependencies import get_catalog_repository
from app.catalog.repository import CatalogRepository
from app.catalog.schemas import (
    CatalogEmbeddingRequest,
    CatalogIndexAccepted,
    CatalogItem,
    CatalogItemCreate,
    CatalogItemList,
    CatalogVectorSearchRequest,
    CatalogVectorSearchResponse,
)
from app.catalog.service import CatalogIndexingService, accepted_response
from app.core.config import get_settings
from app.workers.catalog_indexing import index_catalog_item

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.post("/items", response_model=CatalogItem, status_code=status.HTTP_201_CREATED)
def create_catalog_item(
    item: CatalogItemCreate,
    repository: Annotated[CatalogRepository, Depends(get_catalog_repository)],
) -> CatalogItem:
    return repository.create_item(item)


@router.get("/items", response_model=CatalogItemList)
def list_catalog_items(
    repository: Annotated[CatalogRepository, Depends(get_catalog_repository)],
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> CatalogItemList:
    return CatalogItemList(items=repository.list_items(limit=limit, offset=offset))


@router.post(
    "/embeddings:index",
    response_model=CatalogIndexAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
def enqueue_catalog_embeddings(
    repository: Annotated[CatalogRepository, Depends(get_catalog_repository)],
    request: CatalogEmbeddingRequest | None = None,
) -> CatalogIndexAccepted:
    settings = get_settings()
    request = request or CatalogEmbeddingRequest(
        model_id=settings.embedding_model_id,
        dimensions=settings.embedding_dimensions,
    )
    service = CatalogIndexingService(repository)
    try:
        jobs = service.build_jobs(
            catalog_item_ids=request.catalog_item_ids,
            model_id=request.model_id,
            dimensions=request.dimensions,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    for job in jobs:
        index_catalog_item.send(job.model_dump(mode="json"))
    return accepted_response(jobs, request.model_id, request.dimensions)


@router.post(
    "/items/{catalog_item_id}/embeddings:index",
    response_model=CatalogIndexAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
def enqueue_catalog_item_embedding(
    catalog_item_id: UUID,
    repository: Annotated[CatalogRepository, Depends(get_catalog_repository)],
) -> CatalogIndexAccepted:
    settings = get_settings()
    service = CatalogIndexingService(repository)
    try:
        jobs = service.build_jobs(
            catalog_item_ids=[catalog_item_id],
            model_id=settings.embedding_model_id,
            dimensions=settings.embedding_dimensions,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    for job in jobs:
        index_catalog_item.send(job.model_dump(mode="json"))
    return accepted_response(jobs, settings.embedding_model_id, settings.embedding_dimensions)


@router.post("/vector-search", response_model=CatalogVectorSearchResponse)
def vector_search_catalog(
    request: CatalogVectorSearchRequest,
    repository: Annotated[CatalogRepository, Depends(get_catalog_repository)],
) -> CatalogVectorSearchResponse:
    matches = repository.search_by_embedding(
        embedding=request.embedding,
        model_id=request.model_id,
        limit=request.limit,
        min_similarity=request.min_similarity,
    )
    return CatalogVectorSearchResponse(matches=matches)
