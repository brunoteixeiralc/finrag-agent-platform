"""Infrastructure endpoints that do not depend on external services."""

from typing import Literal

from fastapi import APIRouter, status
from pydantic import BaseModel, ConfigDict

router = APIRouter(tags=["Infrastructure"])


class HealthResponse(BaseModel):
    """Response returned when the HTTP process is alive."""

    model_config = ConfigDict(frozen=True)

    status: Literal["ok"] = "ok"


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
