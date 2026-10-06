"""Conservative transcript-evidence repairs for small-model extraction output."""

from __future__ import annotations

import re
from datetime import date
from typing import Callable

from backend.models.meeting import ActionItem, MeetingOutput, UnresolvedIssue


_STOPWORDS = {"the", "and", "for", "with", "that", "this", "from", "into", "will", "would", "could", "should"}
_SKIP_ACTION = re.compile(
    r"\b(?:we['’]ll|we will)\s+figure out who\b|\bwill update the group\b|"
    r"\b(?:are we|we are) still on track\b|\bwe['’]re on it\b|\bmeeting adjourned\b",
    re.I,
)
_COMMITMENT = re.compile(
    r"^(?:(?:sure|okay|alright|yes|yeah),?\s*)?(?:(i['’]ll|i will|i can)\s+|"
    r"([A-Z][A-Za-z'-]+)\s+will\s+|someone\s+needs?\s+to\s+)(.+)$",
    re.I,
)
_DEADLINE = re.compile(
    r"\s*(?:,?\s+)?(?:by|before|until|on|due|for)\s+(?:the\s+)?(?:end of\s+)?"
    r"(?:next\s+)?(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|"
    r"tomorrow|today|this\s+week|next\s+week|the\s+\d{1,2}(?:st|nd|rd|th)?|"
    r"[A-Za-z]+\s+\d{1,2}(?:st|nd|rd|th)?)\b.*$",
    re.I,
)
_FILLER_SUFFIX = re.compile(r"\s*,?\s*it can['’]t wait too long\.?$", re.I)
_SOFT_TIME_SUFFIX = re.compile(
    r"\s+(?:sometime\s+next\s+week|in\s+a\s+few\s+days|whenever\s+possible|as\s+soon\s+as\s+possible)\.?$",
    re.I,
)
_ISSUE_CUE = re.compile(
    r"\b(?:still\s+not\s+confirmed|still\s+pending|unresolved|undecided|"
    r"waiting\s+to\s+hear\s+back|needs?\s+approval|not\s+finalized)\b",
    re.I,
)
_SPEAKER = re.compile(r"^\s*(?:\d+[.)]\s*)?(?:[*#_~`]+\s*)?([A-Z][A-Za-z'-]+)\s*:\s*(.+)$")


def _tokens(text: str) -> set[str]:
    return {
        token.lower()
        for token in re.findall(r"\b[A-Za-z]{3,}\b", text)
        if token.lower() not in _STOPWORDS
    }


def _similar(left: str, right: str) -> bool:
    left_tokens, right_tokens = _tokens(left), _tokens(right)
    if not left_tokens or not right_tokens:
        return False
    overlap = len(left_tokens & right_tokens)
    return (
        overlap / len(left_tokens | right_tokens) >= 0.5
        or overlap / min(len(left_tokens), len(right_tokens)) >= 0.6
    )


def repair_output(
    output: MeetingOutput,
    transcript: str,
    meeting_date: date | None = None,
    resolve_deadline: Callable[[str, date], str] | None = None,
) -> MeetingOutput:
    """Add only explicit transcript evidence absent from the model output."""
    lines = transcript.splitlines()
    existing_tasks = [item.task for item in output.action_items]
    existing_issues = [item.issue for item in output.unresolved_issues]

    for line in lines:
        match = _SPEAKER.match(line)
        if not match:
            continue
        speaker, content = match.groups()
        if _SKIP_ACTION.search(content):
            continue

        commitment = _COMMITMENT.match(content.strip())
        if commitment:
            first_person, named_owner, raw_task = commitment.groups()
            task = _DEADLINE.sub("", raw_task).strip(" .?!,;:-")
            task = _FILLER_SUFFIX.sub("", task).strip(" .?!,;:-")
            task = _SOFT_TIME_SUFFIX.sub("", task).strip(" .?!,;:-")
            task = task[:1].upper() + task[1:] if task else task
            if not task or _similar(task, "meeting notes"):
                continue
            if any(_similar(task, existing) for existing in existing_tasks):
                continue

            owner = None if named_owner is None and first_person is None else speaker
            if raw_task.lower().startswith("someone needs"):
                owner = None
            deadline = None
            deadline_match = re.search(r"\b(?:by|before|until|on|due|for)\b(.+)$", raw_task, re.I)
            if deadline_match:
                deadline = deadline_match.group(0).strip(" .?!,;")
                if meeting_date and resolve_deadline:
                    deadline = resolve_deadline(deadline, meeting_date)

            output.action_items.append(
                ActionItem(
                    task=task[:240],
                    owner=owner,
                    deadline=deadline,
                    status="pending",
                    confidence=0.8,
                    evidence=content.strip(),
                )
            )
            existing_tasks.append(task)
            continue

        if _ISSUE_CUE.search(content):
            issue = content.strip(" .?!")
            if issue and not any(_similar(issue, existing) for existing in existing_issues):
                output.unresolved_issues.append(UnresolvedIssue(issue=issue, confidence=0.8))
                existing_issues.append(issue)

    return output
