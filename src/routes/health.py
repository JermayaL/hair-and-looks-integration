"""Health check en admin endpoints."""

import logging
from datetime import date, timedelta

from fastapi import APIRouter

from src.config import settings
from src.database import get_intention_count
from src.klaviyo_client import klaviyo_client
from src.scheduler import run_daily_sync

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health")
async def health_check():
    """Health check met Klaviyo connectie status en buffer statistieken."""
    klaviyo_status = await klaviyo_client.check_connection()
    buffer_stats = await get_intention_count()

    return {
        "status": "healthy",
        "mode": settings.mode.value,
        "klaviyo": klaviyo_status,
        "buffer": buffer_stats,
    }


@router.post("/admin/trigger-daily-sync")
async def trigger_daily_sync():
    """Handmatig de dagelijkse sync triggeren (voor testen).

    Verwerkt alle onverwerkte intenties van gisteren.
    """
    logger.info("Handmatige dagelijkse sync gestart")
    result = await run_daily_sync()
    return {
        "status": "completed",
        "result": result,
    }
