"""Summary Agent: Extracts concise, factual 3-5 sentence meeting summaries."""

import json
import logging
from typing import Optional

from app.services.gemini_analyzer import GeminiAnalyzer, GeminiAnalysisError

logger = logging.getLogger(__name__)


class SummaryAgent:
    """Agent specializing in generating grounded 3-5 sentence meeting summaries."""

    def __init__(self, gemini_analyzer: Optional[GeminiAnalyzer] = None) -> None:
        self.analyzer = gemini_analyzer or GeminiAnalyzer()

    def generate_summary(self, transcript: str) -> str:
        """Generate a concise meeting summary grounded in the transcript text.
        
        Args:
            transcript: Cleaned meeting transcript text.
            
        Returns:
            Concise 3-5 sentence summary string.
            
        Raises:
            GeminiAnalysisError: If Gemini API fails or returns invalid response.
        """
        if not transcript or not transcript.strip():
            raise ValueError("Transcript must contain non-whitespace text.")

        if not self.analyzer.is_configured:
            raise GeminiAnalysisError("Gemini API key is not configured.")

        prompt = self._build_prompt(transcript)
        parsed = self.analyzer.generate_json(prompt)
        if isinstance(parsed, dict) and "summary" in parsed:
            summary = str(parsed["summary"]).strip()
        elif isinstance(parsed, str):
            summary = parsed.strip()
        else:
            summary = str(parsed).strip()

        if not summary:
            raise GeminiAnalysisError("Summary extracted from response was empty.")

        return summary

    @staticmethod
    def _build_prompt(transcript: str) -> str:
        return f"""You are an expert Meeting Summary Agent for student club meetings.
Your task is to produce a factual, concise 3–5 sentence meeting summary.

STRICT RULES:
1. Cover the primary meeting purpose, major discussion topics, confirmed decisions, key upcoming action commitments, and any open issues.
2. Action items must be described with planned/future phrasing (e.g. "Key upcoming tasks include...", "is tasked with", "will coordinate"), NOT as already completed past actions.
3. Keep it strictly grounded in the transcript. Do NOT invent people, facts, dates, or outcomes.
4. Length must be concise (3 to 5 sentences).

Return STRICT JSON only:
{{
  "summary": "3-5 sentence meeting summary"
}}

Transcript:
{transcript}"""
