"""
Health Check Endpoints

Provides operational health and readiness endpoints for monitoring and orchestration.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.database import get_db

router = APIRouter(tags=["Health"])


@router.get("/healthz")
async def health_check() -> dict:
    """
    Liveness probe endpoint.

    Returns 200 if the application is running.
    Used by orchestrators (Kubernetes, Docker Compose) to determine if the container is alive.

    Returns:
        dict: Status message
    """
    return {"status": "healthy"}


@router.get("/readyz")
async def readiness_check(db: AsyncSession = Depends(get_db)) -> dict:
    """
    Readiness probe endpoint.

    Returns 200 if the application is ready to serve traffic (database connection is healthy).
    Used by orchestrators to determine if the container should receive traffic.

    Args:
        db: Database session (dependency injection)

    Returns:
        dict: Status message with database connection status

    Raises:
        HTTPException: If database connection fails
    """
    # Test database connection
    try:
        from sqlalchemy import text
        await db.execute(text("SELECT 1"))
        return {"status": "ready", "database": "connected"}
    except Exception as e:
        # Let the exception propagate - FastAPI will return 500
        raise RuntimeError(f"Database connection failed: {str(e)}")
