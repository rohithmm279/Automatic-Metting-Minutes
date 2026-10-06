"""Decision Agent: Extracts explicitly confirmed club decisions and resolutions."""

import json
import logging
import re
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
                dec_text = re.sub(r"^decision\s*[-:–—]\s*", "", str(d.get("decision", "")).strip(), flags=re.IGNORECASE)
                conf = float(d.get("confidence", 1.0)) if d.get("confidence") is not None else 1.0
                evidence = str(d.get("evidence", "")).strip() or None
            elif isinstance(d, str):
                dec_text = re.sub(r"^decision\s*[-:–—]\s*", "", d.strip(), flags=re.IGNORECASE)
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
        return f"""You are an expert Decision Extraction Agent for business, engineering, and student club meetings.
Your task is to identify explicit, settled decisions and distinguish them from action items, unresolved issues, or general discussion.

STRICT DECISION RULES:
1. TAXONOMY: A Decision is an organizational agreement, policy, schedule target, vendor choice, scope cutoff, or architectural design choice confirmed by the group/leads (e.g., "Launch pricing experiment on September 29, 2026 (pending bugs/QA)", "Keep current paywall layout for the experiment", "Monitor conversion daily and decide on changes after seven days of data").
2. DECISION DISCRIMINATOR & ZERO TASK/RISK OVERLAP:
   - Ask: "Is this a structural policy/agreement, or is it an action item, conditional task, or risk mitigation?"
   - NEVER classify individual tasks, operational actions, conditional action items, or risk mitigations as Key Decisions:
     * "Escalate billing provider's sandbox stability issue..." is an Action Item (#5), NOT a Key Decision.
     * "Hard freeze campaign creatives today..." is an operational risk mitigation strategy, NOT an independent Key Decision.
   - If a person or team is assigned to execute or deliver it (e.g., "Priya Sharma will circulate...", "Dev will escalate..."), it belongs ONLY under Action Items.
   - NEVER list an Action Item, individual assignment, or deliverable handoff under Decisions. Key Decisions describe structural policies, milestone dates, vendors, or designs.
3. Include ALL confirmed strategic choices, launch date policies, milestone/freeze agreements, technical scope alignments, and spending policies explicitly agreed, approved, confirmed, finalized, or decided by the group/leads.
4. REJECT PROPOSALS & SPECULATION: DO NOT treat mere suggestions, contested proposals, possibilities, open discussion, or preferences as decisions.
    - DEFERRALS ARE NOT DECISIONS: Statements such as "we have not finalized the date", "let's decide based on the poll", "we'll confirm later", "tentatively Friday", or "not decided yet" are unresolved issues/pending inputs, NEVER Key Decisions.
5. OPEN ISSUES & RISKS (ZERO-RISK HANDLING & ROUTINE MONITORING RULE): Matters that were left open, undecided, awaiting approval, or flagged as active risks in this meeting transcript.
   - ROUTINE MONITORING VS. RISK: General statements like "Let's monitor the logs", "Keep an eye on metrics", or routine operational checks are ongoing operational follow-ups, NOT Open Issues or Risks. Only log explicit blockers, unresolved bugs, or threats to timelines as Open Issues/Risks.
   - ZERO DATA CONTAMINATION & ZERO-RISK HANDLING: If no open issues or risks are present in this transcript, output an empty array []. NEVER generate a dummy risk item containing text like "No issues identified" or "No issues found". NEVER copy example text or invent risks/issues from other meetings.
6. FORMAT: If a source item begins with an operational label such as "Decision –" or "Decision:", remove that label from the returned decision string. Return the decision as clean prose.
7. evidence: Provide a verbatim quote from the transcript confirming the decision.

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
    "Open issue or pending risk"
  ]
}}

Transcript:
{transcript}"""
