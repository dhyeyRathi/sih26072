"""
Health API endpoints — data source freshness, model status, system health.
"""

from fastapi import APIRouter
from src.health.monitor import health_monitor

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
async def get_system_health():
    """Get complete system health status for all data sources and model."""
    return health_monitor.get_all_status()


@router.get("/sources")
async def get_source_health():
    """Get health status for all data sources."""
    status = health_monitor.get_all_status()
    return status["sources"]


@router.get("/model")
async def get_model_health():
    """Get model inference health status."""
    status = health_monitor.get_all_status()
    return status["model"]
