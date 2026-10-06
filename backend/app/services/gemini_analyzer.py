"""Gemini-backed meeting analysis with Pydantic response validation and key management."""

import datetime
from datetime import timedelta
import json
import logging
import os
import random
import re
import time
from pathlib import Path
from typing import Optional

from app.schemas.meeting_schema import MeetingAnalysis
from app.services.gemini_key_manager import GeminiKeyManager

logger = logging.getLogger(__name__)


class GeminiAnalysisError(Exception):
    """Raised when Gemini analysis cannot produce a valid meeting analysis."""

    def __init__(self, message: str, cause: Exception | None = None) -> None:
        """Retain only a redacted diagnostic summary of an underlying failure."""
        super().__init__(message)
        self.error_type = type(cause).__name__ if cause else type(self).__name__
        self.safe_message = self.redact_message(str(cause) if cause else message)
        self.is_rate_limit = bool(
            "429" in self.safe_message
            or "RESOURCE_EXHAUSTED" in self.safe_message
            or "quota" in self.safe_message.lower()
            or "rate" in self.safe_message.lower()
        )

    @staticmethod
    def redact_message(message: str) -> str:
        """Redact likely credentials and cap the safe diagnostic message length."""
        redacted = re.sub(
            r"(?i)([?&](?:api[_-]?key|key|token|authorization)=)[^&\s,;]+",
            r"\1[REDACTED]",
            message,
        )
        redacted = re.sub(
            r"(?i)\b(authorization|bearer)\s*[:=]?\s*(?:bearer\s+)?[^\s,;]+",
            r"\1: [REDACTED]",
            redacted,
        )
        redacted = re.sub(
            r"(?i)\b(api[_ -]?key|key|token|secret)\b\s*([:=])\s*[^\s,;]+",
            r"\1\2[REDACTED]",
            redacted,
        )
        redacted = re.sub(r"\bAIza[A-Za-z0-9_-]{10,}\b", "[REDACTED]", redacted)
        redacted = re.sub(r"\bAQ\.[A-Za-z0-9_-]{10,}\b", "[REDACTED]", redacted)
        return redacted[:500] or "No diagnostic message was provided."


class GeminiAnalyzer:
    """Analyze cleaned transcripts with Gemini and validate the JSON response."""

    _DEFAULT_MODEL = "gemini-3.5-flash-lite"

    # Backoff configuration
    _BASE_DELAY_S: float = 2.0       # base wait seconds for first retry
    _MAX_DELAY_S: float = 60.0       # cap each individual wait at 60 s
    _JITTER_RANGE: float = 1.5       # add ±jitter_range seconds of random noise
    _INTER_CALL_PACE_S: float = 1.0  # minimum gap between consecutive calls (pacing)

    def __init__(
        self,
        key_manager: Optional[GeminiKeyManager] = None,
        model_name: Optional[str] = None,
    ) -> None:
        """Initialize the analyzer with GeminiKeyManager and configurable model."""
        self._key_manager = key_manager or GeminiKeyManager()
        self._model_name = model_name or self._key_manager.model or self._DEFAULT_MODEL

    @property
    def is_configured(self) -> bool:
        """Return whether a usable Gemini API key was detected, without exposing it."""
        return self._key_manager.is_configured

    @property
    def model_name(self) -> str:
        """Return the configured model name for safe diagnostics."""
        return self._model_name

    @property
    def key_manager(self) -> GeminiKeyManager:
        """Return the associated key manager."""
        return self._key_manager

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_json(self, prompt: str, max_retries: int = 6) -> dict | list:
        """Execute a JSON-configured prompt with exponential backoff + jitter for transient errors
        and failover from primary to backup key on 429 quota exhaustion.

        Key failover rules:
          1. In auto mode, use primary key first.
          2. When primary key encounters 429 / RESOURCE_EXHAUSTED / quota limits, fail over
             to the backup key for the same request.
          3. Do not switch keys on successful requests (each new request starts with primary).
          4. Transient 503 / UNAVAILABLE errors trigger backoff + retry on the active key.
        """
        if not self.is_configured:
            raise GeminiAnalysisError("Gemini API key is not configured.")

        key_candidates = self._key_manager.get_key_candidates()
        if not key_candidates:
            raise GeminiAnalysisError("No valid Gemini API key available for the current mode.")

        try:
            from google import genai
            from google.genai import types

            config = types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.0,
            )

            last_err: Exception | None = None

            for key_idx, (key_label, api_key) in enumerate(key_candidates):
                has_subsequent_key = (key_idx + 1) < len(key_candidates)
                client = genai.Client(api_key=api_key)

                for attempt in range(1, max_retries + 1):
                    try:
                        logger.debug(
                            "Gemini request attempt %d/%d (model=%s, key=%s).",
                            attempt,
                            max_retries,
                            self._model_name,
                            key_label,
                        )
                        response = client.models.generate_content(
                            model=self._model_name,
                            contents=prompt,
                            config=config,
                        )
                        if response and response.text:
                            raw = response.text.strip()
                            if raw.startswith("```"):
                                raw = raw.split("\n", 1)[1]
                                if raw.endswith("```"):
                                    raw = raw.rsplit("```", 1)[0]
                                raw = raw.strip()
                            result = json.loads(raw)
                            # Successful — pace the next call
                            time.sleep(self._INTER_CALL_PACE_S)
                            return result
                        raise GeminiAnalysisError("Gemini returned an empty response.")

                    except Exception as error:
                        last_err = error
                        msg = str(error)
                        is_rate_limit = any(
                            t in msg for t in ("429", "RESOURCE_EXHAUSTED", "quota", "rate limit")
                        )
                        is_transient = is_rate_limit or any(
                            t in msg for t in ("503", "UNAVAILABLE", "timeout", "connection")
                        )

                        # Primary key hit 429 quota exhaustion -> failover to backup key
                        if is_rate_limit and has_subsequent_key:
                            next_key_label = key_candidates[key_idx + 1][0]
                            logger.warning(
                                "Gemini key '%s' encountered quota limit (429 / RESOURCE_EXHAUSTED). "
                                "Failing over to '%s' key for current request...",
                                key_label,
                                next_key_label,
                            )
                            break

                        if is_transient and attempt < max_retries:
                            wait = self._compute_wait(attempt, error, is_rate_limit)
                            logger.warning(
                                "Gemini transient error on '%s' key (attempt %d/%d, rate_limit=%s): %s. "
                                "Retrying in %.1fs...",
                                key_label,
                                attempt,
                                max_retries,
                                is_rate_limit,
                                GeminiAnalysisError.redact_message(msg[:200]),
                                wait,
                            )
                            time.sleep(wait)
                        else:
                            if not has_subsequent_key:
                                raise error
                            else:
                                raise error

            raise last_err or GeminiAnalysisError("Max retries exceeded or all keys exhausted.")

        except GeminiAnalysisError:
            raise
        except (ImportError, json.JSONDecodeError, ValueError, TypeError) as error:
            raise GeminiAnalysisError("Gemini response could not be parsed.", error) from error
        except Exception as error:
            raise GeminiAnalysisError("Gemini analysis request failed.", error) from error

    def analyze(self, transcript: str) -> MeetingAnalysis:
        """Return Gemini analysis validated against the existing response schema.

        Raises:
            GeminiAnalysisError: If configuration, the Gemini request, JSON parsing,
                or schema validation fails.
        """
        if not isinstance(transcript, str) or not transcript.strip():
            raise GeminiAnalysisError("A non-empty transcript is required for analysis.")
        prompt = self._build_prompt(transcript)
        response_data = self.generate_json(prompt)
        try:
            return MeetingAnalysis.model_validate(response_data)
        except Exception as error:
            raise GeminiAnalysisError("Gemini analysis could not be validated.", error) from error

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _compute_wait(self, attempt: int, error: Exception, is_rate_limit: bool) -> float:
        """Compute how long to wait before the next retry.

        Uses ``Retry-After`` when the error object carries that information,
        otherwise uses exponential backoff with ±jitter.
        """
        retry_after = self._extract_retry_after(str(error))
        if retry_after is not None:
            jitter = random.uniform(0, self._JITTER_RANGE)
            wait = min(retry_after + jitter, self._MAX_DELAY_S)
            logger.info("Respecting Retry-After: %.1fs (jitter +%.1fs).", retry_after, jitter)
            return wait

        # Exponential backoff: base * 2^(attempt-1) ± jitter
        exp_wait = self._BASE_DELAY_S * (2 ** (attempt - 1))
        jitter = random.uniform(-self._JITTER_RANGE, self._JITTER_RANGE)
        wait = min(max(exp_wait + jitter, self._BASE_DELAY_S), self._MAX_DELAY_S)
        return wait

    @staticmethod
    def _extract_retry_after(error_msg: str) -> float | None:
        """Parse Retry-After seconds from a Gemini error message string."""
        patterns = [
            r"retry[_-]?delay\s*\{?\s*seconds[:\s]+(\d+)",  # proto: retry_delay { seconds: 30 }
            r"retry[_-]?delay[:\s]+(\d+)",                  # retryDelay: 60
            r"retry.after[:\s]+(\d+)",                      # Retry-After: 45
            r"\"retry_after\"\s*:\s*(\d+)",                 # JSON key
            r"wait\s+(\d+)\s*s",                            # wait 30 s
        ]
        for pattern in patterns:
            match = re.search(pattern, error_msg, re.IGNORECASE)
            if match:
                return float(match.group(1))
        return None

    @classmethod
    def _extract_meeting_date(cls, transcript: str) -> Optional[datetime.date]:
        """Extract calendar date from meeting headers for prompt date anchoring."""
        month_map = {
            "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3,
            "april": 4, "apr": 4, "may": 5, "june": 6, "jun": 6, "july": 7, "jul": 7,
            "august": 8, "aug": 8, "september": 9, "sep": 9, "sept": 9,
            "october": 10, "oct": 10, "november": 11, "nov": 11, "december": 12, "dec": 12,
        }
        match_iso = re.search(r"(?i)\b(?:date|meeting\s+date)\s*[:|-]?\s*(\d{4})-(\d{1,2})-(\d{1,2})\b", transcript)
        if match_iso:
            try:
                return datetime.date(int(match_iso.group(1)), int(match_iso.group(2)), int(match_iso.group(3)))
            except ValueError:
                pass
        match_text = re.search(
            r"(?i)\b(?:date|meeting\s+date)\s*[:|-]?\s*([A-Za-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})\b",
            transcript,
        )
        if match_text:
            m_val = month_map.get(match_text.group(1).lower())
            if m_val:
                try:
                    return datetime.date(int(match_text.group(3)), m_val, int(match_text.group(2)))
                except ValueError:
                    pass
        match_day_first = re.search(
            r"(?i)\b(?:date|meeting\s+date)\s*[:|-]?\s*(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]+),?\s+(\d{4})\b",
            transcript,
        )
        if match_day_first:
            m_val = month_map.get(match_day_first.group(2).lower())
            if m_val:
                try:
                    return datetime.date(int(match_day_first.group(3)), m_val, int(match_day_first.group(1)))
                except ValueError:
                    pass
        match_hdr = re.search(r"(?i)\b([A-Za-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})\b", transcript[:500])
        if match_hdr:
            m_val = month_map.get(match_hdr.group(1).lower())
            if m_val:
                try:
                    return datetime.date(int(match_hdr.group(3)), m_val, int(match_hdr.group(2)))
                except ValueError:
                    pass
        return None

    @classmethod
    def _generate_calendar_context(cls, transcript: str) -> str:
        """Construct explicit calendar reference table for relative time math."""
        meeting_date = cls._extract_meeting_date(transcript)
        if not meeting_date:
            return ""
        
        weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        meeting_weekday = weekdays[meeting_date.weekday()]
        
        lines = [
            f"ANCHOR_DATE = {meeting_date.isoformat()} ({meeting_weekday})",
            "CALENDAR REFERENCE FOR RELATIVE TIME RESOLUTION:",
            f"- Today / Tonight / EOD = {meeting_weekday} ({meeting_date.isoformat()})",
            f"- Tomorrow / Tomorrow night = {weekdays[(meeting_date.weekday() + 1) % 7]} ({(meeting_date + timedelta(days=1)).isoformat()})",
        ]
        for offset in range(1, 8):
            target_dt = meeting_date + timedelta(days=offset)
            target_day_name = weekdays[target_dt.weekday()]
            lines.append(f"- {target_day_name} = {target_dt.isoformat()}")
        
        lines.append(f"- Next Monday = {(meeting_date + timedelta(days=((0 - meeting_date.weekday()) % 7 or 7))).isoformat()}")
        lines.append(f"- Next Friday = {(meeting_date + timedelta(days=((4 - meeting_date.weekday()) % 7 or 7))).isoformat()}")
        return "\n".join(lines)

    @classmethod
    def _build_prompt(cls, transcript: str) -> str:
        """Create a strict, comprehensive single-call prompt without changing transcript text."""
        cal_anchor = cls._generate_calendar_context(transcript)
        cal_block = f"\nCALENDAR ANCHOR & RELATIVE DATE REFERENCE:\n{cal_anchor}\n" if cal_anchor else ""
        return f"""You are an expert AI meeting analyst for organizational, business, and technical meetings.
Analyze the following meeting transcript and produce a complete, factual analysis in a single response.
{cal_block}
Return STRICT JSON only. Do not use Markdown, code fences, commentary, or fields
other than summary, action_items, decisions, and unresolved_issues.

Use this exact JSON shape:
{{
  "summary": "concise 3-5 sentence meeting summary covering purpose, key decisions, planned tasks, and open items",
  "action_items": [
    {{
      "task": "Clean normalized task description without deadline words",
      "owner": "Person Name or Not specified",
      "deadline": "YYYY-MM-DD or Not specified",
      "status": "pending",
      "confidence": 1.0,
      "evidence": "Short verbatim quote or dialogue snippet from transcript"
    }}
  ],
  "decisions": [
    "Explicit confirmed decision or agreed policy"
  ],
  "unresolved_issues": [
    "Monitored risk, blocker, pending external sign-off, or deferred question"
  ]
}}

STRICT RULES & GROUNDING:
1. SUMMARY:
   - Provide a factual, concise 3-5 sentence meeting summary synthesizing the concluded state and final consensus.
   - Cover primary meeting purpose, major discussion topics, confirmed decisions, upcoming action commitments, and open issues/risks.
   - Action items must be described with planned/future phrasing (e.g. "Key upcoming tasks include...", "is tasked with", "will coordinate"), NOT as already completed past actions.
   - Ground all approvals and statements strictly to the actual speakers. NEVER state that an external or absent team approved something when the speaker merely mentioned needing or seeking their sign-off.
   - Never describe an initial proposal as an agreed outcome if the transcript records subsequent pushback, debate, or postponement.
   - ACCURATE ATTRIBUTION & SENDER/RECIPIENT DISTINCTION: When summarizing commitments, accurately state who will perform the task versus who receives the output (e.g., if Person A commits to circulate materials to Team B, state that Person A will circulate them to Team B, NEVER that Team B was tasked with providing or preparing the materials).

2. ACTION ITEMS, DEDUPLICATION, ATOMIZATION & OWNER BINDING:
   - Extract all explicit engineering/operational tasks, commitments, deliverables (e.g., prototype delivery, registration), assignments, or agreed prerequisite steps.
   - DEDUPLICATION GUARDRAIL:
     * Deduplicate all action items before finalizing JSON output.
     * Never output identical or semantically duplicate tasks (e.g., do not output the same link sharing or setup task multiple times).
   - MULTI-SPEAKER TASK ATOMIZATION:
     * If a task or workstream is shared between multiple people (e.g., "Rohith does intro, Arun does tech demo" or "Marcus and Sarah will review PRs"), ALWAYS split into separate atomic action items:
       1. [Rohith] Handle introduction
       2. [Arun] Handle technical demo
   - EXPLICIT SPEAKER ATTRIBUTION & FIRST-PERSON OWNERSHIP CONSTRAINT:
     * When a participant speaks in first-person (e.g., "I'll send the meeting link", "I can take that", "I'll handle this", "I will do X", "My action item is X"), map the speaker name from the dialogue line or timestamp (e.g., [00:03:51] Karthik: or Karthik:) directly as the owner.
     * NEVER output "Unassigned" or "Not specified" if a speaker voluntarily takes ownership or commits in dialogue.
     * When tasks are listed with names (e.g. "1. Marcus: Update specs..."), extract that named person as the owner.
     * NEVER assign tasks to the meeting host, facilitator, or Incident Commander simply because they summarized or requested the task at the end.
     * If unassigned, use "Not specified" or null. NEVER invent an owner.
   - IN-MEETING COMPLETIONS (TEMPORAL AWARENESS): If a participant states they have ALREADY completed a task during the call (e.g., "I just tried it", "I'm pushing the hotfix right now", "Done", "I've pushed the commit"), DO NOT mark it as a pending action item. Either mark its status as "completed" or exclude it. Ensure pending action items capture actual future/post-meeting deliverables.
   - A date in the meeting header is never an implicit deadline. Only assign a deadline when the same action's dialogue explicitly says by/before/on/due/tomorrow/today, names a date, or uses an equivalent temporal cue.
   - NO META-TASKS / NO MEETING OBJECTIVES:
     * DO NOT log meta-goals, meeting agendas, or conversation topics (e.g., "Discuss budget", "Plan event", "Finalize workshop", "Log action items", "Note down meeting minutes") as Action Items.
     * Action Items MUST be atomic deliverables assigned to a person with a clear output (e.g., "Write PDF", "Send link", "Deploy hotfix").
   - task: ONLY the core task action. Normalize the task to the actual action. NEVER include deadline/timeframe words (e.g., "by Friday", "before the weekend", "next week", "by Sept 23", "post-launch", "by EOD today", "today") inside the task field.

3. DATE FORMATTING, RELATIVE DATE MATH & DEPENDENCIES:
   - ALL action item deadlines MUST be formatted strictly as ISO standard dates: YYYY-MM-DD (e.g., "2026-09-20", "2026-09-22", "2026-09-23", "2026-09-24", "2026-09-25", "2026-10-05").
   - FORWARD RELATIVE DATE MATH RULE:
     * When calculating relative weekdays ("by Thursday evening", "by Wednesday", "by Tuesday", "this Friday at 5 PM", "tomorrow", "by EOD"), ALWAYS compute strictly forward from the Meeting Header Date.
     * NEVER output a deadline date that occurs BEFORE the meeting header date (e.g., NEVER output 2026-09-03 or 2026-09-14 for a meeting held on September 20, 2026).
   - DEPENDENT TASK CHAIN CONSTRAINT:
     * If Task B explicitly depends on the completion of Task A (e.g., "after registration closes on Friday", "once backend API is deployed"):
       Enforce: Deadline(Task B) >= Deadline(Task A).
   - NO INCIDENT / TIMELINE TIMESTAMPS AS DEADLINES: Incident event timestamps, alert firing times (e.g., "11:02 AM", "14:30 UTC"), log timestamps, and dialogue timestamps indicate when past events occurred, NOT task deadlines. NEVER treat past incident times as deadlines. If no explicit future calendar date exists, deadline MUST be "Not specified".
   - status: Use "pending" unless the transcript explicitly states that specific task is completed.
   - confidence: Numeric confidence from 0.0 to 1.0 (default 1.0).
   - evidence: A short verbatim quote or dialogue snippet from the transcript demonstrating this action item.

4. KEY DECISIONS (STRICT TAXONOMY, CONSENSUS VERIFICATION & ZERO TASK CONFLATION):
   - A DECISION is strictly reserved for organizational agreements, policy choices, Tech Stack selections (e.g., Streamlit, FAISS, sentence-transformers), Architectural design, Project Naming (e.g., "StudyGen"), Scope cutoffs, or presentation role division strategy.
   - CONSENSUS VERIFICATION:
     * A statement is ONLY a Key Decision if it contains explicit team consensus ("Approved", "Let's make [X] official", "Agreed", "We keep...", "We decided", "completely fine for v1", "good to go", "locked in").
     * REJECT CONTESTED & SPECULATIVE PROPOSALS: Reject tentative phrases ("What if", "Tentative", "Need to check with X first", "Maybe"). If a proposal requires future external approval or was postponed, do NOT list it as a confirmed decision; move it to Unresolved Issues / Risks.
   - ZERO TASK OVERLAP & NO INDIVIDUAL TASK ASSIGNMENTS:
     * Do NOT put individual task assignments ("Person X will handle backend/UI/documentation", "Person X to circulate...") under Key Decisions. Put them ONLY under Action Items with that person as the owner.
     * Decisions must be phrased as collective choices, technical decisions, or agreed policies (e.g., "Use FAISS for vector search and Streamlit for UI", "Adopt 'StudyGen' as working project name").

5. OPEN ISSUES & RISKS (EXPLICIT RISK & BLOCKER CAPTURE):
   - Open Issues & Risks MUST be active blockers, explicit capacity limits, missing dependencies, or unconfirmed approvals that threaten the timeline (e.g., tight deadline for vector pipeline, "Wi-Fi unstable", "Need faculty approval", "No budget confirmed").
   - ROUTINE MONITORING VS. RISK: General statements like "Let's monitor the logs", "Keep an eye on metrics", or routine operational checks are ongoing operational follow-ups, NOT Open Issues or Risks. Only log explicit blockers, unresolved bugs, or threats to timelines as Open Issues/Risks.
   - ZERO DATA CONTAMINATION & ZERO-RISK HANDLING: If no active blockers or open risks exist in the transcript, return "unresolved_issues": [] (an empty array). NEVER generate a dummy risk item containing text like "No issues identified" or "No issues found". NEVER copy example text or invent risks/issues from other meetings.
   - Do not repeat an action item as an unresolved issue. An issue is the unresolved blocker, risk, pending approval, or unanswered question behind the action, not the action itself.

6. GROUNDING & SELF-CHECK:
   - Preserve factual meaning; NEVER invent or assume owners, deadlines, decisions, evidence, or issues not present in the transcript.
   - In-meeting completed tasks are not marked as pending action items; pending action items are real upcoming deliverables.
   - Routine monitoring is not extracted as an unresolved issue or risk.
   - Use empty arrays [] when no items exist for a category.

Transcript:
{transcript}"""
