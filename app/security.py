"""Bearer authentication dependency for future versioned API routes."""

from hmac import compare_digest
from typing import Annotated

from fastapi import Depends, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.http import ApiError
from app.settings import Settings

bearer_scheme = HTTPBearer(
    scheme_name="BearerAuth",
    bearerFormat="API key",
    description="Internal API key required by functional `/v1` endpoints.",
    auto_error=False,
)


async def require_api_key(
    request: Request,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
) -> None:
    """Reject missing, unconfigured, or invalid API keys uniformly."""

    settings: Settings = request.app.state.settings
    configured_key = settings.api_key
    provided_key = credentials.credentials if credentials is not None else None

    is_valid = (
        configured_key is not None
        and provided_key is not None
        and compare_digest(
            provided_key.encode("utf-8"),
            configured_key.get_secret_value().encode("utf-8"),
        )
    )
    if not is_valid:
        raise ApiError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="unauthorized",
            message="Authentication credentials are missing or invalid.",
            headers={"WWW-Authenticate": "Bearer"},
        )
