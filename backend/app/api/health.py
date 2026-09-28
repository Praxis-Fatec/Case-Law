from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.config import settings

router = APIRouter(tags=["infrastructure"])


class HealthResponse(BaseModel):
    status: str = Field(
        description="Always `ok` when the API is able to answer.",
        examples=["ok"],
    )
    environment: str = Field(
        description="Which environment answered the request.",
        examples=["development", "homologation", "production"],
    )


@router.get("/health", summary="Check that the API is up")
def health() -> HealthResponse:
    """
    Report whether the API is able to answer, and from which environment.

    Used by the Docker healthcheck and by the deploy pipeline to decide
    if a release is healthy before routing traffic to it.
    """
    return HealthResponse(status="ok", environment=settings.environment)
