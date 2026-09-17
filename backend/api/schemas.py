"""API-layer Pydantic schemas.

Kept separate from backend/models/meeting.py (AI/Pydantic models) and
backend/database/repository.py (SQLite rows).  These schemas define the exact
shape of every HTTP request body and response body.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# Allowed action-item statuses (mirrors validator.py ALLOWED_STATUSES)
# ---------------------------------------------------------------------------
ALLOWED_STATUSES: set[str] = {"pending", "in_progress", "completed", "cancelled"}


# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------


class CreateMeetingRequest(BaseModel):
    """POST /meetings request body."""

    transcript: str = Field(
        ...,
        min_length=1,
        description="Full meeting transcript text.",
    )

    @field_validator("transcript")
    @classmethod
    def transcript_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Transcript must contain non-whitespace text.")
        return v


class UpdateActionItemStatusRequest(BaseModel):
    """PATCH /meetings/{id}/action-items/{item_id}/status request body."""

    status: str = Field(..., description=f"New status. Allowed: {sorted(ALLOWED_STATUSES)}")

    @field_validator("status")
    @classmethod
    def status_must_be_valid(cls, v: str) -> str:
        if v not in ALLOWED_STATUSES:
            raise ValueError(
                f"Invalid status '{v}'. Allowed values: {sorted(ALLOWED_STATUSES)}"
            )
        return v


# ---------------------------------------------------------------------------
# Sub-object responses
# ---------------------------------------------------------------------------


class ActionItemResponse(BaseModel):
    id: int
    meeting_id: int
    task: str
    owner: Optional[str]
    deadline: Optional[str]
    status: str
    confidence: float
    evidence: Optional[str] = None


class DecisionResponse(BaseModel):
    id: int
    meeting_id: int
    decision: str
    confidence: float


class UnresolvedIssueResponse(BaseModel):
    id: int
    meeting_id: int
    issue: str
    confidence: float


# ---------------------------------------------------------------------------
# Top-level responses
# ---------------------------------------------------------------------------


class CreateMeetingResponse(BaseModel):
    """POST /meetings response."""

    meeting_id: int
    summary: str
    action_items: list[ActionItemResponse]
    decisions: list[DecisionResponse]
    unresolved_issues: list[UnresolvedIssueResponse]
    created_at: str


class MeetingListItem(BaseModel):
    """Single item in GET /meetings list."""

    id: int
    summary: str
    created_at: str
    action_items_count: int
    decisions_count: int
    unresolved_issues_count: int


class MeetingDetailResponse(BaseModel):
    """GET /meetings/{id} response."""

    id: int
    transcript: str
    summary: str
    created_at: str
    action_items: list[ActionItemResponse]
    decisions: list[DecisionResponse]
    unresolved_issues: list[UnresolvedIssueResponse]


class UpdateActionItemStatusResponse(BaseModel):
    """PATCH .../status response."""

    action_item_id: int
    status: str
    updated: bool
