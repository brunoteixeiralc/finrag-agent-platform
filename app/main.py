"""FastAPI application entry point."""

from fastapi import FastAPI

from app.api.infrastructure import router as infrastructure_router


def create_app() -> FastAPI:
    """Build and configure the FinRAG HTTP application."""

    application = FastAPI(
        title="FinRAG Agent Platform",
        summary="Evidence-grounded RAG API for public and synthetic documents.",
        description=(
            "M1 foundation of the FinRAG Agent Platform. Document ingestion and RAG query "
            "endpoints are planned but are not implemented yet."
        ),
        version="0.1.0",
        docs_url="/docs",
        openapi_url="/openapi.json",
    )
    application.include_router(infrastructure_router)
    return application


app = create_app()
