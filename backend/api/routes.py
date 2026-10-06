"""FastAPI route handlers.

Wires HTTP requests to:
  - MeetingOrchestrator  (AI pipeline)
  - MeetingRepository    (SQLite persistence)

No AI or DB logic lives here.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response, status

from backend.ai.orchestrator import MeetingOrchestrator, MeetingParseError
from backend.ai.validator import MeetingValidationError
from backend.database.repository import MeetingRepository
from backend.api.schemas import (
    ALLOWED_STATUSES,
    ActionItemResponse,
    CreateMeetingRequest,
    CreateMeetingResponse,
    DecisionResponse,
    MeetingDetailResponse,
    MeetingListItem,
    UnresolvedIssueResponse,
    UpdateActionItemStatusRequest,
    UpdateActionItemStatusResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_repo(request: Request) -> MeetingRepository:
    """Pull the shared MeetingRepository from app state."""
    return request.app.state.repository


def _row_to_action_item(row: dict[str, Any]) -> ActionItemResponse:
    owner_val = row.get("owner")
    conf_val = float(row.get("confidence", 1.0)) if row.get("confidence") is not None else 1.0
    return ActionItemResponse(
        id=row["id"],
        meeting_id=row["meeting_id"],
        task=row["task"],
        owner=owner_val,
        assignee=owner_val,
        deadline=row.get("deadline"),
        status=row.get("status", "pending"),
        confidence=conf_val,
        confidence_score=conf_val,
        evidence=row.get("evidence"),
    )


def _row_to_decision(row: dict[str, Any]) -> DecisionResponse:
    return DecisionResponse(
        id=row["id"],
        meeting_id=row["meeting_id"],
        decision=row["decision"],
        confidence=row["confidence"],
    )


def _row_to_issue(row: dict[str, Any]) -> UnresolvedIssueResponse:
    return UnresolvedIssueResponse(
        id=row["id"],
        meeting_id=row["meeting_id"],
        issue=row["issue"],
        confidence=row["confidence"],
    )


# ---------------------------------------------------------------------------
# POST /meetings
# ---------------------------------------------------------------------------


@router.post(
    "/meetings",
    response_model=CreateMeetingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Analyse a transcript and persist the result",
)
def create_meeting(body: CreateMeetingRequest, request: Request) -> CreateMeetingResponse:
    """Run the full AI pipeline and store the validated output in SQLite."""
    repo = _get_repo(request)
    orchestrator: MeetingOrchestrator = request.app.state.orchestrator

    try:
        meeting_output = orchestrator.analyze(body.transcript)
    except MeetingValidationError as exc:
        logger.warning("Validation error during analysis: %s", exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except MeetingParseError as exc:
        logger.error("Parse error from model output: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The AI model returned an unparseable response. Please retry.",
        ) from exc
    except ValueError as exc:
        logger.warning("Invalid transcript input: %s", exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Unexpected error during AI analysis: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI model is currently unavailable. Please ensure Ollama is running.",
        ) from exc

    try:
        meeting_id = repo.save_meeting(
            transcript=body.transcript, meeting_output=meeting_output
        )
    except Exception as exc:
        logger.error("Database error while saving meeting: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to persist meeting. Please try again.",
        ) from exc

    saved = repo.get_meeting(meeting_id)
    if saved is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Meeting was saved but could not be retrieved.",
        )

    return CreateMeetingResponse(
        meeting_id=saved["id"],
        summary=saved["summary"],
        title=saved.get("title"),
        meeting_date=saved.get("meeting_date"),
        meeting_time=saved.get("meeting_time"),
        start_time=saved.get("start_time"),
        end_time=saved.get("end_time"),
        action_items=[_row_to_action_item(r) for r in saved["action_items"]],
        decisions=[_row_to_decision(r) for r in saved["decisions"]],
        unresolved_issues=[_row_to_issue(r) for r in saved["unresolved_issues"]],
        created_at=saved["created_at"],
        model_name=saved.get("model_name"),
        pipeline_name=saved.get("pipeline_name"),
        prompt_version=saved.get("prompt_version"),
        fallback_used=bool(saved.get("fallback_used", 0)),
    )


# ---------------------------------------------------------------------------
# GET /meetings
# ---------------------------------------------------------------------------


@router.get(
    "/meetings",
    response_model=list[MeetingListItem],
    summary="List all stored meetings",
)
def list_meetings(request: Request, limit: int = 50, offset: int = 0) -> list[MeetingListItem]:
    """Return stored meetings (newest first) with item counts."""
    repo = _get_repo(request)
    rows = repo.list_meetings(limit=limit, offset=offset)
    return [
        MeetingListItem(
            id=r["id"],
            summary=r["summary"],
            title=r.get("title"),
            meeting_date=r.get("meeting_date"),
            meeting_time=r.get("meeting_time"),
            start_time=r.get("start_time"),
            end_time=r.get("end_time"),
            created_at=r["created_at"],
            action_items_count=r["action_items_count"],
            decisions_count=r["decisions_count"],
            unresolved_issues_count=r["unresolved_issues_count"],
            model_name=r.get("model_name"),
            pipeline_name=r.get("pipeline_name"),
            prompt_version=r.get("prompt_version"),
            fallback_used=bool(r.get("fallback_used", 0)),
        )
        for r in rows
    ]


# ---------------------------------------------------------------------------
# GET /meetings/{meeting_id}
# ---------------------------------------------------------------------------


@router.get(
    "/meetings/{meeting_id}",
    response_model=MeetingDetailResponse,
    summary="Retrieve a complete meeting by ID",
)
def get_meeting(meeting_id: int, request: Request) -> MeetingDetailResponse:
    """Return the full meeting record including all child rows."""
    repo = _get_repo(request)
    row = repo.get_meeting(meeting_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Meeting {meeting_id} not found.",
        )
    return MeetingDetailResponse(
        id=row["id"],
        transcript=row["transcript"],
        summary=row["summary"],
        title=row.get("title"),
        meeting_date=row.get("meeting_date"),
        meeting_time=row.get("meeting_time"),
        start_time=row.get("start_time"),
        end_time=row.get("end_time"),
        created_at=row["created_at"],
        action_items=[_row_to_action_item(r) for r in row["action_items"]],
        decisions=[_row_to_decision(r) for r in row["decisions"]],
        unresolved_issues=[_row_to_issue(r) for r in row["unresolved_issues"]],
        model_name=row.get("model_name"),
        pipeline_name=row.get("pipeline_name"),
        prompt_version=row.get("prompt_version"),
        fallback_used=bool(row.get("fallback_used", 0)),
    )


# ---------------------------------------------------------------------------
# PATCH /meetings/{meeting_id}/action-items/{item_id}/status
# ---------------------------------------------------------------------------


@router.patch(
    "/meetings/{meeting_id}/action-items/{item_id}/status",
    response_model=UpdateActionItemStatusResponse,
    summary="Update an action-item status",
)
def update_action_item_status(
    meeting_id: int,
    item_id: int,
    body: UpdateActionItemStatusRequest,
    request: Request,
) -> UpdateActionItemStatusResponse:
    """Validate and apply a new status to a single action item."""
    repo = _get_repo(request)

    # Ensure the parent meeting exists
    meeting = repo.get_meeting(meeting_id)
    if meeting is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Meeting {meeting_id} not found.",
        )

    # Ensure the action item belongs to this meeting
    items = repo.get_action_items(meeting_id)
    item_ids = {item["id"] for item in items}
    if item_id not in item_ids:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Action item {item_id} not found in meeting {meeting_id}.",
        )

    updated = repo.update_action_item_status(item_id, body.status)
    return UpdateActionItemStatusResponse(
        action_item_id=item_id,
        status=body.status,
        updated=updated,
    )


# ---------------------------------------------------------------------------
# DELETE /meetings/{meeting_id}
# ---------------------------------------------------------------------------


@router.delete(
    "/meetings/{meeting_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a meeting and cascade delete all child records",
)
def delete_meeting(meeting_id: int, request: Request) -> Response:
    """Delete a meeting and cascade delete all associated child records."""
    repo = _get_repo(request)
    deleted = repo.delete_meeting(meeting_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Meeting {meeting_id} not found.",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)

