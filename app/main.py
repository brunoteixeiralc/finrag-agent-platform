"""FastAPI application entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.infrastructure import router as infrastructure_router
from app.database import DatabaseGateway, PsycopgDatabase, UnconfiguredDatabase
from app.http import RequestIdMiddleware, register_error_handlers
from app.settings import Settings, get_settings


def create_app(
    settings: Settings | None = None,
    database: DatabaseGateway | None = None,
) -> FastAPI:
    """Build and configure the FinRAG HTTP application."""

    resolved_settings = settings if settings is not None else get_settings()
    resolved_database = database
    if resolved_database is None:
        resolved_database = (
            PsycopgDatabase(resolved_settings.database_url.get_secret_value())
            if resolved_settings.database_url is not None
            else UnconfiguredDatabase()
        )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        await resolved_database.open()
        try:
            yield
        finally:
            await resolved_database.close()

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
        lifespan=lifespan,
    )
    application.state.settings = resolved_settings
    application.state.database = resolved_database
    application.add_middleware(RequestIdMiddleware)
    register_error_handlers(application)
    application.include_router(infrastructure_router)
    return application


app = create_app()
