"""Small model-adapter boundary for comparable analysis execution."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

from backend.models.normalized_analysis import NormalizedMeetingAnalysis, normalize_analysis


class AnalysisAdapter(Protocol):
    """Interface implemented by model and fallback analysis providers."""

    model_name: str
    pipeline_name: str
    prompt_version: str

    def analyze(self, transcript: str) -> NormalizedMeetingAnalysis:
        """Analyze one transcript and return the shared internal contract."""


class QwenAdapter:
    """Adapter around the canonical local Qwen orchestrator."""

    model_name = "qwen2.5:3b"
    pipeline_name = "qwen_application"
    prompt_version = "backend.ai.prompts.v1"

    def __init__(self, orchestrator: Any):
        self.orchestrator = orchestrator

    def analyze(self, transcript: str) -> NormalizedMeetingAnalysis:
        result = self.orchestrator.analyze(transcript)
        return normalize_analysis(
            result,
            model_name=self.model_name,
            pipeline_name=self.pipeline_name,
            prompt_version=self.prompt_version,
        )


class CallableAdapter:
    """Adapter for an existing callable, useful for evaluation and fallback paths."""

    def __init__(
        self,
        analyzer: Callable[[str], Any],
        *,
        model_name: str,
        pipeline_name: str,
        prompt_version: str,
        fallback_used: bool = False,
    ):
        self.analyzer = analyzer
        self.model_name = model_name
        self.pipeline_name = pipeline_name
        self.prompt_version = prompt_version
        self.fallback_used = fallback_used

    def analyze(self, transcript: str) -> NormalizedMeetingAnalysis:
        result = self.analyzer(transcript)
        return normalize_analysis(
            result,
            model_name=self.model_name,
            pipeline_name=self.pipeline_name,
            prompt_version=self.prompt_version,
            fallback_used=self.fallback_used,
        )