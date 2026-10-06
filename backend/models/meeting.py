from typing import Optional
from pydantic import BaseModel, Field


class ActionItem(BaseModel):
    task: str = Field(..., description="Core actionable task description")
    owner: Optional[str] = Field(default=None, description="Explicit owner assigned to task, or None")
    assignee: Optional[str] = Field(default=None, description="Alias for owner")
    deadline: Optional[str] = Field(default=None, description="Explicit deadline or timeframe, or None")
    status: str = Field(default="pending", description="Status of the action item")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence score between 0.0 and 1.0")
    confidence_score: Optional[float] = Field(default=None, description="Confidence score alias")
    evidence: Optional[str] = Field(default=None, description="Direct quote or supporting snippet from the transcript, or None")


class Decision(BaseModel):
    decision: str = Field(..., description="Explicit agreement or decision made")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence score between 0.0 and 1.0")


class UnresolvedIssue(BaseModel):
    issue: str = Field(..., description="Pending, undecided, or unresolved matter")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence score between 0.0 and 1.0")


class MeetingOutput(BaseModel):
    summary: str = Field(..., description="Concise 3-5 sentence meeting summary")
    action_items: list[ActionItem] = Field(default_factory=list, description="List of action items")
    decisions: list[Decision] = Field(default_factory=list, description="List of confirmed decisions")
    unresolved_issues: list[UnresolvedIssue] = Field(default_factory=list, description="List of unresolved issues")
    title: Optional[str] = Field(default=None, description="Extracted or user-confirmed meeting title")
    meeting_date: Optional[str] = Field(default=None, description="Human-readable meeting date extracted from transcript")
    meeting_time: Optional[str] = Field(default=None, description="Meeting time range or start time string extracted from transcript")
    start_time: Optional[str] = Field(default=None, description="Meeting start time extracted from transcript")
    end_time: Optional[str] = Field(default=None, description="Meeting end time extracted from transcript if available")
    model_name: Optional[str] = Field(default=None, description="Model used to generate the analysis")
    pipeline_name: Optional[str] = Field(default=None, description="Pipeline that generated the analysis")
    prompt_version: Optional[str] = Field(default=None, description="Prompt version used for the analysis")
    fallback_used: bool = Field(default=False, description="Whether a fallback analyzer generated the output")
