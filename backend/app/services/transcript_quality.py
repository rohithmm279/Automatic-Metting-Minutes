"""Deterministic input checks shared by product and research analysis paths."""

import re


_SPEAKER_TURN_RE = re.compile(
    r"(?m)^\s*(?:(?:\d+[.)]|[*#_~`]+)\s*)?([A-Za-z][A-Za-z0-9 .'-]{1,48})\s*:\s*(\S.*)$"
)
_HEADER_LABELS = {"date", "time", "meeting", "subject", "topic", "title", "attendees", "present", "location", "schedule", "agenda"}


def validate_meeting_transcript(transcript: str) -> str:
    """Return cleaned transcript text or reject input that is not dialogue."""
    if not isinstance(transcript, str):
        raise ValueError("Transcript must be text.")

    cleaned = "\n".join(line.strip() for line in transcript.splitlines() if line.strip())
    if not cleaned:
        raise ValueError("Transcript must contain non-whitespace text.")

    turns = _SPEAKER_TURN_RE.findall(cleaned)
    speakers = {
        speaker.strip().casefold()
        for speaker, _ in turns
        if speaker.strip().casefold() not in _HEADER_LABELS
    }
    has_meeting_header = bool(
        re.search(r"(?im)^\s*(?:meeting|date|subject|topic|title|attendees|agenda)\s*:", cleaned)
    )
    if not speakers or (len(speakers) < 2 and not (has_meeting_header and len(turns) >= 1)):
        raise ValueError(
            "Input does not look like a meeting transcript. Include at least two speaker turns."
        )

    return cleaned