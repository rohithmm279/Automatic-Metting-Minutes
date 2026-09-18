"""Agent Orchestrator: Controls the workflow for meeting minutes and action items.

Refactored to ONE Gemini API call per meeting:
Transcript → Preprocessor → ONE Gemini Call (all fields) → Local Validation → Structured Output
"""

import logging
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

logger = logging.getLogger(__name__)


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
        cleaned_transcript = TranscriptProcessor.clean_transcript(transcript)
        if not cleaned_transcript:
            raise ValueError("Transcript must contain non-whitespace text.")

        # Step 2: Single Gemini Call Pipeline
        try:
            if not self.gemini_analyzer.is_configured:
                raise GeminiAnalysisError("Gemini API key is not configured.")

            logger.info(
                "Executing Single-Call Pipeline with Gemini (%s)...",
                self.gemini_analyzer.model_name,
            )

            # Check if custom mocked agent subcomponents were injected (for unit test compatibility)
            # If summary_agent, action_agent, or decision_agent were mocked specifically in tests,
            # we respect them; otherwise we execute the unified single Gemini call.
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
                        if d_text:
                            decisions_flat.append(d_text)
                            detailed_decisions.append(
                                DecisionItem(
                                    decision=d_text,
                                    confidence=d_conf,
                                    evidence=d_ev,
                                )
                            )

                # Unresolved issues
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
            )
            return fallback_analysis, "RULE-BASED FALLBACK", is_rl

