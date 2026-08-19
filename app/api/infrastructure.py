"""Infrastructure liveness and readiness endpoints."""

import asyncio
from typing import Literal

from fastapi import APIRouter, Request, Response, status
from pydantic import BaseModel, ConfigDict

from app.database import DatabaseGateway
from app.settings import Settings

router = APIRouter(tags=["Infrastructure"])


class HealthResponse(BaseModel):
    """Response returned when the HTTP process is alive."""

    model_config = ConfigDict(frozen=True)

    status: Literal["ok"] = "ok"


class ReadinessResponse(BaseModel):
    """Response returned after checking required local dependencies."""

    model_config = ConfigDict(frozen=True)

    status: Literal["ready", "not_ready"]


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Check process health",
    description="Confirms that the HTTP process is running without checking external services.",
)
async def health() -> HealthResponse:
    """Return process liveness without performing I/O."""

    return HealthResponse()


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "model": ReadinessResponse,
            "description": "PostgreSQL or pgvector is unavailable.",
        }
    },
    summary="Check required dependencies",
    description="Confirms that PostgreSQL is reachable and the pgvector extension is enabled.",
)
async def readiness(request: Request, response: Response) -> ReadinessResponse:
    """Return readiness without exposing database connection details."""

    database: DatabaseGateway = request.app.state.database
    settings: Settings = request.app.state.settings

    try:
        async with asyncio.timeout(settings.readiness_timeout_seconds):
            is_ready = await database.is_ready()
    except TimeoutError:
        is_ready = False

    if is_ready:
        return ReadinessResponse(status="ready")

    response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadinessResponse(status="not_ready")
