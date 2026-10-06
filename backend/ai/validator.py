"""Deterministic validator for meeting intelligence outputs."""

import re
from datetime import date, timedelta
from backend.models.meeting import MeetingOutput, ActionItem, Decision, UnresolvedIssue

ALLOWED_STATUSES = {"pending", "in_progress", "completed", "cancelled"}


class MeetingValidationError(ValueError):
    """Raised when extracted meeting data fails validation."""
    pass


class MeetingValidator:
    """Validates MeetingOutput structures and checks grounding against transcript."""

    def __init__(self, allowed_statuses: set[str] | None = None):
        self.allowed_statuses = allowed_statuses or ALLOWED_STATUSES

    @staticmethod
    def _supported_iso_dates(transcript: str) -> set[str]:
        """Return ISO dates supported by header dates and relative date phrases."""
        meeting_date = None
        header_patterns = (
            r"(?i)\bdate\s*[:\-]\s*(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})\b",
            r"(?i)\bdate\s*[:\-]\s*([A-Za-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?[,]?\s+(\d{4})\b",
            r"(?i)\bdate\s*[:\-]\s*(\d{4})[-/]((?:0?[1-9]|1[0-2]))[-/](\d{1,2})\b",
        )
        header = next(
            (match for pattern in header_patterns if (match := re.search(pattern, transcript))),
            None,
        )
        if header:
            first, second, third = header.groups()
            months = {
                "january": 1, "jan": 1, "february": 2, "feb": 2,
                "march": 3, "mar": 3, "april": 4, "apr": 4,
                "may": 5, "june": 6, "jun": 6, "july": 7, "jul": 7,
                "august": 8, "aug": 8, "september": 9, "sep": 9, "sept": 9,
                "october": 10, "oct": 10, "november": 11, "nov": 11,
                "december": 12, "dec": 12,
            }
            if first.isdigit() and len(first) == 4:
                year, month, day = int(first), int(second), int(third)
            elif first.isdigit():
                year, month, day = int(third), months.get(second.lower(), 0), int(first)
            else:
                year, month, day = int(third), months.get(first.lower(), 0), int(second)
            if month:
                try:
                    meeting_date = date(year, month, day)
                except ValueError:
                    pass

        supported: set[str] = set()
        if meeting_date:
            supported.add(meeting_date.isoformat())
            if re.search(r"\b(?:today|tonight|eod)\b", transcript, re.I):
                supported.add(meeting_date.isoformat())
            if re.search(r"\btomorrow\b", transcript, re.I):
                supported.add((meeting_date + timedelta(days=1)).isoformat())

            weekdays = {
                "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
                "friday": 4, "saturday": 5, "sunday": 6,
            }
            for weekday_name, weekday_number in weekdays.items():
                if re.search(rf"\b{weekday_name}\b", transcript, re.I):
                    days_ahead = (weekday_number - meeting_date.weekday()) % 7
                    if days_ahead == 0:
                        days_ahead = 7
                    supported.add((meeting_date + timedelta(days=days_ahead)).isoformat())

        for match in re.finditer(r"\b\d{4}-\d{2}-\d{2}\b", transcript):
            try:
                supported.add(date.fromisoformat(match.group(0)).isoformat())
            except ValueError:
                pass
        return supported

    def validate(self, output: MeetingOutput, transcript: str) -> MeetingOutput:
        """Run all deterministic validations against the MeetingOutput and transcript."""
        if not isinstance(output, MeetingOutput):
            raise MeetingValidationError("Output must be an instance of MeetingOutput.")

        if not transcript or not transcript.strip():
            raise MeetingValidationError("Transcript must not be empty.")

        transcript_lower = transcript.lower()

        # 1. Summary validation
        if not output.summary or not output.summary.strip():
            raise MeetingValidationError("Meeting summary must be a non-empty string.")

        # 2. Action items validation
        for idx, item in enumerate(output.action_items):
            if not isinstance(item, ActionItem):
                raise MeetingValidationError(f"Action item at index {idx} is not an ActionItem instance.")

            if not item.task or not item.task.strip():
                raise MeetingValidationError(f"Action item at index {idx} has an empty task.")

            if item.status not in self.allowed_statuses:
                raise MeetingValidationError(
                    f"Action item at index {idx} has invalid status '{item.status}'. "
                    f"Must be one of {self.allowed_statuses}."
                )

            if not (0.0 <= item.confidence <= 1.0):
                raise MeetingValidationError(
                    f"Action item at index {idx} has invalid confidence {item.confidence}. Must be in [0.0, 1.0]."
                )

            # Check owner against transcript
            if item.owner is not None:
                cleaned_owner = item.owner.strip()
                if not cleaned_owner:
                    item.owner = None
                elif cleaned_owner.lower() not in transcript_lower:
                    raise MeetingValidationError(
                        f"Action item at index {idx} references owner '{item.owner}' which is not in the transcript."
                    )

            # Check deadline against transcript (token grounding to support multi-turn composite deadlines)
            if item.deadline is not None:
                cleaned_deadline = item.deadline.strip()
                if not cleaned_deadline or cleaned_deadline.lower() in ("not specified", "null", "none", "no deadline"):
                    item.deadline = None
                elif cleaned_deadline.lower() not in transcript_lower:
                    MONTH_MAP = {
                        "jan": ["january", "jan"],
                        "january": ["january", "jan"],
                        "feb": ["february", "feb"],
                        "february": ["february", "feb"],
                        "mar": ["march", "mar"],
                        "march": ["march", "mar"],
                        "apr": ["april", "apr"],
                        "april": ["april", "apr"],
                        "may": ["may"],
                        "jun": ["june", "jun"],
                        "june": ["june", "jun"],
                        "jul": ["july", "jul"],
                        "july": ["july", "jul"],
                        "aug": ["august", "aug"],
                        "august": ["august", "aug"],
                        "sep": ["september", "sep", "sept"],
                        "sept": ["september", "sep", "sept"],
                        "september": ["september", "sep", "sept"],
                        "oct": ["october", "oct"],
                        "october": ["october", "oct"],
                        "nov": ["november", "nov"],
                        "november": ["november", "nov"],
                        "dec": ["december", "dec"],
                        "december": ["december", "dec"],
                        "01": ["january", "jan", "1st", "1"],
                        "02": ["february", "feb", "2nd", "2"],
                        "03": ["march", "mar", "3rd", "3"],
                        "04": ["april", "apr", "4th", "4"],
                        "05": ["may", "5th", "5"],
                        "06": ["june", "jun", "6th", "6"],
                        "07": ["july", "jul", "7th", "7"],
                        "08": ["august", "aug", "8th", "8"],
                        "09": ["september", "sep", "sept", "9th", "9"],
                        "10": ["october", "oct", "10th", "10"],
                        "11": ["november", "nov", "11th", "11"],
                        "12": ["december", "dec", "12th", "12"],
                        "1": ["january", "jan", "1st", "1"],
                        "2": ["february", "feb", "2nd", "2"],
                        "3": ["march", "mar", "3rd", "3"],
                        "4": ["april", "apr", "4th", "4"],
                        "5": ["may", "5th", "5"],
                        "6": ["june", "jun", "6th", "6"],
                        "7": ["july", "jul", "7th", "7"],
                        "8": ["august", "aug", "8th", "8"],
                        "9": ["september", "sep", "sept", "9th", "9"],
                    }
                    WEEKDAY_MAP = {
                        "mon": ["monday", "mon"],
                        "monday": ["monday", "mon"],
                        "tue": ["tuesday", "tue", "tues"],
                        "tues": ["tuesday", "tue", "tues"],
                        "tuesday": ["tuesday", "tue", "tues"],
                        "wed": ["wednesday", "wed"],
                        "wednesday": ["wednesday", "wed"],
                        "thu": ["thursday", "thu", "thur", "thurs"],
                        "thur": ["thursday", "thu", "thur", "thurs"],
                        "thurs": ["thursday", "thu", "thur", "thurs"],
                        "thursday": ["thursday", "thu", "thur", "thurs"],
                        "fri": ["friday", "fri"],
                        "friday": ["friday", "fri"],
                        "sat": ["saturday", "sat"],
                        "saturday": ["saturday", "sat"],
                        "sun": ["sunday", "sun"],
                        "sunday": ["sunday", "sun"],
                    }
                    is_iso_date = bool(re.match(r"^\d{4}-\d{2}-\d{2}$", cleaned_deadline))
                    if is_iso_date:
                        supported_dates = self._supported_iso_dates(transcript)
                        if cleaned_deadline in supported_dates:
                            continue
                        has_meeting_header = bool(
                            re.search(
                                r"(?i)\bdate\s*[:\-]\s*(?:\d{1,2}\s+[A-Za-z]+\s+\d{4}|[A-Za-z]+\s+\d{1,2},?\s+\d{4})\b",
                                transcript,
                            )
                        )
                        if has_meeting_header:
                            raise MeetingValidationError(
                                f"Action item at index {idx} references deadline '{item.deadline}' which is not in the transcript."
                            )
                        # With no absolute meeting date, an ISO value can only be
                        # grounded by an explicit relative phrase in the source.
                        # Do not reject the normalized value merely because the
                        # transcript contains the original phrase rather than ISO text.
                        if re.search(
                            r"\b(?:today|tonight|tomorrow|eod|end of (?:this|the) week|"
                            r"next week|next month|(?:next\s+)?(?:monday|tuesday|wednesday|"
                            r"thursday|friday|saturday|sunday))\b",
                            transcript,
                            re.IGNORECASE,
                        ):
                            continue
                    has_temporal_context = any(
                        term in transcript_lower
                        for term in (
                            "today", "tomorrow", "tonight", "yesterday", "eod", "end of day",
                            "mon", "monday", "tue", "tues", "tuesday", "wed", "wednesday",
                            "thu", "thur", "thurs", "thursday", "fri", "friday", "sat", "saturday", "sun", "sunday",
                            "next", "this", "week", "month", "mid", "early", "end", "soon", "asap",
                            "january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december",
                            "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "sept", "oct", "nov", "dec",
                            "date", "time", "deadline", "by", "before", "due", "until", "after", "schedule", "scheduled",
                        )
                    )

                    dl_tokens = [
                        w for w in re.findall(r"\b[A-Za-z0-9]+\b", cleaned_deadline.lower())
                        if w not in {"of", "by", "the", "at", "on", "in", "and", "or", "to", "for", "eod", "end", "day", "date", "due", "before", "until"}
                    ]
                    if dl_tokens:
                        def _token_grounded(t: str, other_grounded: bool = False) -> bool:
                            if t in transcript_lower:
                                return True
                            expanded_months = MONTH_MAP.get(t)
                            if expanded_months and any(m in transcript_lower for m in expanded_months):
                                return True
                            expanded_days = WEEKDAY_MAP.get(t)
                            if expanded_days and any(d in transcript_lower for d in expanded_days):
                                return True
                            num_match = re.match(r"^(\d+)(?:st|nd|rd|th)?$", t)
                            if num_match:
                                num = num_match.group(1)
                                if num in transcript_lower:
                                    return True
                                for sfx in ("st", "nd", "rd", "th"):
                                    if f"{num}{sfx}" in transcript_lower:
                                        return True
                                if num.startswith("0") and num.lstrip("0") in transcript_lower:
                                    return True
                            if re.match(r"^\d{4}$", t) and other_grounded:
                                return True
                            return False

                        non_year_tokens = [t for t in dl_tokens if not re.match(r"^\d{4}$", t)]
                        has_grounded_non_year = any(_token_grounded(t) for t in non_year_tokens)

                        if not all(_token_grounded(token, other_grounded=has_grounded_non_year) for token in dl_tokens):
                            raise MeetingValidationError(
                                f"Action item at index {idx} references deadline '{item.deadline}' which is not in the transcript."
                            )

        # 3. Decisions validation
        for idx, dec in enumerate(output.decisions):
            if not isinstance(dec, Decision):
                raise MeetingValidationError(f"Decision at index {idx} is not a Decision instance.")

            if not dec.decision or not dec.decision.strip():
                raise MeetingValidationError(f"Decision at index {idx} has an empty decision text.")

            if not (0.0 <= dec.confidence <= 1.0):
                raise MeetingValidationError(
                    f"Decision at index {idx} has invalid confidence {dec.confidence}. Must be in [0.0, 1.0]."
                )

        # 4. Unresolved issues validation
        for idx, issue in enumerate(output.unresolved_issues):
            if not isinstance(issue, UnresolvedIssue):
                raise MeetingValidationError(f"Unresolved issue at index {idx} is not an UnresolvedIssue instance.")

            if not issue.issue or not issue.issue.strip():
                raise MeetingValidationError(f"Unresolved issue at index {idx} has an empty issue text.")

            if not (0.0 <= issue.confidence <= 1.0):
                raise MeetingValidationError(
                    f"Unresolved issue at index {idx} has invalid confidence {issue.confidence}. Must be in [0.0, 1.0]."
                )

        return output
