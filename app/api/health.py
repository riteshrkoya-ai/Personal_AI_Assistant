from fastapi import APIRouter

from app.core.database import check_database_connection

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check() -> dict:
    return {
        "status": "healthy",
        "service": "AI Personal Assistant API",
        "version": "0.1.0",
    }


@router.get("/health/db")
async def database_health_check() -> dict:
    is_connected = await check_database_connection()

    return {
        "database": "connected" if is_connected else "not connected",
        "status": "healthy" if is_connected else "unhealthy",
    }