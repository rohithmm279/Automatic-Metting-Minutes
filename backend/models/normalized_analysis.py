"""Shared internal analysis contract used across model and evaluation paths."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class NormalizedActionItem(BaseModel):
    task: str
    owner: str | None = None
    deadline: str | None = None
    status: str = "pending"
    confidence: float | None = None
    evidence: str | None = None


class NormalizedDecision(BaseModel):
    decision: str
    confidence: float | None = None
    evidence: str | None = None


class NormalizedIssue(BaseModel):
    issue: str
    confidence: float | None = None


class NormalizedMeetingAnalysis(BaseModel):
    """Canonical representation for cross-model comparison and provenance."""

    summary: str
    action_items: list[NormalizedActionItem] = Field(default_factory=list)
    decisions: list[NormalizedDecision] = Field(default_factory=list)
    unresolved_issues: list[NormalizedIssue] = Field(default_factory=list)
    title: str | None = None
    meeting_date: str | None = None
    meeting_time: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    model_name: str | None = None
    pipeline_name: str | None = None
    prompt_version: str | None = None
    fallback_used: bool = False


def normalize_analysis(
    analysis: Any,
    *,
    model_name: str | None = None,
    pipeline_name: str | None = None,
    prompt_version: str | None = None,
    fallback_used: bool = False,
) -> NormalizedMeetingAnalysis:
    """Adapt either existing meeting schema to the shared internal contract."""
    action_items = [
        NormalizedActionItem(
            task=str(item.task),
            owner=_optional_text(getattr(item, "owner", None)),
            deadline=_optional_text(getattr(item, "deadline", None)),
            status=str(getattr(item, "status", "pending") or "pending"),
            confidence=_optional_float(getattr(item, "confidence", None)),
            evidence=_optional_text(getattr(item, "evidence", None)),
        )
        for item in getattr(analysis, "action_items", [])
        if getattr(item, "task", None)
    ]

    decisions = []
    detailed_decisions = getattr(analysis, "detailed_decisions", None) or []
    if detailed_decisions:
        decisions.extend(
            NormalizedDecision(
                decision=str(item.decision),
                confidence=_optional_float(getattr(item, "confidence", None)),
                evidence=_optional_text(getattr(item, "evidence", None)),
            )
            for item in detailed_decisions
            if getattr(item, "decision", None)
        )
    else:
        for item in getattr(analysis, "decisions", []):
            text = getattr(item, "decision", item)
            if text:
                decisions.append(
                    NormalizedDecision(
                        decision=str(text),
                        confidence=_optional_float(getattr(item, "confidence", None)),
                        evidence=_optional_text(getattr(item, "evidence", None)),
                    )
                )

    issues = [
        NormalizedIssue(
            issue=str(getattr(item, "issue", item)),
            confidence=_optional_float(getattr(item, "confidence", None)),
        )
        for item in getattr(analysis, "unresolved_issues", [])
        if getattr(item, "issue", item)
    ]

    return NormalizedMeetingAnalysis(
        summary=str(getattr(analysis, "summary", "")),
        action_items=action_items,
        decisions=decisions,
        unresolved_issues=issues,
        title=_optional_text(getattr(analysis, "title", None)),
        meeting_date=_optional_text(getattr(analysis, "meeting_date", None)),
        meeting_time=_optional_text(getattr(analysis, "meeting_time", None)),
        start_time=_optional_text(getattr(analysis, "start_time", None)),
        end_time=_optional_text(getattr(analysis, "end_time", None)),
        model_name=model_name,
        pipeline_name=pipeline_name,
        prompt_version=prompt_version,
        fallback_used=fallback_used,
    )


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)