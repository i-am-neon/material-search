from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.catalog.router import router as catalog_router
from app.core.config import get_settings
from app.dev.router import router as dev_router
from app.search.router import router as search_router


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name)
    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.include_router(catalog_router)
    app.include_router(dev_router)
    app.include_router(search_router)

    @app.get("/healthz", tags=["system"])
    def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
