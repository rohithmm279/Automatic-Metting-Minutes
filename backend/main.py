"""FastAPI application entry point.

Start with:
    uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

Or from the backend/ directory:
    uvicorn main:app --reload
"""

from __future__ import annotations

import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from fastapi.responses import JSONResponse

# ---------------------------------------------------------------------------
# Path bootstrap — allow running both from repo root and from backend/
# ---------------------------------------------------------------------------
_ROOT = Path(__file__).resolve().parent.parent   # r:\S5 mini datasets
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# ---------------------------------------------------------------------------
# Environment variables
# ---------------------------------------------------------------------------
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")
load_dotenv(_ROOT / ".env")
load_dotenv()

# ---------------------------------------------------------------------------
# Internal imports
# ---------------------------------------------------------------------------
from backend.ai.groq_client import GroqClient                    # noqa: E402
from backend.ai.ollama_client import OllamaClient                # noqa: E402
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

DEFAULT_CORS_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]


def get_cors_origins() -> list[str]:
    configured = os.getenv("CORS_ORIGINS", "")
    if not configured:
        return DEFAULT_CORS_ORIGINS

    origins = [origin.strip() for origin in configured.split(",") if origin.strip()]
    return origins if origins else DEFAULT_CORS_ORIGINS


# ---------------------------------------------------------------------------
# Lifespan — initialise shared resources once at startup
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
    """Initialise DB schema and shared singletons before serving requests."""
    logger.info("Initialising SQLite schema at %s", DEFAULT_DB_PATH)
    init_db(db_path=DEFAULT_DB_PATH)

    application.state.repository = MeetingRepository(db_path=DEFAULT_DB_PATH)
    two_pass = os.getenv("MEETING_TWO_PASS", "false").strip().lower() not in {"0", "false", "no", "off"}

    groq_api_key = os.getenv("GROQ_API_KEY", "").strip()
    if groq_api_key:
        groq_model = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")
        ai_client = GroqClient(api_key=groq_api_key, model=groq_model)
        logger.info("Application ready — Groq (%s) + SQLite persistence active.", groq_model)
    else:
        ollama_model = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
        ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        ai_client = OllamaClient(model=ollama_model, base_url=ollama_url)
        logger.info("Application ready — Qwen2.5:3b via Ollama (%s) + SQLite persistence active.", ollama_url)

    application.state.orchestrator = MeetingOrchestrator(
        client=ai_client,
        temperature=0.0,
        two_pass=two_pass,
        evidence_repair=True,
    )
    yield
    logger.info("Application shutting down.")


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Meeting Minutes API",
    description=(
        "AI-powered meeting analysis using Groq or local Ollama "
        "with SQLite persistence."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
cors_origins = get_cors_origins()
allow_credentials = "*" not in cors_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=allow_credentials,
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


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        reload=False,
    )
