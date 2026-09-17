"""Decision Agent: Extracts explicitly confirmed club decisions and resolutions."""

import json
import logging
from typing import Optional

from app.schemas.meeting_schema import DecisionItem
from app.services.gemini_analyzer import GeminiAnalyzer, GeminiAnalysisError

logger = logging.getLogger(__name__)


class DecisionAgent:
    """Agent specializing in extracting explicit confirmed group decisions."""

    def __init__(self, gemini_analyzer: Optional[GeminiAnalyzer] = None) -> None:
        self.analyzer = gemini_analyzer or GeminiAnalyzer()

    def extract_decisions(self, transcript: str) -> tuple[list[str], list[DecisionItem], list[str]]:
        """Extract explicit confirmed decisions and unresolved issues from transcript.
        
        Args:
            transcript: Cleaned meeting transcript.
            
        Returns:
            Tuple of:
              - list[str]: flat list of decision strings (backward-compatible)
              - list[DecisionItem]: structured decision items with evidence & confidence
              - list[str]: list of unresolved/open issues identified
              
        Raises:
            GeminiAnalysisError: If Gemini fails.
        """
        if not transcript or not transcript.strip():
            raise ValueError("Transcript must contain non-whitespace text.")

        if not self.analyzer.is_configured:
            raise GeminiAnalysisError("Gemini API key is not configured.")

        prompt = self._build_prompt(transcript)
        parsed = self.analyzer.generate_json(prompt)
        if not isinstance(parsed, dict):
            raise GeminiAnalysisError("Expected JSON object with 'decisions' and 'unresolved_issues'.")

        raw_decisions = parsed.get("decisions", [])
        decisions_flat: list[str] = []
        detailed_decisions: list[DecisionItem] = []

        for d in raw_decisions:
            if isinstance(d, dict):
                dec_text = str(d.get("decision", "")).strip()
                conf = float(d.get("confidence", 1.0)) if d.get("confidence") is not None else 1.0
                evidence = str(d.get("evidence", "")).strip() or None
            elif isinstance(d, str):
                dec_text = d.strip()
                conf = 1.0
                evidence = None
            else:
                continue

            if dec_text:
                decisions_flat.append(dec_text)
                detailed_decisions.append(
                    DecisionItem(
                        decision=dec_text,
                        confidence=conf,
                        evidence=evidence,
                    )
                )

        raw_issues = parsed.get("unresolved_issues", [])
        unresolved_issues: list[str] = []
        for issue in raw_issues:
            if isinstance(issue, dict):
                iss_text = str(issue.get("issue", "")).strip()
            elif isinstance(issue, str):
                iss_text = issue.strip()
            else:
                continue

            if iss_text:
                unresolved_issues.append(iss_text)

        return decisions_flat, detailed_decisions, unresolved_issues

    @staticmethod
    def _build_prompt(transcript: str) -> str:
        return f"""You are an expert Decision Extraction Agent for student club meetings.
Your task is to identify explicit, settled decisions and distinguish them from unresolved issues or general discussion.

STRICT DECISION RULES:
1. Include ONLY outcomes that were explicitly agreed upon, approved, confirmed, finalized, or decided by the group (e.g., agreed budget amount, chosen event date/theme, selected speaker).
2. DO NOT treat mere suggestions, proposals, possibilities, open discussion, or preferences as decisions.
3. DO NOT include individual action items (like 'booking a venue' or 'contacting security') as decisions.
4. UNRESOLVED ISSUES: Matters that were left open, undecided, awaiting approval, or flagged for future discussion.
5. evidence: Provide a verbatim quote from the transcript confirming the decision.

Return STRICT JSON only:
{{
  "decisions": [
    {{
      "decision": "Explicit decision text",
      "confidence": 1.0,
      "evidence": "Quote from transcript where group agreed"
    }}
  ],
  "unresolved_issues": [
    "Open issue or pending question"
  ]
}}

Transcript:
{transcript}"""
