"""Orchestrator for end-to-end meeting analysis pipeline."""

import json
import os
import re
from datetime import date, timedelta
from typing import Any
from backend.ai.groq_client import GroqClient
from backend.ai.ollama_client import OllamaClient
from backend.ai.evidence_repair import repair_output
from backend.ai.prompts import build_intent_tagging_prompt, build_meeting_analysis_prompt
from backend.ai.validator import MeetingValidator
from backend.app.services.transcript_processor import TranscriptProcessor
from backend.app.services.transcript_quality import validate_meeting_transcript
from backend.models.meeting import ActionItem, Decision, UnresolvedIssue, MeetingOutput


class MeetingParseError(ValueError):
    """Raised when the LLM response cannot be parsed as structured meeting data."""
    pass


def _flatten_string_or_list(item: Any) -> str:
    """Recursively flatten nested lists/dicts to a single string."""
    if isinstance(item, str):
        return item.strip()
    if isinstance(item, list):
        return " ".join(_flatten_string_or_list(x) for x in item).strip()
    if isinstance(item, dict):
        return str(item.get("decision", item.get("issue", item.get("task", str(item))))).strip()
    return str(item).strip()


_JOINT_OWNER_RE = re.compile(
    r'^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+(?:and|&|,)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
    re.IGNORECASE,
)

_PROMPT_EXAMPLE_PHRASES = {
    "guest's travel plans",
    "budget approval",
    "finalize the event date",
}

_STATUS_ALIASES = {
    "todo": "pending",
    "to_do": "pending",
    "open": "pending",
    "not_started": "pending",
    "planned": "pending",
    "assigned": "pending",
    "confirmed": "pending",
    "active": "in_progress",
    "in progress": "in_progress",
    "done": "completed",
    "finished": "completed",
    "resolved": "completed",
    "closed": "completed",
    "settled": "completed",
}

_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_ISO_DATETIME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2})?)$")


def _is_prompt_example_leak(text: str, transcript_lower: str) -> bool:
    """Reject a known prompt example when the transcript does not support it."""
    normalized = re.sub(r"['’]", "'", text.strip().lower())
    return normalized in _PROMPT_EXAMPLE_PHRASES and normalized not in transcript_lower


def _normalize_owner(raw: str) -> str | None:
    """Normalize owner string.

    - Strips filler tokens.
    - For joint owners ("Mark and Jin"), keeps both names separated by " & ".
    - Returns None when owner cannot be resolved.
    """
    if not raw:
        return None
    raw = raw.strip()
    if raw.lower() in ("null", "none", "not specified", "unassigned", ""):
        return None
    m = _JOINT_OWNER_RE.match(raw)
    if m:
        return f"{m.group(1)} & {m.group(2)}"
    return raw


_WEEKDAY_MAP = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}


def _resolve_deadline_to_iso(deadline_str: str, meeting_date: date) -> str:
    """Convert a relative deadline expression to an ISO date string (YYYY-MM-DD).

    Falls back to the original string when the expression is not recognizable.
    """
    dl = deadline_str.strip().lower()
    datetime_match = re.fullmatch(r"(\d{4}-\d{2}-\d{2})[t ]\d{2}:\d{2}(?::\d{2})?", dl)
    if datetime_match:
        return datetime_match.group(1)
    # Normalize separators: "mid-November" → "mid november"
    dl = re.sub(r'\b(mid|early|end)-(\w)', r'\1 \2', dl)
    ref = meeting_date

    # today / tonight / right after this call|meeting
    if dl in ("today", "tonight", "right after this call", "right after this meeting"):
        return ref.isoformat()

    # tomorrow
    if dl.startswith("tomorrow"):
        return (ref + timedelta(days=1)).isoformat()

    # EOD today / EOD tomorrow
    if "eod today" in dl:
        return ref.isoformat()
    if "eod tomorrow" in dl:
        return (ref + timedelta(days=1)).isoformat()
    if dl.startswith("eod"):
        return ref.isoformat()

    # next <weekday> / <weekday> (bare or with "by", "this", "on")
    m_next_day = re.search(r'\b(?:next\s+|by\s+|this\s+|on\s+)?(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b', dl)
    if m_next_day:
        target_wd = _WEEKDAY_MAP[m_next_day.group(1)]
        cur_wd = ref.weekday()
        days_ahead = (target_wd - cur_wd) % 7
        if days_ahead == 0 and ("next" in dl or dl.startswith("next")):
            days_ahead = 7
        target_date = ref + timedelta(days=days_ahead)
        if target_date < ref:
            target_date += timedelta(days=7)
        return target_date.isoformat()

    # next week / this week
    if "next week" in dl:
        return (ref + timedelta(days=(7 - ref.weekday()))).isoformat()
    if "this week" in dl:
        return (ref + timedelta(days=(4 - ref.weekday()))).isoformat()  # Friday of this week

    # next month
    if "next month" in dl:
        if ref.month == 12:
            return date(ref.year + 1, 1, 1).isoformat()
        return date(ref.year, ref.month + 1, 1).isoformat()

    # mid-<Month> / end of <Month> / early <Month>
    MONTH_NAMES = {
        "january": 1, "february": 2, "march": 3, "april": 4,
        "may": 5, "june": 6, "july": 7, "august": 8,
        "september": 9, "october": 10, "november": 11, "december": 12,
    }
    MONTH_ABBR = {
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6,
        "jul": 7, "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
    }

    m_period = re.match(r'^(mid|end of|early)\s+(\w+)', dl)
    if m_period:
        period, mon_str = m_period.group(1), m_period.group(2)
        mon_num = MONTH_NAMES.get(mon_str) or MONTH_ABBR.get(mon_str)
        if mon_num:
            yr = ref.year if mon_num >= ref.month else ref.year + 1
            if period == "mid":
                return date(yr, mon_num, 15).isoformat()
            if period == "early":
                return date(yr, mon_num, 1).isoformat()
            # end of month: last day
            import calendar
            last_day = calendar.monthrange(yr, mon_num)[1]
            return date(yr, mon_num, last_day).isoformat()

    # <Month> <DD>
    m_date = re.match(r'^(\w+)\s+(\d{1,2})(?:st|nd|rd|th)?', dl)
    if m_date:
        mon_str, day_str = m_date.group(1), m_date.group(2)
        mon_num = MONTH_NAMES.get(mon_str) or MONTH_ABBR.get(mon_str)
        if mon_num:
            day = int(day_str)
            yr = ref.year
            # roll to next year if the date is already past
            if date(yr, mon_num, day) < ref:
                yr += 1
            return date(yr, mon_num, day).isoformat()

    # Could not resolve — return original
    return deadline_str


_HEADER_DATE_RE = re.compile(
    r'\*{0,2}(?:Date(?:\s*/\s*Time|(?:\s*Time))?)\*{0,2}\s*[:\-]?\*{0,2}\s*'
    r'(?:\w+,\s+)?'                              # optional weekday
    r'((?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)'
    r'\s+\d{1,2}(?:st|nd|rd|th)?\s*,?\s*\d{4}'  # Month DD, YYYY
    r'|\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}'          # MM/DD/YY or MM-DD-YYYY
    r'|\d{4}[/\-]\d{1,2}[/\-]\d{1,2})',           # YYYY-MM-DD
    re.IGNORECASE,
)

# Broader date pattern for transcript body (e.g. "18 September 2026, 3:00 PM")
_BODY_DATE_RE = re.compile(
    r'\b((?:January|February|March|April|May|June|July|August|September|October|November|December)'
    r'\s+\d{1,2}(?:st|nd|rd|th)?\s*,?\s*\d{4}'
    r'|\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}'
    r'|\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}'
    r'|\d{4}[/\-]\d{1,2}[/\-]\d{1,2})\b',
    re.IGNORECASE,
)

# Meeting title extraction patterns (ordered by priority)
_TITLE_BRACKET_RE = re.compile(
    r'\[Meeting:\s*([^|\]]+?)(?:\s*\|[^\]]*)?\]',
    re.IGNORECASE,
)
_TITLE_HEADER_RE = re.compile(
    r'^(?:Meeting|Subject|Topic|Title|Re)\s*[:\-]\s*(.+)$',
    re.IGNORECASE | re.MULTILINE,
)

_MONTH_NAME_MAP = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4,
    "jun": 6, "jul": 7, "aug": 8, "sep": 9, "sept": 9,
    "oct": 10, "nov": 11, "dec": 12,
}


def _extract_date_from_transcript(transcript: str) -> date | None:
    """Try to parse a meeting date from transcript header lines.

    Looks for patterns like:
    - "Date/Time: Tuesday, Oct 14, 2025"
    - "Date: 2025-10-14"
    - "Date: 10/14/2025"

    Returns a date object or None if not found.
    """
    for line in transcript.splitlines()[:30]:  # only check first 30 lines (header area)
        m = _HEADER_DATE_RE.search(line)
        if m:
            raw = m.group(1).strip().rstrip(',')
        else:
            m_day_first_header = re.search(
                r'(?i)\bdate(?:\s*/\s*time|\s*time)?\s*[:\-]\s*'
                r'(\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+\d{4})\b',
                line,
            )
            if not m_day_first_header:
                continue
            raw = m_day_first_header.group(1).strip().rstrip(',')


        # ISO: YYYY-MM-DD or YYYY/MM/DD
        m_iso = re.match(r'^(\d{4})[/\-](\d{1,2})[/\-](\d{1,2})$', raw)
        if m_iso:
            try:
                return date(int(m_iso.group(1)), int(m_iso.group(2)), int(m_iso.group(3)))
            except ValueError:
                continue

        # Numeric: MM/DD/YY or MM-DD-YYYY
        m_num = re.match(r'^(\d{1,2})[/\-](\d{1,2})[/\-](\d{2,4})$', raw)
        if m_num:
            mm, dd, yy = int(m_num.group(1)), int(m_num.group(2)), int(m_num.group(3))
            if yy < 100:
                yy += 2000
            try:
                return date(yy, mm, dd)
            except ValueError:
                continue

        # Named month: "Oct 14, 2025" or "October 14 2025"
        m_named = re.match(
            r'^(\w+)\s+(\d{1,2})(?:st|nd|rd|th)?\s*,?\s*(\d{4})$', raw, re.IGNORECASE
        )
        if m_named:
            mon_str = m_named.group(1).lower()
            mon_num = _MONTH_NAME_MAP.get(mon_str)
            if mon_num:
                try:
                    return date(int(m_named.group(3)), mon_num, int(m_named.group(2)))
                except ValueError:
                    continue

        # Day-first named month: "22 September 2026"
        m_day_first = re.match(
            r'^(\d{1,2})(?:st|nd|rd|th)?\s+(\w+)\s+(\d{4})$', raw, re.IGNORECASE
        )
        if m_day_first:
            mon_num = _MONTH_NAME_MAP.get(m_day_first.group(2).lower())
            if mon_num:
                try:
                    return date(int(m_day_first.group(3)), mon_num, int(m_day_first.group(1)))
                except ValueError:
                    continue

    return None


_TIME_RANGE_RE = re.compile(
    r'\b(\d{1,2}(?::\d{2})?\s*(?:AM|PM|am|pm)?)\s*(?:-|–|—|to)\s*(\d{1,2}(?::\d{2})?\s*(?:AM|PM|am|pm))\b',
    re.IGNORECASE,
)
_SINGLE_TIME_RE = re.compile(
    r'\b(\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)?|\d{1,2}\s*(?:AM|PM|am|pm))\b',
    re.IGNORECASE,
)
_HEADER_TIME_RE = re.compile(
    r'\*{0,2}(?:Time|Date\s*(?:&|/)\s*Time|Schedule)\*{0,2}\s*[:\-]?\*{0,2}\s*(.+)$',
    re.IGNORECASE | re.MULTILINE,
)


def _extract_time_from_transcript(transcript: str) -> tuple[str | None, str | None, str | None]:
    """Extract meeting time (full range or single time), start_time, and end_time.

    Returns: (meeting_time, start_time, end_time)
    """
    lines = transcript.splitlines()[:30]
    # Check header lines first
    for line in lines:
        m_hdr = _HEADER_TIME_RE.search(line)
        if m_hdr:
            raw_time_hdr = m_hdr.group(1).strip()
            # Try range in header
            m_rng = _TIME_RANGE_RE.search(raw_time_hdr)
            if m_rng:
                st, et = m_rng.group(1).strip(), m_rng.group(2).strip()
                return f"{st} - {et}", st, et
            # Try single time in header
            m_sgl = _SINGLE_TIME_RE.search(raw_time_hdr)
            if m_sgl:
                st = m_sgl.group(1).strip()
                return st, st, None

    # Check first 10 lines for any time range pattern
    header_block = "\n".join(lines[:10])
    m_rng = _TIME_RANGE_RE.search(header_block)
    if m_rng:
        st, et = m_rng.group(1).strip(), m_rng.group(2).strip()
        if ("am" in st.lower() or "pm" in st.lower() or ":" in st or
            "am" in et.lower() or "pm" in et.lower() or ":" in et):
            return f"{st} - {et}", st, et

    # Check for single time in first 5 lines
    for line in lines[:5]:
        m_sgl = _SINGLE_TIME_RE.search(line)
        if m_sgl:
            st = m_sgl.group(1).strip()
            if "am" in st.lower() or "pm" in st.lower():
                return st, st, None

    return None, None, None


def _extract_human_date_from_transcript(transcript: str) -> str | None:
    """Return a human-readable date string from the transcript for display purposes.

    Searches first 30 lines for a Date/Time header label, then falls back to
    any recognizable date pattern in the first 5 lines.
    Returns the raw matched string (e.g. "18 September 2026") or None.
    """
    lines = transcript.splitlines()[:30]
    # Priority 1: explicit Date/Time header label
    for line in lines:
        m = _HEADER_DATE_RE.search(line)
        if m:
            return m.group(1).strip().rstrip(',')
    # Priority 2: date mentioned inline in first 5 lines (e.g. "18 September 2026, 3:00 PM")
    for line in transcript.splitlines()[:5]:
        m = _BODY_DATE_RE.search(line)
        if m:
            return m.group(1).strip().rstrip(',')
    return None


def _extract_title_from_transcript(transcript: str) -> str | None:
    """Extract a meeting title from transcript header patterns.

    Checks (in priority order):
    1. Bracket notation: [Meeting: Annual Fest Planning | Attendees: ...]
    2. Header label:     Meeting: Annual Fest Planning
                         Subject: Annual Fest Planning
                         **Meeting:** Annual Fest Planning
    3. Markdown heading or bold title:
                         # Weekly Product Sync – Atlas Platform
                         **Weekly Product Sync – Atlas Platform**
    4. First non-empty line before date/time or dialogue
    """
    lines = [line.strip() for line in transcript.splitlines() if line.strip()]
    if not lines:
        return None
    header = "\n".join(lines[:10])

    m = _TITLE_BRACKET_RE.search(header)
    if m:
        return m.group(1).strip()

    # Clean markdown formatting from lines for header matching
    for line in lines[:6]:
        clean_line = re.sub(r'^\s*[*#_~`]+\s*|\s*[*#_~`]+\s*$', '', line).strip()
        m = re.match(r'^(?:Meeting|Subject|Topic|Title|Re)\s*[:\-]\s*(.+)$', clean_line, re.IGNORECASE)
        if m:
            raw = m.group(1).strip()
            raw = re.sub(r'^\s*[*#_~`]+\s*|\s*[*#_~`]+\s*$', '', raw).strip()
            if not re.match(r'^[\d/\-]{5,}', raw) and len(raw) > 3:
                return raw

    # Check if first line is wrapped in markdown bold or is a markdown heading
    first_line = lines[0]
    clean_first = re.sub(r'^\s*[*#_~`]+\s*|\s*[*#_~`]+\s*$', '', first_line).strip()
    is_meta = bool(re.match(r'^(?:Date|Time|Attendees?|Present|Location|Schedule|Agenda)\s*[:\-]', clean_first, re.IGNORECASE))
    is_speaker = bool(re.match(r'^[A-Z][a-zA-Z\s]{1,25}:', clean_first))

    if not is_meta and not is_speaker and len(clean_first) > 3 and len(clean_first) <= 120:
        is_md_title = bool(re.match(r'^(?:#{1,6}\s+|\*{2}|_{2})', first_line))
        next_line = lines[1] if len(lines) > 1 else ""
        is_followed_by_meta_or_dialogue = bool(
            re.search(r'^(?:\*{0,2}(?:Date|Time|Attendees?|Present|Location|Schedule|Agenda)\*{0,2}\s*[:\-])|^[A-Z][a-zA-Z\s]{1,25}:', next_line, re.IGNORECASE)
        )
        if is_md_title or is_followed_by_meta_or_dialogue:
            return clean_first

    return None


class MeetingOrchestrator:
    """Orchestrates transcript preprocessing, Ollama inference, parsing, and validation."""

    def __init__(
        self,
        client: Any | None = None,
        validator: MeetingValidator | None = None,
        temperature: float = 0.0,
        repository: Any | None = None,
        model: str | None = None,
        ollama_base_url: str = "http://localhost:11434",
        two_pass: bool = False,
        evidence_repair: bool = False,
    ):
        if client is not None:
            self.client = client
        elif os.getenv("GROQ_API_KEY", "").strip():
            self.client = GroqClient(model=model or os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b"))
        else:
            self.client = OllamaClient(model=model or "qwen2.5:3b", base_url=ollama_base_url)
        self.validator = validator or MeetingValidator()
        self.temperature = temperature
        self.repository = repository
        self.two_pass = two_pass
        self.evidence_repair = evidence_repair
        self.last_archetype = "other"

    def _classify_intents(self, transcript: str) -> str:
        """Run pass one and return validated, compact intent evidence for pass two."""
        raw_output = self.client.generate(
            prompt=build_intent_tagging_prompt(transcript),
            temperature=self.temperature,
        )
        parsed = self._parse_json(raw_output)
        archetype = parsed.get("meeting_archetype", "other")
        allowed_archetypes = {"corporate_sync", "student_casual", "technical_design", "sales", "other"}
        if archetype not in allowed_archetypes:
            archetype = "other"
        self.last_archetype = archetype

        tags = parsed.get("utterance_tags", [])
        if not isinstance(tags, list):
            raise MeetingParseError("Field 'utterance_tags' must be a list.")

        allowed_intents = {"proposal", "final_decision", "assigned_task", "unresolved_issue", "context"}
        clean_tags = []
        for tag in tags:
            if not isinstance(tag, dict) or tag.get("intent") not in allowed_intents:
                continue
            text = str(tag.get("text", "")).strip()
            if not text:
                continue
            clean_tags.append({
                "speaker": tag.get("speaker"),
                "text": text,
                "intent": tag["intent"],
            })

        return json.dumps(
            {"meeting_archetype": archetype, "utterance_tags": clean_tags},
            ensure_ascii=True,
        )

    def _parse_json(self, raw_output: str) -> dict[str, Any]:
        """Strip optional markdown formatting and parse raw JSON."""
        cleaned = (raw_output or "").strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, count=1, flags=re.IGNORECASE)
            cleaned = re.sub(r"\s*```$", "", cleaned, count=1).strip()

        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError as err:
            # Small local models occasionally add one sentence before the JSON.
            # Decode from the first object boundary while preserving strict object validation.
            start = cleaned.find("{")
            if start < 0:
                raise MeetingParseError(
                    f"Model response is not valid JSON: {err}. Preview: {raw_output[:200]}"
                ) from err
            try:
                parsed, _ = json.JSONDecoder().raw_decode(cleaned[start:])
            except json.JSONDecodeError:
                raise MeetingParseError(
                    f"Model response is not valid JSON: {err}. Preview: {raw_output[:200]}"
                ) from err

        if not isinstance(parsed, dict):
            raise MeetingParseError(
                f"Model output root must be a JSON object, got {type(parsed).__name__}."
            )

        return parsed

    def _build_models(self, data: dict[str, Any], transcript_clean: str = "", meeting_date: date | None = None) -> MeetingOutput:
        """Convert parsed dictionary to Pydantic MeetingOutput with entity and deadline resolution."""
        summary = str(data.get("summary", "")).strip()
        transcript_lower = transcript_clean.lower() if transcript_clean else ""

        # Precompile temporal regexes
        time_pattern = re.compile(
            r'\b(?:by|before|until|on|at|for|due)\s+('
            r'(?:next\s+)?(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)(?:\s+(?:morning|afternoon|evening|EOD|at\s+\d+[:\.]\d+\s*(?:AM|PM)?))?'
            r'|tomorrow(?:\s+(?:morning|afternoon|evening|at\s+\d+[:\.]\d+\s*(?:AM|PM)?|EOD))?'
            r'|\d{1,2}(?::\d{2})?\s*(?:AM|PM|am|pm)(?:\s+tomorrow)?'
            r'|EOD(?:\s+today|\s+tomorrow)?'
            r'|tonight'
            r'|today'
            r'|right after this (?:call|meeting)'
            r'|(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{1,2}(?:st|nd|rd|th)?'
            r'|(?:mid|end of|early)\s+(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?|next\s+week|this\s+week|next\s+month|Q[1-4])'
            r'|next\s+(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|week|month)'
            r')(?:\s+at\s+the\s+latest)?\b',
            re.IGNORECASE,
        )
        end_time_pattern = re.compile(
            r'(?:\s+(?:by|on|at|before|until|for)\s+)?\b(today|tonight|tomorrow|tomorrow at \d+[:\.]\d+\s*(?:AM|PM)?|next Monday|next Tuesday|next Wednesday|next Thursday|next Friday|Thursday|Friday|Monday|Tuesday|Wednesday|Saturday|Sunday|right after this call|right after this meeting)\b\s*$',
            re.IGNORECASE,
        )

        # Parse speaker dialogue turns from transcript
        turns: list[tuple[str, str]] = []
        if transcript_clean:
            for line in transcript_clean.splitlines():
                line_str = line.strip()
                m_turn = re.match(r'^\*{0,2}([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b.*?\*{0,2}[:\-]\s*(.*)$', line_str)
                if m_turn:
                    turns.append((m_turn.group(1), m_turn.group(2)))

        # Action items
        action_items: list[ActionItem] = []
        raw_actions = data.get("action_items", [])
        if not isinstance(raw_actions, list):
            raise MeetingParseError("Field 'action_items' must be a list.")

        for item in raw_actions:
            if not isinstance(item, dict):
                continue
            task = str(item.get("task", "")).strip()
            owner = _normalize_owner(str(item.get("owner") or ""))
            if owner and transcript_lower and owner.lower() not in transcript_lower:
                owner = None
            deadline = item.get("deadline")
            if deadline is not None:
                deadline = str(deadline).strip() or None
                if deadline and deadline.lower() in ("null", "none", "not specified", "no deadline"):
                    deadline = None
            status = str(item.get("status", "pending")).strip() or "pending"
            status = _STATUS_ALIASES.get(status.lower(), status)

            # Check if task itself has a prefix like "1. Marcus: Update the specs..." or "Marcus: Update..."
            match_task_lead = re.match(
                r"^(?:(?:\d+[\.\)]|\*|-|•)\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s*[:\-–—]\s*(.*)$",
                task,
            )
            if match_task_lead:
                cand_name = match_task_lead.group(1).strip()
                rest_task = match_task_lead.group(2).strip()
                if (
                    owner is None
                    and cand_name.lower() not in {"the", "we", "i", "our", "team", "someone", "action", "item", "task", "note"}
                    and (not transcript_lower or cand_name.lower() in transcript_lower)
                ):
                    owner = cand_name
                if rest_task:
                    task = rest_task

            # 1. Extract deadline from task string if present
            m_time = time_pattern.search(task)
            if m_time:
                if not deadline:
                    deadline = m_time.group(1).strip()
                matched_str = m_time.group(0).strip()
                task = re.sub(re.escape(matched_str), '', task, flags=re.IGNORECASE).strip()
                task = re.sub(r'\s{2,}', ' ', task).strip(' ,.-')

            m_end = end_time_pattern.search(task)
            if m_end:
                if not deadline:
                    deadline = m_end.group(1).strip()
                task = task[:m_end.start()].strip(' ,.-')

            # 2. If owner or deadline is still None, align with transcript turns
            if transcript_clean and task:
                task_keywords = [
                    w.lower()
                    for w in re.findall(r"\b[A-Za-z]{3,}\b", task)
                    if w.lower() not in {"the", "and", "for", "that", "with", "this", "from", "have", "make", "will"}
                ]
                if task_keywords:
                    def _extract_time_str(t: str) -> str | None:
                        m_t = time_pattern.search(t)
                        if m_t:
                            return m_t.group(1).strip()
                        m_s = re.search(
                            r'\b(today|tonight|tomorrow|tomorrow at \d+[:\.]\d+\s*(?:AM|PM)?|next Monday|next Tuesday|next Wednesday|next Thursday|next Friday|Thursday|Friday|Monday|Tuesday|Wednesday|right after this (?:call|meeting)|by EOD today|by \d+\s*(?:AM|PM)\s*tomorrow|by 9 AM tomorrow)\b',
                            t,
                            re.IGNORECASE,
                        )
                        if m_s:
                            return m_s.group(1).strip()
                        return None

                    # If owner is known, first search owner's own turns for deadline commitment
                    if owner and deadline is None:
                        best_owner_score = 0
                        best_owner_time = None
                        for idx, (spk, text) in enumerate(turns):
                            if spk.lower() in owner.lower() or owner.lower() in spk.lower():
                                prev_text = turns[idx-1][1].lower() if idx > 0 else ""
                                cur_text = text.lower()
                                o_score = sum(2 for w in task_keywords if w in cur_text) + sum(1 for w in task_keywords if w in prev_text)
                                if o_score > best_owner_score:
                                    t_found = _extract_time_str(text)
                                    if t_found:
                                        best_owner_score = o_score
                                        best_owner_time = t_found
                        if best_owner_time:
                            deadline = best_owner_time

                    # If still missing owner or deadline, perform general turn search
                    is_model_date = bool(
                        deadline
                        and (
                            _ISO_DATETIME_RE.fullmatch(deadline)
                            or (meeting_date is not None and _ISO_DATE_RE.fullmatch(deadline))
                        )
                    )
                    if owner is None or deadline is None or is_model_date:
                        best_score = 0
                        best_turn_time = None
                        best_spk = None

                        for idx, (spk, text) in enumerate(turns):
                            prev_text = turns[idx-1][1].lower() if idx > 0 else ""
                            next_text = turns[idx+1][1].lower() if idx + 1 < len(turns) else ""
                            cur_text = text.lower()

                            turn_score = sum(2 for w in task_keywords if w in cur_text)
                            window_score = sum(1 for w in task_keywords if (w in prev_text or w in next_text))
                            total_score = turn_score + window_score

                            if owner and (spk.lower() in owner.lower() or owner.lower() in spk.lower()):
                                total_score += 2

                            if total_score > best_score:
                                found_t = _extract_time_str(text)
                                if not found_t and next_text:
                                    found_t = _extract_time_str(next_text)

                                best_score = total_score
                                best_turn_time = found_t
                                best_spk = spk

                        if owner is None and best_spk and best_spk.lower() in transcript_lower:
                            owner = best_spk
                        if best_turn_time and (deadline is None or is_model_date):
                            deadline = best_turn_time

            # Resolve relative deadline to ISO date if meeting_date is provided
            if deadline and meeting_date:
                deadline = _resolve_deadline_to_iso(deadline, meeting_date)

            action_items.append(
                ActionItem(
                    task=task,
                    owner=owner,
                    deadline=deadline,
                    status=status,
                    confidence=1.0,
                )
            )

        # Decisions
        decisions: list[Decision] = []
        raw_decisions = data.get("decisions", [])
        if not isinstance(raw_decisions, list):
            raise MeetingParseError("Field 'decisions' must be a list.")

        for dec in raw_decisions:
            dec_text = _flatten_string_or_list(dec)
            dec_text = re.sub(r"^decision\s*[-:–—]\s*", "", dec_text, flags=re.IGNORECASE).strip()
            if dec_text and not _is_prompt_example_leak(dec_text, transcript_lower):
                decisions.append(Decision(decision=dec_text, confidence=1.0))

        # Unresolved issues
        unresolved_issues: list[UnresolvedIssue] = []
        raw_issues = data.get("unresolved_issues", [])
        if not isinstance(raw_issues, list):
            raise MeetingParseError("Field 'unresolved_issues' must be a list.")

        for issue in raw_issues:
            issue_text = _flatten_string_or_list(issue)
            if issue_text and not _is_prompt_example_leak(issue_text, transcript_lower):
                unresolved_issues.append(UnresolvedIssue(issue=issue_text, confidence=1.0))

        return MeetingOutput(
            summary=summary,
            action_items=action_items,
            decisions=decisions,
            unresolved_issues=unresolved_issues,
            title=None,       # populated by analyze() after transcript extraction
            meeting_date=None,
            meeting_time=None,
            start_time=None,
            end_time=None,
        )

    def analyze(self, transcript: str, meeting_date: date | None = None) -> MeetingOutput:
        """Run full meeting analysis workflow: preprocess -> prompt -> Ollama -> parse -> validate -> output.

        Args:
            transcript: Raw meeting transcript text.
            meeting_date: Optional date the meeting occurred. When supplied, relative
                deadline expressions ("tomorrow", "next Monday", "mid-November", etc.)
                are resolved to absolute ISO-8601 date strings (YYYY-MM-DD).
        """
        cleaned_transcript = validate_meeting_transcript(transcript)

        # 1. Extract title, human-readable date, and time from transcript header before preprocessing
        extracted_title = _extract_title_from_transcript(transcript)
        extracted_date_str = _extract_human_date_from_transcript(transcript)
        extracted_time_str, extracted_start_time, extracted_end_time = _extract_time_from_transcript(transcript)

        # 2. Auto-detect meeting date object from transcript header if not provided
        if meeting_date is None:
            meeting_date = _extract_date_from_transcript(transcript)

        # 3. Preprocess transcript using existing TranscriptProcessor
        cleaned_transcript = TranscriptProcessor.clean_transcript(cleaned_transcript)

        # 4. Optionally classify intent before applying the full extraction prompt.
        intent_context = None
        if self.two_pass:
            try:
                intent_context = self._classify_intents(cleaned_transcript)
            except (MeetingParseError, ValueError, TypeError, json.JSONDecodeError):
                # Pass one is a guardrail, not a hard dependency. Keep the proven
                # one-pass extraction path available when a small model misbehaves.
                self.last_archetype = "other"
                intent_context = None
        prompt = build_meeting_analysis_prompt(cleaned_transcript, intent_context=intent_context)

        # 5. Call local Ollama model
        raw_output = self.client.generate(prompt=prompt, temperature=self.temperature)

        # 6. Parse JSON
        parsed_data = self._parse_json(raw_output)

        # 7. Convert to Pydantic models with transcript context and meeting date
        meeting_output = self._build_models(parsed_data, cleaned_transcript, meeting_date)
        if self.evidence_repair:
            meeting_output = repair_output(
                meeting_output,
                cleaned_transcript,
                meeting_date=meeting_date,
                resolve_deadline=_resolve_deadline_to_iso,
            )
        meeting_output = self._sanitize_categories(meeting_output, cleaned_transcript)

        # 8. Deterministic validation
        validated_output = self.validator.validate(meeting_output, cleaned_transcript)

        # 9. Attach extracted metadata (not part of AI output, purely transcript-derived)
        validated_output.title = extracted_title
        validated_output.meeting_date = extracted_date_str
        validated_output.meeting_time = extracted_time_str
        validated_output.start_time = extracted_start_time
        validated_output.end_time = extracted_end_time
        validated_output.model_name = getattr(self.client, "model", "qwen2.5:3b")
        validated_output.pipeline_name = getattr(
            self.client,
            "pipeline_name",
            "groq_application" if isinstance(self.client, GroqClient) else "qwen_application",
        )
        validated_output.prompt_version = "backend.ai.prompts.v3-two-pass" if self.two_pass else "backend.ai.prompts.v2"
        validated_output.fallback_used = False

        return validated_output

    @staticmethod
    def _sanitize_categories(output: MeetingOutput, transcript: str) -> MeetingOutput:
        """Remove common cross-category false positives using transcript evidence."""
        action_like = re.compile(
            r"^(?:someone|anyone|[A-Z][A-Za-z'-]+)\s+(?:needs?|should|must|will|shall|can|could|would)\b|"
            r"\b(?:prepare|send|book|arrange|organize|schedule|test|draft|invite|set up|fix|confirm|update|coordinate)\b.*\b(?:by|before|tomorrow|today|next week|this week)\b",
            re.IGNORECASE,
        )
        output.decisions = [
            decision for decision in output.decisions
            if not action_like.search(decision.decision.strip())
        ]

        unresolved_cues = re.compile(
            r"\b(?:still|not confirmed|not finalized|unresolved|undecided|pending|waiting for|needs? approval|needs? discussion|unclear)\b",
            re.IGNORECASE,
        )
        transcript_lines = transcript.splitlines()
        grounded_issues: list[UnresolvedIssue] = []
        for issue in output.unresolved_issues:
            issue_words = {word.lower() for word in re.findall(r"\b[A-Za-z]{4,}\b", issue.issue)}
            has_topic_evidence = any(
                len(issue_words & {word.lower() for word in re.findall(r"\b[A-Za-z]{4,}\b", line)}) >= min(2, len(issue_words))
                for line in transcript_lines
            )
            has_unresolved_evidence = any(
                unresolved_cues.search(line)
                and len(issue_words & {word.lower() for word in re.findall(r"\b[A-Za-z]{4,}\b", line)}) >= min(2, len(issue_words))
                for line in transcript_lines
            )
            if not has_topic_evidence or has_unresolved_evidence:
                grounded_issues.append(issue)
        output.unresolved_issues = grounded_issues
        return output

    def analyze_and_save(
        self, transcript: str, repository: Any | None = None
    ) -> tuple[MeetingOutput, int]:
        """Analyze transcript and persist validated output to the repository.

        Returns:
            tuple[MeetingOutput, int]: The validated MeetingOutput and generated meeting ID.
        """
        repo = repository or self.repository
        if repo is None:
            raise ValueError("No repository provided to persist the meeting.")

        validated_output = self.analyze(transcript)
        meeting_id = repo.save_meeting(transcript=transcript, meeting_output=validated_output)
        return validated_output, meeting_id
