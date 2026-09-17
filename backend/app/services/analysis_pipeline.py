"""Analysis pipeline delegating transcript processing to the multi-agent orchestrator."""

from dataclasses import dataclass
import logging

from app.agents.orchestrator import AgentOrchestrator
from app.schemas.meeting_schema import MeetingAnalysis

logger = logging.getLogger(__name__)


@dataclass
class PipelineAnalysisResult:
    analysis: MeetingAnalysis
    source: str
    rate_limited: bool = False


# Shared orchestrator singleton instance
_orchestrator = AgentOrchestrator()


def analyze_transcript_detailed(transcript: str) -> PipelineAnalysisResult:
    """Clean a transcript, run multi-agent analysis with validation, and safely fall back if needed.

    Returns the analysis along with execution source and rate limit status.

    Raises:
        ValueError: If cleaning leaves no usable transcript content.
    """
    analysis, source, rate_limited = _orchestrator.process_transcript(transcript)
    return PipelineAnalysisResult(
        analysis=analysis,
        source=source,
        rate_limited=rate_limited,
    )


def analyze_transcript(transcript: str) -> MeetingAnalysis:
    """Clean a transcript and run the agentic workflow.

    Raises:
        ValueError: If cleaning leaves no usable transcript content.
    """
    return analyze_transcript_detailed(transcript).analysis
