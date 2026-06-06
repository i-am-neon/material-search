from fastapi import FastAPI

from app.catalog.router import router as catalog_router
from app.core.config import get_settings
from app.search.router import router as search_router


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name)

    app.include_router(catalog_router)
    app.include_router(search_router)

    @app.get("/healthz", tags=["system"])
    def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
