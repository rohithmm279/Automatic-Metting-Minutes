"""Agent Orchestrator: Controls the multi-agent workflow for meeting minutes and action items."""

import logging
import time
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
    """Central orchestrator coordinating Preprocessor, Summary, Action, Decision, and Validation agents.

    Architecture:
    Transcript
      ↓
    Transcript Preprocessor
      ↓
    Agent Orchestrator
      ↓
    ┌──────────────┬──────────────┬──────────────┐
    ↓              ↓              ↓
    Summary Agent  Action Agent   Decision Agent
    └──────────────┴──────────────┴──────────────┘
      ↓
    Validation Agent
      ↓
    Structured Output
    """

    # Minimum gap (seconds) between agent Gemini calls to avoid bursting rate limits.
    # The GeminiAnalyzer itself also enforces _INTER_CALL_PACE_S after each successful
    # call, so this adds an explicit orchestrator-level guard between agents.
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
        """Execute the full agentic workflow.

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

        # Step 2: Try Agentic Gemini Pipeline
        try:
            if not self.gemini_analyzer.is_configured:
                raise GeminiAnalysisError("Gemini API key is not configured.")

            logger.info(
                "Executing Agentic Pipeline with Gemini (%s)...",
                self.gemini_analyzer.model_name,
            )

            # Step 2a: Summary Agent
            logger.debug("Running Summary Agent...")
            summary = self.summary_agent.generate_summary(cleaned_transcript)

            # Inter-agent pacing: prevent back-to-back bursts hitting the rate limit
            time.sleep(self._INTER_AGENT_DELAY_S)

            # Step 2b: Action Agent
            logger.debug("Running Action Agent...")
            action_items = self.action_agent.extract_action_items(cleaned_transcript)

            time.sleep(self._INTER_AGENT_DELAY_S)

            # Step 2c: Decision Agent
            logger.debug("Running Decision Agent...")
            decisions_flat, detailed_decisions, unresolved_issues = self.decision_agent.extract_decisions(
                cleaned_transcript
            )

            # Step 2d: Validation Agent (no API call — runs locally)
            logger.debug("Running Validation Agent...")
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

            # Step 2e: Final Structured Output
            analysis = MeetingAnalysis(
                summary=val_summary,
                action_items=val_actions,
                decisions=val_decisions,
                unresolved_issues=unresolved_issues,
                detailed_decisions=val_detailed_decs,
                validation=overall_validation,
            )
            logger.info("Agentic pipeline completed successfully (AGENTIC_GEMINI).")
            return analysis, "AGENTIC_GEMINI", False

        except (GeminiAnalysisError, Exception) as error:
            # Step 3: Graceful Rule-Based Fallback
            is_rl = False
            if isinstance(error, GeminiAnalysisError):
                is_rl = error.is_rate_limit
                logger.warning(
                    "Agentic Gemini failed: %s (%s). Falling back to rule-based analyzer.",
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
                    "Agentic Gemini failed: %s. Falling back to rule-based analyzer.",
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
