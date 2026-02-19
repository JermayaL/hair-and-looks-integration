"""Hair & Looks — Salonhub → Klaviyo middleware.

FastAPI applicatie die Salonhub webhooks opvangt,
buffert in SQLite, en dagelijks doorstuurt naar Klaviyo V3 API.
"""

import logging
from contextlib import asynccontextmanager

from apscheduler import AsyncScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import settings
from src.database import init_db
from src.routes import health, webhook
from src.scheduler import run_daily_sync

# Logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup en shutdown logica."""
    # Startup
    logger.info(f"Hair & Looks integratie gestart (modus: {settings.mode.value})")
    await init_db()

    # Plan de dagelijkse sync met APScheduler v4
    async with AsyncScheduler() as scheduler:
        await scheduler.add_schedule(
            run_daily_sync,
            CronTrigger(hour=settings.daily_sync_hour, minute=0),
            id="daily_sync",
        )
        logger.info(f"Scheduler gestart: dagelijkse sync om {settings.daily_sync_hour:02d}:00")

        yield

    logger.info("Hair & Looks integratie gestopt")


# FastAPI app
app = FastAPI(
    title="Hair & Looks — Salonhub → Klaviyo",
    description="Middleware die Salonhub webhooks opvangt en doorstuurt naar Klaviyo V3 API",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS (open voor webhook ontvangers)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(webhook.router, tags=["Webhook"])
app.include_router(health.router, tags=["Health & Admin"])


@app.get("/")
async def root():
    return {
        "service": "Hair & Looks — Salonhub → Klaviyo",
        "version": "0.1.0",
        "mode": settings.mode.value,
        "docs": "/docs",
    }
