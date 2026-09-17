from contextlib import asynccontextmanager
import logging
from typing import AsyncGenerator
from fastapi import FastAPI, HTTPException, Request

from app.schemas.meeting_schema import (
    MeetingRequest,
    MeetingAnalysis
)
from app.schemas.evaluation_schema import DatasetInfo, EvaluationRequest, EvaluationResult
from app.services.analysis_pipeline import analyze_transcript, analyze_transcript_detailed
from app.services.dataset_loader import DatasetLoader
from app.services.evaluation_service import EvaluationService
from backend.database.connection import DEFAULT_DB_PATH
from backend.database.repository import MeetingRepository
from backend.database.schema import init_db

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
    """Initialise DB schema and repository singleton on app startup."""
    init_db(db_path=DEFAULT_DB_PATH)
    if not hasattr(application.state, "repository") or application.state.repository is None:
        application.state.repository = MeetingRepository(db_path=DEFAULT_DB_PATH)
    yield


app = FastAPI(
    title="Automatic Meeting Minutes & Action Item Generator",
    description="Backend API for AI-powered meeting analysis",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/")
def home():
    return {
        "message": "Meeting Minutes AI Backend is running"
    }


def _get_repository(request: Request) -> MeetingRepository:
    """Retrieve repository from app state or fall back to default instance."""
    repo = getattr(request.app.state, "repository", None)
    if repo is None:
        repo = MeetingRepository(db_path=DEFAULT_DB_PATH)
        request.app.state.repository = repo
    return repo


@app.post(
    "/analyze-meeting",
    response_model=MeetingAnalysis
)
def analyze_meeting(meeting_request: MeetingRequest, request: Request):
    try:
        analysis = analyze_transcript(meeting_request.transcript)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Transcript must contain non-whitespace text.",
        )

    try:
        repo = _get_repository(request)
        repo.save_meeting_analysis(
            transcript=meeting_request.transcript,
            analysis=analysis,
        )
    except Exception as exc:
        logger.error("Database error while saving meeting analysis: %s", exc)
        raise HTTPException(
            status_code=500,
            detail="Failed to persist meeting analysis to database.",
        ) from exc

    return analysis


@app.get("/datasets", response_model=list[DatasetInfo])
def list_datasets():
    """List selectable supported files and directory collections for evaluation."""
    return DatasetLoader().discover()


@app.post("/evaluate", response_model=EvaluationResult)
def evaluate(request: EvaluationRequest):
    """Evaluate the shared analysis pipeline against one file or directory collection."""
    loader = DatasetLoader()
    try:
        records, skipped_records = loader.load(request.dataset_name, request.limit)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    return EvaluationService().evaluate(
        dataset_name=request.dataset_name,
        requested_limit=request.limit,
        records=records,
        skipped_records=skipped_records,
        analyze=analyze_transcript_detailed,
        pacing_seconds=request.pacing_seconds,
    )
