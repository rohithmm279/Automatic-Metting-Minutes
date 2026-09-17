"""Action Agent: Extracts structured action items with explicit owner, deadline, and evidence."""

import json
import logging
from typing import Optional

from app.schemas.meeting_schema import ActionItem
from app.services.gemini_analyzer import GeminiAnalyzer, GeminiAnalysisError

logger = logging.getLogger(__name__)


class ActionAgent:
    """Agent specializing in identifying assigned tasks, explicit owners, and explicit deadlines."""

    def __init__(self, gemini_analyzer: Optional[GeminiAnalyzer] = None) -> None:
        self.analyzer = gemini_analyzer or GeminiAnalyzer()

    def extract_action_items(self, transcript: str) -> list[ActionItem]:
        """Extract action items from transcript.
        
        Args:
            transcript: Cleaned meeting transcript.
            
        Returns:
            List of ActionItem instances.
            
        Raises:
            GeminiAnalysisError: If Gemini fails.
        """
        if not transcript or not transcript.strip():
            raise ValueError("Transcript must contain non-whitespace text.")

        if not self.analyzer.is_configured:
            raise GeminiAnalysisError("Gemini API key is not configured.")

        prompt = self._build_prompt(transcript)
        parsed = self.analyzer.generate_json(prompt)
        raw_actions = parsed.get("action_items", []) if isinstance(parsed, dict) else parsed

        if not isinstance(raw_actions, list):
            raise GeminiAnalysisError("Expected list of action items.")

        action_items: list[ActionItem] = []
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
            confidence = float(item.get("confidence", 1.0)) if item.get("confidence") is not None else 1.0
            evidence = str(item.get("evidence", "")).strip() or None

            action_items.append(
                ActionItem(
                    task=task,
                    owner=owner,
                    deadline=deadline,
                    status=status,
                    confidence=confidence,
                    evidence=evidence,
                )
            )

        return action_items

    @staticmethod
    def _build_prompt(transcript: str) -> str:
        return f"""You are an expert Action Item Extraction Agent for student club meetings.
Your job is to identify only explicit tasks, commitments, or assignments from the transcript.

STRICT EXTRACTION RULES:
1. Extract only tasks that are actually assigned, requested, or explicitly committed to.
2. task: ONLY the core task action. Normalize the task to the actual action. NEVER include deadline/timeframe words (e.g., "by Friday", "before the weekend", "next week") inside the task field.
3. owner: The explicit person named or self-assigning speaker. If the owner is not explicitly identifiable, output "Not specified" or null. NEVER invent an owner.
4. deadline: The explicit deadline or timeframe mentioned (e.g., "by Friday", "next week", "before next meeting"). If not explicitly mentioned, output "Not specified" or null. NEVER invent a deadline.
5. status: "pending" unless the transcript explicitly states it is completed.
6. evidence: A short verbatim quote or dialogue snippet from the transcript demonstrating this action item.
7. FORBIDDEN: Do NOT include group decisions (such as agreeing on an event date or budget) as action items.

Return STRICT JSON only in this format:
{{
  "action_items": [
    {{
      "task": "Clean task description",
      "owner": "Person Name or Not specified",
      "deadline": "Deadline string or Not specified",
      "status": "pending",
      "confidence": 1.0,
      "evidence": "Quote from transcript"
    }}
  ]
}}

Transcript:
{transcript}"""
