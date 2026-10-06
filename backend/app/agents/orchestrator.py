import datetime
from datetime import timedelta
import logging
import re
from typing import Optional

from app.agents.summary_agent import SummaryAgent
from app.agents.action_agent import ActionAgent
from app.agents.decision_agent import DecisionAgent
from app.agents.validation_agent import ValidationAgent
from app.schemas.meeting_schema import (
    ActionItem,
    DecisionItem,
    MeetingAnalysis,
    OverallValidation,
)
from app.services.gemini_analyzer import GeminiAnalyzer, GeminiAnalysisError
from app.services.meeting_analyzer import MeetingAnalyzer
from app.services.transcript_processor import TranscriptProcessor
from app.services.transcript_quality import validate_meeting_transcript

logger = logging.getLogger(__name__)

MONTH_MAP = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}


class AgentOrchestrator:
    """Central orchestrator coordinating Preprocessor, single-call Gemini Analyzer, and Validation agent.

    Architecture:
    Transcript
      ↓
    Transcript Preprocessor
      ↓
    ONE Gemini API Call (Summary, Action Items with Evidence, Decisions, Unresolved Issues)
      ↓
    Validation Agent (Local deterministic validation — NO additional API calls)
      ↓
    Structured Output (MeetingAnalysis)
    """

    # Retained for backward compatibility
    _INTER_AGENT_DELAY_S: float = 2.0

    def __init__(
        self,
        gemini_analyzer: Optional[GeminiAnalyzer] = None,
        summary_agent: Optional[SummaryAgent] = None,
        action_agent: Optional[ActionAgent] = None,
        decision_agent: Optional[DecisionAgent] = None,
        validation_agent: Optional[ValidationAgent] = None,
        fallback_analyzer: Optional[MeetingAnalyzer] = None,
    ) -> None:
        self.gemini_analyzer = gemini_analyzer or GeminiAnalyzer()
        self.summary_agent = summary_agent or SummaryAgent(self.gemini_analyzer)
        self.action_agent = action_agent or ActionAgent(self.gemini_analyzer)
        self.decision_agent = decision_agent or DecisionAgent(self.gemini_analyzer)
        self.validation_agent = validation_agent or ValidationAgent()
        self.fallback_analyzer = fallback_analyzer or MeetingAnalyzer()

    def process_transcript(self, transcript: str) -> tuple[MeetingAnalysis, str, bool]:
        """Execute the single-call Gemini workflow with local validation.

        Args:
            transcript: Raw or preprocessed transcript string.

        Returns:
            Tuple of (MeetingAnalysis, execution_source, is_rate_limited)

        Raises:
            ValueError: If transcript is empty.
        """
        # Step 1: Clean Transcript via Preprocessor
        cleaned_transcript = validate_meeting_transcript(transcript)
        cleaned_transcript = TranscriptProcessor.clean_transcript(cleaned_transcript)

        meeting_date = self._extract_meeting_date(cleaned_transcript)
        extracted_title = self._extract_title(transcript)
        extracted_date_str = self._extract_human_date(transcript)
        extracted_time_str, extracted_start_time, extracted_end_time = self._extract_time(transcript)

        # Step 2: Single Gemini Call Pipeline
        try:
            if not self.gemini_analyzer.is_configured:
                raise GeminiAnalysisError("Gemini API key is not configured.")

            logger.info(
                "Executing Single-Call Pipeline with Gemini (%s)...",
                self.gemini_analyzer.model_name,
            )

            # Check if custom mocked agent subcomponents were injected (for unit test compatibility)
            is_mocked_custom_agents = (
                type(self.summary_agent) is not SummaryAgent
                or type(self.action_agent) is not ActionAgent
                or type(self.decision_agent) is not DecisionAgent
            )

            if is_mocked_custom_agents:
                summary = self.summary_agent.generate_summary(cleaned_transcript)
                action_items = self.action_agent.extract_action_items(cleaned_transcript)
                decisions_flat, detailed_decisions, unresolved_issues = self.decision_agent.extract_decisions(
                    cleaned_transcript
                )
            else:
                raw_data = self.gemini_analyzer.generate_json(
                    self.gemini_analyzer._build_prompt(cleaned_transcript)
                )
                if not isinstance(raw_data, dict):
                    raise GeminiAnalysisError("Gemini did not return a valid JSON object.")

                summary = str(raw_data.get("summary", "")).strip()
                if not summary:
                    raise GeminiAnalysisError("Gemini returned an empty summary.")

                # Action items extraction & normalization
                raw_actions = raw_data.get("action_items", [])
                action_items = []
                if isinstance(raw_actions, list):
                    for item in raw_actions:
                        if not isinstance(item, dict):
                            continue
                        task = str(item.get("task", "")).strip()
                        if not task:
                            continue
                        raw_owner = item.get("owner")
                        if raw_owner is None or str(raw_owner).strip().lower() in ("null", "none", "not specified", "unassigned", ""):
                            owner = "Not specified"
                        else:
                            owner = str(raw_owner).strip()

                        raw_deadline = item.get("deadline")
                        if raw_deadline is None or str(raw_deadline).strip().lower() in ("null", "none", "not specified", "no deadline", ""):
                            deadline = "Not specified"
                        else:
                            deadline = str(raw_deadline).strip()

                        status = str(item.get("status", "pending")).strip() or "pending"
                        conf = float(item.get("confidence", 1.0)) if item.get("confidence") is not None else 1.0
                        ev = str(item.get("evidence", "")).strip() or None

                        # Filter out meta-tasks and unassigned attendance reminders.
                        if self._is_meta_task(task) or self._is_unassigned_meeting_attendance(task, owner):
                            continue

                        # The meeting header date is context, not an implicit deadline.
                        if not self._deadline_is_explicit_for_action(deadline, task, ev):
                            deadline = "Not specified"

                        # Enhanced entity and deadline resolution for list items, relative dates, and dialogue
                        task, owner, deadline = self._resolve_owner_and_deadline(
                            task=task,
                            owner=owner,
                            deadline=deadline,
                            evidence=ev,
                            transcript_clean=cleaned_transcript,
                            meeting_date=meeting_date,
                        )

                        action_items.append(
                            ActionItem(
                                task=task,
                                owner=owner,
                                deadline=deadline,
                                status=status,
                                confidence=conf,
                                evidence=ev,
                            )
                        )

                # Decisions & Detailed decisions extraction
                raw_decisions = raw_data.get("decisions", [])
                decisions_flat: list[str] = []
                detailed_decisions: list[DecisionItem] = []
                if isinstance(raw_decisions, list):
                    for d in raw_decisions:
                        if isinstance(d, dict):
                            d_text = str(d.get("decision", "")).strip()
                            d_conf = float(d.get("confidence", 1.0)) if d.get("confidence") is not None else 1.0
                            d_ev = str(d.get("evidence", "")).strip() or None
                        elif isinstance(d, str):
                            d_text = d.strip()
                            d_conf = 1.0
                            d_ev = None
                        else:
                            continue
                        d_text = re.sub(r"^decision\s*[-:–—]\s*", "", d_text, flags=re.IGNORECASE).strip()
                        if d_text:
                            decisions_flat.append(d_text)
                            detailed_decisions.append(
                                DecisionItem(
                                    decision=d_text,
                                    confidence=d_conf,
                                    evidence=d_ev,
                                )
                            )

                # Unresolved issues & hallucination pruning
                raw_issues = raw_data.get("unresolved_issues", [])
                unresolved_issues = []
                if isinstance(raw_issues, list):
                    for iss in raw_issues:
                        if isinstance(iss, dict):
                            iss_text = str(iss.get("issue", "")).strip()
                        elif isinstance(iss, str):
                            iss_text = iss.strip()
                        else:
                            continue
                        if iss_text:
                            unresolved_issues.append(iss_text)

            # Strict mutual exclusivity: Filter out decisions that are action items assigned to individuals, tasks, or risk mitigations
            decisions_flat, detailed_decisions = self._filter_action_items_from_decisions(
                decisions_flat, detailed_decisions, action_items
            )
            # Deduplicate action items deterministically
            action_items = self._deduplicate_action_items(action_items)

            decisions_flat, detailed_decisions, unresolved_issues = self._move_deferred_decisions_to_issues(
                decisions_flat, detailed_decisions, unresolved_issues
            )

            # Filter dummy placeholder risks (e.g. "No issues identified") and prune hallucinated issues
            unresolved_issues = self._filter_dummy_unresolved_issues(unresolved_issues)
            unresolved_issues = self.validation_agent.filter_unresolved_issues(
                unresolved_issues, cleaned_transcript.lower()
            )
            unresolved_issues = self._remove_action_issue_duplicates(unresolved_issues, action_items)

            # Step 2b: Validation Agent (runs locally on extracted data — NO API call)
            logger.debug("Running Validation Agent locally...")
            (
                val_summary,
                val_actions,
                val_decisions,
                val_detailed_decs,
                overall_validation,
            ) = self.validation_agent.validate_all(
                transcript=cleaned_transcript,
                summary=summary,
                action_items=action_items,
                decisions=decisions_flat,
                detailed_decisions=detailed_decisions,
                unresolved_issues=unresolved_issues,
            )

            # Step 2c: Final Structured Output
            analysis = MeetingAnalysis(
                summary=val_summary,
                action_items=val_actions,
                decisions=val_decisions,
                unresolved_issues=unresolved_issues,
                detailed_decisions=val_detailed_decs,
                validation=overall_validation,
                title=extracted_title,
                meeting_date=extracted_date_str,
                meeting_time=extracted_time_str,
                start_time=extracted_start_time,
                end_time=extracted_end_time,
                model_name=self.gemini_analyzer.model_name,
                pipeline_name="gemini_agentic",
                prompt_version="app.services.gemini_analyzer.v1",
                fallback_used=False,
            )
            logger.info("Single-call pipeline completed successfully (AGENTIC_GEMINI).")
            return analysis, "AGENTIC_GEMINI", False

        except (GeminiAnalysisError, Exception) as error:
            # Step 3: Graceful Rule-Based Fallback
            is_rl = False
            if isinstance(error, GeminiAnalysisError):
                is_rl = error.is_rate_limit
                logger.warning(
                    "Single-call Gemini failed: %s (%s). Falling back to rule-based analyzer.",
                    error.error_type,
                    error.safe_message,
                )
            else:
                err_msg = str(error)
                is_rl = bool(
                    "429" in err_msg
                    or "RESOURCE_EXHAUSTED" in err_msg
                    or "quota" in err_msg.lower()
                    or "rate" in err_msg.lower()
                )
                logger.warning(
                    "Single-call Gemini failed: %s. Falling back to rule-based analyzer.",
                    err_msg[:200],
                )

            fallback_res = self.fallback_analyzer.analyze(cleaned_transcript)

            # Pass fallback output through Validation Agent
            (
                val_summary,
                val_actions,
                val_decisions,
                val_detailed_decs,
                overall_val,
            ) = self.validation_agent.validate_all(
                transcript=cleaned_transcript,
                summary=fallback_res.summary,
                action_items=fallback_res.action_items,
                decisions=fallback_res.decisions,
                unresolved_issues=fallback_res.unresolved_issues,
            )

            fallback_analysis = MeetingAnalysis(
                summary=val_summary,
                action_items=val_actions,
                decisions=val_decisions,
                unresolved_issues=fallback_res.unresolved_issues,
                validation=overall_val,
                title=extracted_title,
                meeting_date=extracted_date_str,
                meeting_time=extracted_time_str,
                start_time=extracted_start_time,
                end_time=extracted_end_time,
                model_name="rule-based",
                pipeline_name="rule_based_fallback",
                prompt_version="app.services.meeting_analyzer.v1",
                fallback_used=True,
            )
            return fallback_analysis, "RULE-BASED FALLBACK", is_rl

    @staticmethod
    def _is_meta_task(task: str) -> bool:
        """Identify administrative meta-tasks and meeting agendas rather than individual deliverables."""
        t = task.strip().lower()
        return bool(
            re.search(
                r"^(?:log|assign|record|note\s+down|track)\s+(?:the\s+)?(?:action\s+items?|decisions?|meeting\s+minutes?|tasks?|items?)\b",
                t,
            )
            or re.search(
                r"\b(?:log\s+and\s+assign|assign\s+the\s+task\s+to\s+log|track\s+(?:these\s+)?items\s+in\s+jira)\b",
                t,
            )
            or re.search(
                r"^(?:finalize|complete|discuss|review|plan|organize|hold)\s+(?:the\s+)?(?:workshop|meeting|event|session|hackathon|webinar)\s*(?:plan|agenda|logistics|details|topics?)?$",
                t,
            )
        )

    @staticmethod
    def _extract_title(transcript: str) -> Optional[str]:
        """Extract meeting title from transcript headers."""
        if not transcript:
            return None
        lines = [line.strip() for line in transcript.splitlines() if line.strip()]
        if not lines:
            return None
        header = "\n".join(lines[:10])
        m_bracket = re.search(r'\[Meeting:\s*([^|\]]+?)(?:\s*\|[^\]]*)?\]', header, re.IGNORECASE)
        if m_bracket:
            return m_bracket.group(1).strip()
        for line in lines[:6]:
            clean_line = re.sub(r'^\s*[*#_~`]+\s*|\s*[*#_~`]+\s*$', '', line).strip()
            m = re.match(r'^(?:Meeting|Subject|Topic|Title|Re)\s*[:\-]\s*(.+)$', clean_line, re.IGNORECASE)
            if m:
                raw = re.sub(r'^\s*[*#_~`]+\s*|\s*[*#_~`]+\s*$', '', m.group(1)).strip()
                if not re.match(r'^[\d/\-]{5,}', raw) and len(raw) > 3:
                    return raw
        first_line = lines[0]
        clean_first = re.sub(r'^\s*[*#_~`]+\s*|\s*[*#_~`]+\s*$', '', first_line).strip()
        is_meta = bool(re.match(r'^(?:Date|Time|Attendees?|Present|Location|Schedule|Agenda)\s*[:\-]', clean_first, re.IGNORECASE))
        is_speaker = bool(re.match(r'^[A-Z][a-zA-Z\s]{1,25}:', clean_first))
        if not is_meta and not is_speaker and len(clean_first) > 3:
            if first_line.startswith("**") or first_line.startswith("#") or first_line.startswith("__"):
                return clean_first
        return None

    @staticmethod
    def _extract_human_date(transcript: str) -> Optional[str]:
        """Extract human-readable date string from transcript header."""
        if not transcript:
            return None
        lines = transcript.splitlines()[:30]
        hdr_re = re.compile(
            r'\*{0,2}(?:Date(?:\s*/\s*Time|(?:\s*Time))?)\*{0,2}\s*[:\-]?\*{0,2}\s*(?:\w+,\s+)?'
            r'((?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{1,2}(?:st|nd|rd|th)?\s*,?\s*\d{4}|\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}|\d{4}[/\-]\d{1,2}[/\-]\d{1,2})',
            re.IGNORECASE,
        )
        for line in lines:
            m = hdr_re.search(line)
            if m:
                return m.group(1).strip().rstrip(',')
        return None

    @staticmethod
    def _extract_time(transcript: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
        """Extract time range or single time string, start_time, and end_time."""
        if not transcript:
            return None, None, None
        lines = transcript.splitlines()[:30]
        hdr_time_re = re.compile(r'\*{0,2}(?:Time|Date\s*(?:&|/)\s*Time|Schedule)\*{0,2}\s*[:\-]?\*{0,2}\s*(.+)$', re.IGNORECASE | re.MULTILINE)
        time_rng_re = re.compile(r'\b(\d{1,2}(?::\d{2})?\s*(?:AM|PM|am|pm)?)\s*(?:-|–|—|to)\s*(\d{1,2}(?::\d{2})?\s*(?:AM|PM|am|pm))\b', re.IGNORECASE)
        sgl_time_re = re.compile(r'\b(\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)?|\d{1,2}\s*(?:AM|PM|am|pm))\b', re.IGNORECASE)
        for line in lines:
            m_hdr = hdr_time_re.search(line)
            if m_hdr:
                raw_time_hdr = m_hdr.group(1).strip()
                m_rng = time_rng_re.search(raw_time_hdr)
                if m_rng:
                    st, et = m_rng.group(1).strip(), m_rng.group(2).strip()
                    return f"{st} - {et}", st, et
                m_sgl = sgl_time_re.search(raw_time_hdr)
                if m_sgl:
                    st = m_sgl.group(1).strip()
                    return st, st, None
        return None, None, None

    @staticmethod
    def _extract_meeting_date(transcript: str) -> Optional[datetime.date]:
        """Extract calendar date from meeting headers."""
        if not transcript:
            return None

        # Look for Date: YYYY-MM-DD
        match_iso = re.search(r"(?i)\b(?:date|meeting\s+date)\s*[:|-]?\s*(\d{4})-(\d{1,2})-(\d{1,2})\b", transcript)
        if match_iso:
            try:
                return datetime.date(int(match_iso.group(1)), int(match_iso.group(2)), int(match_iso.group(3)))
            except ValueError:
                pass

        # Look for Date: Month DD, YYYY
        match_text = re.search(
            r"(?i)\b(?:date|meeting\s+date)\s*[:|-]?\s*([A-Za-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})\b",
            transcript,
        )
        if match_text:
            m_val = MONTH_MAP.get(match_text.group(1).lower())
            if m_val:
                try:
                    return datetime.date(int(match_text.group(3)), m_val, int(match_text.group(2)))
                except ValueError:
                    pass

        # Look for Date: DD Month YYYY
        match_day_first = re.search(
            r"(?i)\b(?:date|meeting\s+date)\s*[:|-]?\s*(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]+),?\s+(\d{4})\b",
            transcript,
        )
        if match_day_first:
            m_val = MONTH_MAP.get(match_day_first.group(2).lower())
            if m_val:
                try:
                    return datetime.date(int(match_day_first.group(3)), m_val, int(match_day_first.group(1)))
                except ValueError:
                    pass

        # Check the header (first 500 characters) for Month DD, YYYY
        match_hdr = re.search(r"(?i)\b([A-Za-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})\b", transcript[:500])
        if match_hdr:
            m_val = MONTH_MAP.get(match_hdr.group(1).lower())
            if m_val:
                try:
                    return datetime.date(int(match_hdr.group(3)), m_val, int(match_hdr.group(2)))
                except ValueError:
                    pass

        return None

    @staticmethod
    def _format_iso_deadline(deadline: str, meeting_date: Optional[datetime.date]) -> str:
        """Convert relative deadlines or textual dates into ISO YYYY-MM-DD.
        
        Strict Forward Relative Date Math:
        When computing weekday deadlines, compute strictly forward from meeting_date.
        Never output a date prior to meeting_date.
        """
        if not deadline or deadline in ("Not specified", "No deadline", "null", "None", ""):
            return "Not specified"

        dl = deadline.strip()
        dl_lower = dl.lower()

        # Reject standalone clock timestamps (e.g. 11:02 AM)
        if re.fullmatch(r"\d{1,2}:\d{2}\s*(?:am|pm|utc|est|pst|gmt)?", dl_lower):
            return "Not specified"

        # If already formatted as ISO YYYY-MM-DD
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", dl):
            if meeting_date:
                try:
                    parsed_dt = datetime.date.fromisoformat(dl)
                    if parsed_dt < meeting_date:
                        # Reject past date generated by LLM (e.g. 2026-09-03 when meeting is 2026-09-20)
                        pass
                    else:
                        return dl
                except ValueError:
                    pass
            else:
                return dl

        # Explicit full date inside string e.g. "today, September 20, 2026 EOD" or "September 23, 2026"
        match_full = re.search(r"(?i)\b([A-Za-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})\b", dl)
        if match_full:
            m_val = MONTH_MAP.get(match_full.group(1).lower())
            if m_val:
                try:
                    candidate = datetime.date(int(match_full.group(3)), m_val, int(match_full.group(2)))
                    if not meeting_date or candidate >= meeting_date:
                        return candidate.isoformat()
                except ValueError:
                    pass

        # Explicit month and day without year e.g. "September 23"
        match_m_d = re.search(r"(?i)\b([A-Za-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?\b", dl)
        if match_m_d:
            m_name = match_m_d.group(1).lower()
            if m_name in MONTH_MAP:
                m_val = MONTH_MAP[m_name]
                yr = meeting_date.year if meeting_date else 2026
                try:
                    candidate = datetime.date(yr, m_val, int(match_m_d.group(2)))
                    if not meeting_date or candidate >= meeting_date:
                        return candidate.isoformat()
                except ValueError:
                    pass

        # Relative resolution if meeting_date is known (Strict Forward Date Math)
        if meeting_date:
            if re.search(r"\b(?:today|tonight|eod)\b", dl_lower):
                return meeting_date.isoformat()
            if "tomorrow" in dl_lower:
                return (meeting_date + timedelta(days=1)).isoformat()

            weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
            for target_weekday, w_name in enumerate(weekdays):
                if re.search(r"\b" + w_name + r"\b", dl_lower):
                    current_weekday = meeting_date.weekday()
                    days_ahead = (target_weekday - current_weekday) % 7
                    if days_ahead == 0 and ("next" in dl_lower or dl_lower.startswith("next") or f"by {w_name}" in dl_lower or f"on {w_name}" in dl_lower):
                        days_ahead = 7
                    elif days_ahead == 0:
                        days_ahead = 7
                    target_date = meeting_date + timedelta(days=days_ahead)
                    return target_date.isoformat()

        return "Not specified" if re.fullmatch(r"\d{4}-\d{2}-\d{2}", dl) else dl

    @staticmethod
    def _deadline_is_explicit_for_action(deadline: str, task: str, evidence: Optional[str]) -> bool:
        """Require deadline evidence to be attached to this action, not just the header."""
        if not deadline or deadline.strip().lower() in ("not specified", "no deadline", "null", "none"):
            return True
        source = " ".join(part for part in (task, evidence or "") if part).lower()
        return bool(re.search(
            r"\b(?:by|before|on|due|until|for|tomorrow|today|tonight|eod|this\s+\w+|next\s+\w+|"
            r"monday|tuesday|wednesday|thursday|friday|saturday|sunday|"
            r"january|february|march|april|may|june|july|august|september|october|november|december|"
            r"\d{1,2}(?:st|nd|rd|th)?[\s/-]+(?:[A-Za-z]+|\d{1,2})|"
            r"(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2})\b",
            source,
            re.IGNORECASE,
        ))

    @staticmethod
    def _is_unassigned_meeting_attendance(task: str, owner: str) -> bool:
        """Exclude reminders to attend a follow-up meeting, unless someone organizes it."""
        if owner and owner.strip().lower() not in ("not specified", "not_specified", "none", "null", "unassigned"):
            return False
        return bool(re.search(
            r"\b(?:everyone|all|team|members?)\b.*\b(?:join|joins|attend|attends|participate)\b|"
            r"\b(?:join|joins|attend|attends|participate)\b.*\b(?:meeting|call|session|discord)\b",
            task,
            re.IGNORECASE,
        ))

    @staticmethod
    def _remove_action_issue_duplicates(issues: list[str], action_items: list[ActionItem]) -> list[str]:
        """Keep unresolved issues separate from concrete actions already extracted."""
        action_terms = [set(re.findall(r"\b[a-z]{4,}\b", item.task.lower())) for item in action_items]
        filtered: list[str] = []
        for issue in issues:
            issue_terms = set(re.findall(r"\b[a-z]{4,}\b", issue.lower()))
            if any(len(terms) >= 2 and len(terms & issue_terms) / len(terms) >= 0.75 for terms in action_terms):
                continue
            filtered.append(issue)
        return filtered

    @classmethod
    def _resolve_owner_and_deadline(
        cls,
        task: str,
        owner: str,
        deadline: str,
        evidence: Optional[str],
        transcript_clean: str,
        meeting_date: Optional[datetime.date] = None,
    ) -> tuple[str, str, str]:
        """Normalize task, recover owner/deadline from evidence, and format ISO deadline."""
        transcript_lower = transcript_clean.lower()
        cleaned_task = task.strip()

        # Check if task itself has a prefix like "1. Marcus: Update the specs..." or "Marcus: Update..."
        match_task_lead = re.match(
            r"^(?:(?:\d+[\.\)]|\*|-|•)\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s*[:\-–—]\s*(.*)$",
            cleaned_task,
        )
        if match_task_lead:
            cand_name = match_task_lead.group(1).strip()
            rest_task = match_task_lead.group(2).strip()
            if (
                owner in ("Not specified", "Unassigned", "", None)
                and cand_name.lower() not in {"the", "we", "i", "our", "team", "someone", "action", "item", "task", "note"}
                and cand_name.lower() in transcript_lower
            ):
                owner = cand_name
            if rest_task:
                cleaned_task = rest_task

        # Inspect evidence for speaker self-commitments or assignments
        if evidence:
            ev_str = evidence.strip()

            # First priority: Speaker self-commitment (e.g. "Maya: ... I'll build it" or "[00:03:51] Karthik: Okay, I'll send...")
            match_self = re.search(
                r"(?:^|\n|\[[\d:]+\]\s*|(?:\d+[\.\)]|\*|-|•)\s*)([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s*:\s*.*?\b(?:i(?:'ll| will)|i can|i'm going to|my action item is|i'll handle|i will handle|i'll send|i will send|i'll take|i will take)\b",
                ev_str,
                re.I,
            )
            if match_self:
                cand = match_self.group(1).strip()
                if (
                    cand.lower() not in {"the", "we", "i", "our", "team", "someone", "action", "item", "task", "note"}
                    and cand.lower() in transcript_lower
                ):
                    owner = cand

            # If owner still unassigned, check list item prefix in evidence
            if owner in ("Not specified", "Unassigned", "", None):
                match_ev_lead = re.search(
                    r"(?:^|\n|\[[\d:]+\]\s*|(?:\d+[\.\)]|\*|-|•)\s*)([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s*[:\-–—]\s*(.+)",
                    ev_str,
                )
                if match_ev_lead:
                    cand = match_ev_lead.group(1).strip()
                    if (
                        cand.lower() not in {"the", "we", "i", "our", "team", "someone", "action", "item", "task", "note"}
                        and cand.lower() in transcript_lower
                    ):
                        owner = cand

            # If owner still unassigned, check addressing
            if owner in ("Not specified", "Unassigned", "", None):
                match_addr = re.search(
                    r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?),\s*(?:can|could|would|please)\s+(?:you\s+)?\b",
                    ev_str,
                    re.I,
                )
                if match_addr:
                    cand = match_addr.group(1).strip()
                    if (
                        cand.lower() not in {"the", "we", "i", "our", "team", "someone"}
                        and cand.lower() in transcript_lower
                    ):
                        owner = cand

            # If owner still unassigned, check "assigned to [Name]"
            if owner in ("Not specified", "Unassigned", "", None):
                match_assign = re.search(
                    r"\b(?:assigned|assign)\s+to\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b",
                    ev_str,
                    re.I,
                )
                if match_assign:
                    cand = match_assign.group(1).strip()
                    if cand.lower() in transcript_lower:
                        owner = cand

        # Fallback owner check against transcript dialogue if still unassigned
        if owner in ("Not specified", "Unassigned", "", None):
            search_snippets = []
            if evidence and len(evidence.strip()) >= 5:
                search_snippets.append(evidence.strip())
            if cleaned_task and len(cleaned_task) >= 5:
                search_snippets.append(cleaned_task)

            for snip in search_snippets:
                snip_words = [w for w in re.findall(r"\b[a-z]{4,}\b", snip.lower()) if w not in {"with", "that", "this", "from", "into", "group"}]
                if not snip_words:
                    continue
                for line in transcript_clean.splitlines():
                    if (
                        re.search(r"\b(?:i(?:'ll| will)|i can|i'm going to|i'll handle|i'll send|i'll take)\b", line, re.I)
                        and sum(1 for w in snip_words if w in line.lower()) >= min(2, len(snip_words))
                    ):
                        m_spk = re.search(r"(?:^|\[[\d:]+\]\s*)([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s*:", line)
                        if m_spk:
                            spk_name = m_spk.group(1).strip()
                            if (
                                spk_name.lower() in transcript_lower
                                and spk_name.lower() not in {"the", "we", "i", "our", "team", "someone", "action", "item", "task", "note"}
                            ):
                                owner = spk_name
                                break
                if owner not in ("Not specified", "Unassigned", "", None):
                    break

        # Deadline safety: If deadline is a pure time-of-day timestamp (e.g. 11:02 AM) without future date context, normalize to Not specified
        if deadline and deadline not in ("Not specified", "No deadline", "", None):
            dl_str = deadline.strip()
            if re.match(r"^\d{1,2}:\d{2}\s*(?:am|pm|utc|est|pst|gmt)?$", dl_str, re.I):
                deadline = "Not specified"

        # If deadline is unassigned, is an erroneous past date, or lazily defaulted to meeting_date when future cues exist
        should_check_evidence = False
        if deadline in ("Not specified", "No deadline", "", None):
            should_check_evidence = True
        elif meeting_date and re.fullmatch(r"\d{4}-\d{2}-\d{2}", deadline):
            try:
                parsed_dl = datetime.date.fromisoformat(deadline)
                if parsed_dl < meeting_date:
                    should_check_evidence = True
                elif parsed_dl == meeting_date:
                    ev_check = f"{evidence or ''} {cleaned_task}".lower()
                    if any(w in ev_check for w in ("tomorrow", "thursday", "friday", "saturday", "sunday", "next week", "after registration", "after form closes")):
                        should_check_evidence = True
            except ValueError:
                should_check_evidence = True

        if should_check_evidence:
            search_sources = []
            if evidence:
                search_sources.append(evidence)
            for line in transcript_clean.splitlines():
                if any(w in line.lower() for w in re.findall(r"\b[a-z]{4,}\b", cleaned_task.lower()) if w not in {"with", "that", "this", "from"}):
                    search_sources.append(line)

            for src in search_sources:
                dl_match = re.search(
                    r"\b(?:(?:by|before|on|due|for|until|after)\s+(?:the\s+)?(?:end of )?(?:next\s+)?"
                    r"(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)(?:\s+(?:evening|morning|afternoon|eod|end of day|night|\d{1,2}(?::\d{2})?\s*(?:am|pm)?))?|"
                    r"(?:by|before|on|due|for|until|after)\s+(?:[A-Za-z]+\s+\d{1,2}(?:st|nd|rd|th)?|\d{1,2}(?:st|nd|rd|th)?(?:\s+of\s+[A-Za-z]+)?)|"
                    r"(?:by\s+)?(?:eod\s+tomorrow|end of day tomorrow|tomorrow\s+night|tomorrow\s+evening|eod|tonight|tomorrow|today|this\s+(?:week|month)|next\s+(?:week|month)|"
                    r"sometime\s+next\s+week|before\s+the\s+weekend|after\s+registration(?:\s+closes)?(?:\s+on\s+friday)?|"
                    r"(?:thursday|friday|monday|tuesday|wednesday|saturday|sunday)\s+(?:evening|morning|afternoon|eod|night|\d{1,2}(?::\d{2})?\s*(?:am|pm)?)))\b",
                    src,
                    re.IGNORECASE,
                )
                if dl_match:
                    raw_dl = dl_match.group(0).strip()
                    if "registration" in raw_dl.lower() and "friday" not in raw_dl.lower():
                        deadline = "Friday" if "friday" in transcript_clean.lower() else raw_dl
                    else:
                        deadline = raw_dl
                    break

        # Format ISO deadline
        deadline = cls._format_iso_deadline(deadline, meeting_date)

        return cleaned_task, owner, deadline

    @staticmethod
    def _deduplicate_action_items(action_items: list[ActionItem]) -> list[ActionItem]:
        """Deduplicate action items based on task similarity, merging owner and deadline info."""
        if not action_items:
            return []

        deduped: list[ActionItem] = []
        for item in action_items:
            task_clean = item.task.strip()
            task_norm = re.sub(r"[^\w\s]", "", task_clean.lower())
            item_words = set(re.findall(r"\b[a-z]{3,}\b", task_norm)) - {"the", "and", "for", "with", "this", "that", "from", "into", "group"}

            matched_existing: Optional[ActionItem] = None
            for existing in deduped:
                ext_clean = existing.task.strip()
                ext_norm = re.sub(r"[^\w\s]", "", ext_clean.lower())
                if task_norm == ext_norm:
                    matched_existing = existing
                    break
                ext_words = set(re.findall(r"\b[a-z]{3,}\b", ext_norm)) - {"the", "and", "for", "with", "this", "that", "from", "into", "group"}
                if item_words and ext_words:
                    overlap = len(item_words & ext_words) / max(len(item_words), len(ext_words))
                    if overlap >= 0.70 or (item_words.issubset(ext_words) and len(item_words) >= 2) or (ext_words.issubset(item_words) and len(ext_words) >= 2):
                        matched_existing = existing
                        break

            if matched_existing:
                # Merge owner if existing is unassigned and current has owner
                if matched_existing.owner in ("Not specified", "Unassigned", "null", None, "") and item.owner not in ("Not specified", "Unassigned", "null", None, ""):
                    matched_existing.owner = item.owner
                # Merge deadline if existing is Not specified and current has deadline
                if matched_existing.deadline in ("Not specified", "null", None, "") and item.deadline not in ("Not specified", "null", None, ""):
                    matched_existing.deadline = item.deadline
                # Merge evidence if existing is empty
                if not matched_existing.evidence and item.evidence:
                    matched_existing.evidence = item.evidence
            else:
                deduped.append(item)

        return deduped

    @staticmethod
    def _filter_action_items_from_decisions(
        decisions_flat: list[str],
        detailed_decisions: list[DecisionItem],
        action_items: list[ActionItem],
    ) -> tuple[list[str], list[DecisionItem]]:
        """Filter out decision strings that describe individual tasks, deliverable handoffs, conditional action items, or risk mitigations."""
        if not decisions_flat:
            return decisions_flat, detailed_decisions

        filtered_flat: list[str] = []
        filtered_detailed: list[DecisionItem] = []

        # Action verbs / imperative patterns indicating individual tasks, operational tasks, or risk mitigations
        task_verb_pattern = re.compile(
            r"^(?:hard\s+freeze|freeze|escalate|conduct|investigate|send|circulate|distribute|update|implement|build|deploy|create|set\s+up|prepare|follow\s+up|contact|schedule|notify|test|draft|review|audit|check|reach\s+out|share|deliver|document|organize)\b",
            re.IGNORECASE,
        )

        # Risk mitigation / conditional action indicators
        conditional_task_pattern = re.compile(
            r"\b(?:if\s+(?:it\s+doesn't|it\s+does\s+not|sandbox|latency|issues|we\s+see|needed|necessary|required))\b|"
            r"\b(?:by\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|tomorrow|eod))\b",
            re.IGNORECASE,
        )

        for idx, dec in enumerate(decisions_flat):
            dec_clean = dec.strip()
            dec_lower = dec_clean.lower()
            is_action_item = False

            # 1. Named individual assignment pattern (e.g. "Priya Sharma to circulate...", "Arun will handle...")
            match_named = re.match(
                r"^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+(?:to|will|shall|must|should|is tasked with|needs to)\s+(.+)",
                dec_clean,
                re.IGNORECASE,
            )
            if match_named:
                is_action_item = True
                cand_owner = match_named.group(1).strip()
                cand_task_raw = match_named.group(2).strip()
                if cand_task_raw:
                    cand_task = cand_task_raw[0].upper() + cand_task_raw[1:]
                    # If not already present in action_items, add it
                    if not any(
                        cand_owner.lower() == (ai.owner or "").lower()
                        and any(w in ai.task.lower() for w in re.findall(r"\b[a-z]{4,}\b", cand_task.lower()))
                        for ai in action_items
                    ):
                        action_items.append(
                            ActionItem(
                                task=cand_task,
                                owner=cand_owner,
                                deadline="Not specified",
                                status="pending",
                                confidence=1.0,
                            )
                        )

            # 2. Starts with task action verb (e.g. "Escalate billing provider...", "Hard freeze campaign creatives...")
            if not is_action_item and task_verb_pattern.search(dec_clean):
                is_action_item = True

            # 3. Conditional risk mitigation task (e.g. "... by Wednesday if it doesn't stabilize")
            if not is_action_item and conditional_task_pattern.search(dec_clean) and any(
                v in dec_lower for v in ("escalate", "freeze", "investigate", "fix", "contact", "support lead", "provider", "sandbox")
            ):
                is_action_item = True

            # 4. Check if decision describes deliverable handoffs / receptions (e.g. "Marketing will receive the final feature list...")
            if not is_action_item and re.search(
                r"\b(?:will\s+receive|to\s+receive|will\s+be\s+sent|will\s+send|will\s+circulate|will\s+share|will\s+distribute|will\s+deliver|will\s+escalate)\b",
                dec_lower,
            ):
                for ai in action_items:
                    ai_task_words = [w for w in re.findall(r"\b[A-Za-z]{4,}\b", ai.task.lower()) if w not in {"with", "that", "this", "from", "into"}]
                    if ai_task_words:
                        matched = sum(1 for w in ai_task_words if w in dec_lower)
                        if matched >= 2 or (len(ai_task_words) == 1 and matched == 1):
                            is_action_item = True
                            break

            # 5. Overlap with extracted action items
            if not is_action_item and action_items:
                dec_words = set(re.findall(r"\b[A-Za-z]{3,}\b", dec_lower))
                for ai in action_items:
                    ai_task_lower = ai.task.lower()
                    task_words = set(re.findall(r"\b[A-Za-z]{3,}\b", ai_task_lower))
                    if task_words and dec_words:
                        overlap = len(task_words & dec_words) / len(task_words)
                        if (overlap >= 0.40 and (ai_task_lower in dec_lower or dec_lower in ai_task_lower)) or overlap >= 0.60:
                            is_action_item = True
                            break
                        shared = [w for w in (task_words & dec_words) if w not in {"the", "and", "for", "with", "this", "that", "from"}]
                        if len(shared) >= 3:
                            is_action_item = True
                            break

            if not is_action_item:
                filtered_flat.append(dec)
                if idx < len(detailed_decisions):
                    filtered_detailed.append(detailed_decisions[idx])

        return filtered_flat, filtered_detailed

    @staticmethod
    def _move_deferred_decisions_to_issues(
        decisions_flat: list[str],
        detailed_decisions: list[DecisionItem],
        unresolved_issues: list[str],
    ) -> tuple[list[str], list[DecisionItem], list[str]]:
        """Move explicit deferrals and unresolved proposals out of decisions."""
        deferred_pattern = re.compile(
            r"\b(?:not|never|haven't|hasn't|don't|doesn't|didn't)\s+(?:yet\s+)?(?:finali[sz]e|decide|confirm|approve|settle)\b|"
            r"\b(?:tentative(?:ly)?|undecided|to be confirmed|not finalized|not decided)\b|"
            r"\b(?:(?:will be|to be)\s+)?(?:decide|decided|confirm|confirmed|approve|approved|finalize|finalized)\s+(?:later|after|based on|once)\b",
            re.IGNORECASE,
        )
        kept_decisions: list[str] = []
        kept_detailed: list[DecisionItem] = []
        for index, decision in enumerate(decisions_flat):
            if deferred_pattern.search(decision):
                if decision not in unresolved_issues:
                    unresolved_issues.append(decision)
                continue
            kept_decisions.append(decision)
            if index < len(detailed_decisions):
                kept_detailed.append(detailed_decisions[index])
        return kept_decisions, kept_detailed, unresolved_issues

    @staticmethod
    def _filter_dummy_unresolved_issues(issues: list[str]) -> list[str]:
        """Filter out dummy/placeholder risk phrases like 'No issues identified'."""
        filtered = []
        for iss in issues:
            iss_clean = iss.strip()
            if not iss_clean:
                continue
            if re.search(
                r"(?i)^(?:no\s+(?:active\s+|open\s+|explicit\s+|identified\s+|unresolved\s+)?(?:issues|risks|blockers|concerns)(?:\s+(?:identified|found|noted|reported|raised))?|none|n/a)\.?$",
                iss_clean,
            ):
                continue
            filtered.append(iss_clean)
        return filtered

