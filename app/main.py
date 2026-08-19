"""FastAPI application entry point."""

from fastapi import FastAPI

from app.api.infrastructure import router as infrastructure_router
from app.settings import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build and configure the FinRAG HTTP application."""

    resolved_settings = settings if settings is not None else get_settings()
    application = FastAPI(
        title=resolved_settings.app_name,
        summary="Evidence-grounded RAG API for public and synthetic documents.",
        description=(
            "M1 foundation of the FinRAG Agent Platform. Document ingestion and RAG query "
            "endpoints are planned but are not implemented yet."
        ),
        version="0.1.0",
        docs_url="/docs",
        openapi_url="/openapi.json",
    )
    application.state.settings = resolved_settings
    application.include_router(infrastructure_router)
    return application


app = create_app()
