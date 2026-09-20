"""Gemini-backed meeting analysis with Pydantic response validation and key management."""

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

    @staticmethod
    def _build_prompt(transcript: str) -> str:
        """Create a strict, comprehensive single-call prompt without changing transcript text."""
        return f"""You are an expert AI meeting analyst for organizational, business, and technical meetings.
Analyze the following meeting transcript and produce a complete, factual analysis in a single response.

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


2. ACTION ITEMS & OWNER BINDING:
   - Extract all explicit engineering/operational tasks, commitments, deliverables, assignments, or agreed prerequisite steps.
   - OWNER BINDING & SELF-COMMITMENT PRECEDENCE:
     * Assign tasks to the person who explicitly self-commits ("I will do X", "I'll handle this", "My action item is X", "I can take that") or is directly requested ("Priya, can you circulate...").
     * When tasks are listed with names (e.g. "1. Marcus: Update specs..."), extract that named person as the owner.
     * NEVER assign tasks to the meeting host, facilitator, or Incident Commander simply because they summarized or requested the task at the end.
     * If unassigned, use "Not specified" or null. NEVER invent an owner.
   - NO META-TASKS: Do NOT extract meta-instructions or meeting administrative commands (e.g., "log the action items", "assign tasks to log", "note down the meeting minutes", "record these items in Jira") as action items.
   - task: ONLY the core task action. Normalize the task to the actual action. NEVER include deadline/timeframe words (e.g., "by Friday", "before the weekend", "next week", "by Sept 23", "post-launch", "by EOD today", "today") inside the task field.

3. DATE FORMATTING & FORWARD DATE COMPUTATION:
   - ALL action item deadlines MUST be formatted strictly as ISO standard dates: YYYY-MM-DD (e.g., "2026-09-20", "2026-09-22", "2026-09-23", "2026-10-05").
   - FORWARD RELATIVE DATE MATH RULE:
     * When calculating relative weekdays ("by Wednesday", "by Tuesday", "this Friday", "tomorrow", "by EOD"), ALWAYS compute strictly forward from the Meeting Header Date.
     * For example, if the meeting took place on Sunday, September 20, 2026:
       - "today" or "today EOD" -> "2026-09-20"
       - "tomorrow" -> "2026-09-21"
       - "by Tuesday" -> "2026-09-22" (September 20 + 2 days = September 22)
       - "by Wednesday" -> "2026-09-23" (September 20 + 3 days = September 23)
       - "this Friday" -> "2026-09-25" (September 20 + 5 days = September 25)
     * NEVER output a deadline date that occurs BEFORE the meeting header date (e.g., NEVER output 2026-09-03 or 2026-09-14 for a meeting held on September 20, 2026).
   - NO INCIDENT / TIMELINE TIMESTAMPS AS DEADLINES: Incident event timestamps, alert firing times (e.g., "11:02 AM", "14:30 UTC"), log timestamps, and dialogue timestamps indicate when past events occurred, NOT task deadlines. NEVER treat past incident times as deadlines. If no explicit future calendar date exists, deadline MUST be "Not specified".
   - status: Use "pending" unless the transcript explicitly states that specific task is completed.
   - confidence: Numeric confidence from 0.0 to 1.0 (default 1.0).
   - evidence: A short verbatim quote or dialogue snippet from the transcript demonstrating this action item.

4. KEY DECISIONS (STRICT TAXONOMY & DECISION DISCRIMINATOR):
   - A DECISION is an organizational agreement, policy, schedule target, vendor choice, scope cutoff, or architectural design choice confirmed by the group (e.g., "Launch pricing experiment on September 29, 2026 (pending bugs/QA)", "Keep current paywall layout for the experiment", "Monitor conversion daily and decide on changes after seven days of data").
   - DECISION DISCRIMINATOR & ZERO TASK/RISK OVERLAP:
     * Ask: "Is this a structural policy/agreement, or is it an action item, conditional task, or risk mitigation?"
     * NEVER classify individual tasks, operational actions, conditional action items, or risk mitigations as Key Decisions:
       - "Escalate billing provider's sandbox stability issue..." is an Action Item (#5), NOT a Key Decision.
       - "Hard freeze campaign creatives today..." is an operational risk mitigation strategy, NOT an independent Key Decision.
     * If a person or team is assigned to execute or deliver it (e.g., "Priya Sharma will circulate...", "Dev will escalate..."), it belongs ONLY under Action Items.
     * NEVER list an Action Item, conditional task, or deliverable handoff inside Key Decisions.
   - Look for decision and consensus markers: "Let's make [X] official", "Approved", "Agreed", "We keep...", "We decided", "completely fine for v1", "good to go", "locked in".
   - REJECT CONTESTED PROPOSALS: If a proposal was contested, modified, or postponed, do NOT list it as a confirmed decision.

5. OPEN ISSUES & RISKS (ZERO-RISK HANDLING):
   - Include active technical and operational risks, unresolved blockers, or pending external sign-offs explicitly discussed in this transcript.
   - ZERO DATA CONTAMINATION & ZERO-RISK HANDLING: If no active blockers or open risks exist in the transcript, return "unresolved_issues": [] (an empty array). NEVER generate a dummy risk item containing text like "No issues identified" or "No issues found". NEVER copy example text or invent risks/issues from other meetings.
   - Provide clear, descriptive phrasing with context grounded in the transcript.

6. GROUNDING & SELF-CHECK:
   - Preserve factual meaning; NEVER invent or assume owners, deadlines, decisions, evidence, or issues not present in the transcript.
   - Use empty arrays [] when no items exist for a category.

Transcript:
{transcript}"""


