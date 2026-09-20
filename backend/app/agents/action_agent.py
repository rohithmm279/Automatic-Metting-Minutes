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
        return f"""You are an expert Action Item Extraction Agent for business, engineering, and student club meetings.
Your job is to identify only explicit engineering/operational tasks, commitments, or assignments from the transcript.

STRICT EXTRACTION RULES:
1. Extract only concrete engineering or operational tasks that are actually assigned, requested, or explicitly committed to.
2. OWNER BINDING & SELF-COMMITMENT PRECEDENCE: Assign tasks to the person who explicitly self-commits ("I will do X", "I'll handle this", "My action item is X", "I can take that") or is directly requested ("Priya, can you..."). When tasks are listed with names (e.g. "1. Marcus: Update..."), extract that named person. NEVER assign tasks to the meeting host or Incident Commander simply because they summarized or requested the task at the end. If unassigned, output "Not specified" or null. NEVER invent an owner.
3. NO META-TASKS: Do NOT extract meta-instructions or meeting administrative commands (e.g., "log the action items", "assign tasks to log", "note down the meeting minutes", "record these in Jira") as action items. Do NOT assign fake tasks to facilitators simply because they asked the team to record or log items.
4. task: ONLY the core task action. Normalize the task to the actual action. NEVER include deadline/timeframe words (e.g., "by Friday", "before the weekend", "next week", "by EOD tomorrow", "today") inside the task field.
5. deadline: ALL action item deadlines MUST be formatted strictly as ISO standard dates: YYYY-MM-DD (e.g., "2026-09-20", "2026-09-22", "2026-09-23", "2026-10-05").
   - FORWARD RELATIVE DATE MATH RULE: When calculating relative weekdays ("by Wednesday", "by Tuesday", "this Friday", "tomorrow", "by EOD"), ALWAYS compute strictly forward from the Meeting Header Date. For example, for a meeting on Sunday Sep 20, 2026, "by Wednesday" is 2026-09-23 (Sep 20 + 3 days = Sep 23). NEVER output a deadline date that occurs BEFORE the meeting header date (e.g., NEVER output 2026-09-03 or 2026-09-14).
   - NO INCIDENT / TIMELINE TIMESTAMPS AS DEADLINES: Incident event timestamps, alert firing times (e.g., "11:02 AM", "14:30 UTC"), log timestamps, and dialogue timestamps indicate when past events occurred, NOT task deadlines. If no explicit future calendar date is mentioned, output "Not specified" or null.
6. status: "pending" unless the transcript explicitly states it is completed.
7. evidence: A short verbatim quote or dialogue snippet from the transcript demonstrating this action item.
8. FORBIDDEN: Do NOT include group decisions (such as agreeing on an event date or budget) as action items.

Return STRICT JSON only in this format:
{{
  "action_items": [
    {{
      "task": "Clean task description",
      "owner": "Person Name or Not specified",
      "deadline": "YYYY-MM-DD or Not specified",
      "status": "pending",
      "confidence": 1.0,
      "evidence": "Quote from transcript"
    }}
  ]
}}

Transcript:
{transcript}"""
