"""Gemini-backed meeting analysis with Pydantic response validation."""

import json
import logging
import os
import random
import re
import time
from pathlib import Path

from app.schemas.meeting_schema import MeetingAnalysis

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
            r"(?i)([?&](?:api[_-]?key|key|token|authorization)=)[^&\s]+",
            r"\1[REDACTED]",
            message,
        )
        redacted = re.sub(
            r"(?i)\b(api[_ -]?key|token|authorization|bearer)\b\s*([:=])\s*[^\s,;]+",
            r"\1\2[REDACTED]",
            redacted,
        )
        redacted = re.sub(r"\bAIza[A-Za-z0-9_-]{20,}\b", "[REDACTED]", redacted)
        return redacted[:500] or "No diagnostic message was provided."


class GeminiAnalyzer:
    """Analyze cleaned transcripts with Gemini and validate the JSON response."""

    _MODEL_NAME = "gemini-3.6-flash"

    # Backoff configuration
    _BASE_DELAY_S: float = 2.0       # base wait seconds for first retry
    _MAX_DELAY_S: float = 60.0       # cap each individual wait at 60 s
    _JITTER_RANGE: float = 1.5       # add ±jitter_range seconds of random noise
    _INTER_CALL_PACE_S: float = 1.0  # minimum gap between consecutive calls (pacing)

    def __init__(self) -> None:
        """Load the Gemini API key from the project's environment configuration."""
        try:
            from dotenv import load_dotenv

            project_root = Path(__file__).resolve().parents[2]
            load_dotenv(dotenv_path=project_root / ".env")
            self._api_key = os.getenv("GEMINI_API_KEY")
        except ImportError as error:
            raise GeminiAnalysisError("python-dotenv is not installed.", error) from error

    @property
    def is_configured(self) -> bool:
        """Return whether a non-empty Gemini API key was detected, without exposing it."""
        return bool(self._api_key)

    @property
    def model_name(self) -> str:
        """Return the configured model name for safe diagnostics."""
        return self._MODEL_NAME

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_json(self, prompt: str, max_retries: int = 6) -> dict | list:
        """Execute a JSON-configured prompt with exponential backoff + jitter for transient errors.

        Handles 429 / RESOURCE_EXHAUSTED responses by:
          1. Reading the ``Retry-After`` header when available.
          2. Falling back to exponential backoff with random jitter.
          3. Capping the maximum wait at ``_MAX_DELAY_S`` seconds.
          4. Enforcing a minimum ``_INTER_CALL_PACE_S`` gap between calls.
        """
        if not self._api_key:
            raise GeminiAnalysisError("Gemini API key is not configured.")

        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=self._api_key)
            config = types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.0,
            )

            last_err: Exception | None = None
            for attempt in range(1, max_retries + 1):
                try:
                    logger.debug(
                        "Gemini request attempt %d/%d (model=%s).",
                        attempt,
                        max_retries,
                        self._MODEL_NAME,
                    )
                    response = client.models.generate_content(
                        model=self._MODEL_NAME,
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

                    if is_transient and attempt < max_retries:
                        wait = self._compute_wait(attempt, error, is_rate_limit)
                        logger.warning(
                            "Gemini transient error (attempt %d/%d, rate_limit=%s): %s. "
                            "Retrying in %.1fs...",
                            attempt,
                            max_retries,
                            is_rate_limit,
                            GeminiAnalysisError.redact_message(msg[:200]),
                            wait,
                        )
                        time.sleep(wait)
                    else:
                        raise error

            raise last_err or GeminiAnalysisError("Max retries exceeded.")

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
        # Try to extract Retry-After from the error message (e.g. "retry_delay { seconds: 30 }")
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
        # Pattern: 'retry_delay { seconds: 30 }' or 'retry_delay { seconds 30 }'
        # Pattern: 'retryDelay: 60' (camelCase, no 'seconds' word)
        # Pattern: 'Retry-After: 45'
        # Pattern: '"retry_after": 30'
        # Pattern: 'wait 30 s'
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
        """Create a strict, schema-focused prompt without changing transcript text."""
        return f"""Analyze the following meeting transcript.

Return strict JSON only. Do not use Markdown, code fences, commentary, or fields
other than summary, action_items, decisions, and unresolved_issues.

Use this exact shape:
{{
  "summary": "concise meeting summary",
  "action_items": [
    {{
      "task": "specific task",
      "owner": "person name or null",
      "deadline": "deadline or null",
      "status": "pending",
      "confidence": 0.0
    }}
  ],
  "decisions": ["decision"],
  "unresolved_issues": ["unresolved issue"]
}}

Rules:
- Action items are commitments, requests, assignments, or required next steps
  expressed in natural language. Normalize each task to the actual action; do
  not copy filler, speaker labels, or unrelated discussion.
- Set owner only when a person is explicitly named or clearly self-assigned by
  an identified speaker. Otherwise use null. Set deadline only when the
  transcript explicitly gives one (for example "by Wednesday", "before Monday",
  "on Friday", "tomorrow", or "next week"); otherwise use null.
- Keep action-item status "pending" unless the transcript explicitly says that
  specific task is completed.
- Include decisions only where the group actually reached an outcome, including
  wording such as agreed to, decided to, approved, confirmed, finalized,
  settled on, chose, selected, will proceed with, let's go with, final choice
  is, committee accepted, or everyone agreed. Do not turn proposals, questions,
  or preferences into decisions.
- Include unresolved issues only when they remain open: still pending, not
  decided, undecided, unresolved, waiting for approval, needs further
  discussion, needs confirmation, not finalized, or open question. Do not list
  a matter as unresolved when the transcript establishes that it was resolved.
- The summary must cover the main discussion topic and prioritize material
  decisions, action items, and unresolved issues. Do not summarize only an
  action item when meaningful decisions or unresolved issues are present.
- Use a numeric confidence from 0.0 to 1.0 when possible; otherwise use null.
- Use empty arrays when no items exist.
- Preserve factual meaning; do not invent owners, deadlines, decisions, or issues.

Transcript:
{transcript}"""
