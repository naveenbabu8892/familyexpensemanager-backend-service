from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.core.database import check_database_connection
from app.schemas.health import HealthResponse

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Application Health Check",
    description="Check API runtime status and PostgreSQL database connectivity.",
)
async def health_check():
    """Verify application health and database connection."""
    db_connected, db_message = await check_database_connection()

    app_status = "healthy" if db_connected else "degraded"
    status_code = status.HTTP_200_OK if db_connected else status.HTTP_200_OK  # 200 with degraded status or 503

    content = {
        "status": app_status,
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "database": "connected" if db_connected else f"disconnected ({db_message})",
    }

    return JSONResponse(status_code=status_code, content=content)


@router.get(
    "/health/live",
    summary="Liveness Probe",
    description="Fast lightweight check to confirm the HTTP server is alive and responding.",
)
async def liveness_probe():
    """Liveness probe for container orchestration."""
    return {"status": "ok"}
