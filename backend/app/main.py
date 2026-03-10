"""FastAPI application factory."""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db.engine import init_db
from app.sources.registry import source_registry
from app.sources.openalex_source import OpenAlexSource
from app.sources.arxiv_source import ArxivSource
from app.sources.scopus_source import ScopusSource

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Startup
    logger.info("ARTA backend starting...")
    await init_db()

    # Load API keys and model settings from DB
    from app.services.ai_service import ai_service
    await ai_service.load_settings_from_db()

    # Register data sources (always register all; availability checked at query time)
    source_registry.register(OpenAlexSource())
    source_registry.register(ArxivSource())
    source_registry.register(ScopusSource())

    # If DB has scopus_api_key, sync it to pybliometrics config
    scopus_key = os.environ.get("SCOPUS_API_KEY", "")
    if scopus_key:
        from app.sources.scopus_source import _write_pybliometrics_key
        _write_pybliometrics_key(scopus_key)

    source_status = await source_registry.status()
    logger.info(f"Data sources: {source_status}")

    yield

    # Shutdown
    logger.info("ARTA backend shutting down...")


def create_app() -> FastAPI:
    app = FastAPI(
        title="ARTA - AI Research Trend Analysis",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS for Tauri/dev
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routes
    from app.api.routes import health, sessions, chat, papers, search, analysis, reports, settings as settings_routes, export
    from app.api.websocket import router as ws_router

    app.include_router(health.router, prefix="/api")
    app.include_router(sessions.router, prefix="/api")
    app.include_router(chat.router, prefix="/api")
    app.include_router(papers.router, prefix="/api")
    app.include_router(search.router, prefix="/api")
    app.include_router(analysis.router, prefix="/api")
    app.include_router(reports.router, prefix="/api")
    app.include_router(settings_routes.router, prefix="/api")
    app.include_router(settings_routes.validate_router, prefix="/api")
    app.include_router(export.router, prefix="/api")
    app.include_router(ws_router)

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
