from typing import Any, Optional
from pydantic import BaseModel, Field


class MeetingRequest(BaseModel):
    transcript: str = Field(
        ...,
        min_length=1,
        description="The complete meeting transcript"
    )


class ValidationInfo(BaseModel):
    is_valid: bool = True
    grounded: bool = True
    confidence: float = 1.0
    notes: Optional[str] = None


class ActionItem(BaseModel):
    task: str
    owner: Optional[str] = None
    deadline: Optional[str] = None
    status: str = "pending"
    confidence: Optional[float] = None
    evidence: Optional[str] = None
    validation: Optional[ValidationInfo] = None


class DecisionItem(BaseModel):
    decision: str
    confidence: Optional[float] = None
    evidence: Optional[str] = None
    validation: Optional[ValidationInfo] = None


class OverallValidation(BaseModel):
    summary_grounded: bool = True
    action_items_valid: bool = True
    decisions_valid: bool = True
    all_grounded: bool = True
    issues: list[str] = []


class MeetingAnalysis(BaseModel):
    summary: str
    action_items: list[ActionItem] = []
    decisions: list[str] = []
    unresolved_issues: list[str] = []
    detailed_decisions: Optional[list[DecisionItem]] = None
    validation: Optional[OverallValidation] = None