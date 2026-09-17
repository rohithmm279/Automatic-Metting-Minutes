"""FastAPI application entry point.

Start with:
    uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

Or from the backend/ directory:
    uvicorn main:app --reload
"""

from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# ---------------------------------------------------------------------------
# Path bootstrap — allow running both from repo root and from backend/
# ---------------------------------------------------------------------------
_ROOT = Path(__file__).resolve().parent.parent   # r:\S5 mini datasets
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# ---------------------------------------------------------------------------
# Internal imports
# ---------------------------------------------------------------------------
from backend.ai.orchestrator import MeetingOrchestrator        # noqa: E402
from backend.database.connection import DEFAULT_DB_PATH         # noqa: E402
from backend.database.repository import MeetingRepository       # noqa: E402
from backend.database.schema import init_db                     # noqa: E402
from backend.api.routes import router                           # noqa: E402

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lifespan — initialise shared resources once at startup
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
    """Initialise DB schema and shared singletons before serving requests."""
    logger.info("Initialising SQLite schema at %s", DEFAULT_DB_PATH)
    init_db(db_path=DEFAULT_DB_PATH)

    application.state.repository = MeetingRepository(db_path=DEFAULT_DB_PATH)
    application.state.orchestrator = MeetingOrchestrator(temperature=0.0)

    logger.info("Application ready — Qwen2.5:3b via Ollama + SQLite persistence active.")
    yield
    logger.info("Application shutting down.")


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Meeting Minutes API",
    description=(
        "AI-powered meeting analysis using Qwen2.5:3b (local Ollama) "
        "with SQLite persistence."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow all origins during local development (lock down before production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Global exception handler — never leak tracebacks to clients
# ---------------------------------------------------------------------------

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("Unhandled exception on %s %s: %s", request.method, request.url, exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected server error occurred."},
    )


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/", tags=["health"])
def health() -> dict:
    return {"status": "ok", "service": "Meeting Minutes API", "version": "1.0.0"}


@app.get("/health", tags=["health"])
def health_check() -> dict:
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Mount API routes
# ---------------------------------------------------------------------------

app.include_router(router, tags=["meetings"])
