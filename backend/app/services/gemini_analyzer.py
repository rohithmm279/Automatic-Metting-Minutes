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
        return f"""You are an expert AI meeting analyst for student club and organizational meetings.
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
      "deadline": "Explicit deadline string or Not specified",
      "status": "pending",
      "confidence": 1.0,
      "evidence": "Short verbatim quote or dialogue snippet from transcript"
    }}
  ],
  "decisions": [
    "Explicit confirmed decision"
  ],
  "unresolved_issues": [
    "Open issue or pending question"
  ]
}}

STRICT RULES & GROUNDING:
1. SUMMARY:
   - Provide a factual, concise 3-5 sentence meeting summary.
   - Cover primary meeting purpose, major discussion topics, confirmed decisions, upcoming action commitments, and open issues.
   - Action items must be described with planned/future phrasing (e.g. "Key upcoming tasks include...", "is tasked with", "will coordinate"), NOT as already completed past actions.

2. ACTION ITEMS:
   - Extract only explicit tasks, commitments, requests, or assignments.
   - task: ONLY the core task action. Normalize the task to the actual action. NEVER include deadline/timeframe words (e.g., "by Friday", "before the weekend", "next week") inside the task field.
   - owner: Set ONLY when a person is explicitly named or clearly self-assigned by an identified speaker. If not explicitly identifiable, use "Not specified" or null. NEVER invent an owner.
   - deadline: Set ONLY when the transcript explicitly gives one (for example "by Wednesday", "before Monday", "on Friday", "tomorrow", "next week"). If not explicitly mentioned, use "Not specified" or null. NEVER invent a deadline.
   - status: Use "pending" unless the transcript explicitly states that specific task is completed.
   - confidence: Numeric confidence from 0.0 to 1.0 (default 1.0).
   - evidence: A short verbatim quote or dialogue snippet from the transcript demonstrating this action item.
   - FORBIDDEN: Do NOT include group decisions (such as agreeing on an event date or budget) as action items.

3. DECISIONS:
   - Include ONLY outcomes that were explicitly agreed upon, approved, confirmed, finalized, settled on, or decided by the group (e.g. agreed budget amount, chosen event date/theme, selected speaker).
   - DO NOT treat mere suggestions, proposals, possibilities, open discussion, or preferences as decisions.
   - DO NOT include individual action items as decisions.

4. UNRESOLVED ISSUES:
   - Include ONLY matters that remain open: still pending, not decided, undecided, unresolved, waiting for approval, needs further discussion, needs confirmation, not finalized, or open question.
   - DO NOT list a matter as unresolved when the transcript establishes that it was resolved.

5. GROUNDING:
   - Preserve factual meaning; NEVER invent or assume owners, deadlines, decisions, evidence, or issues not present in the transcript.
   - Use empty arrays [] when no items exist for a category.

Transcript:
{transcript}"""

