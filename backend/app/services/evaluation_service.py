"""Explainable baseline and semantic evaluation for meeting dataset records."""

import re
import time
from collections.abc import Callable
from typing import Any

from app.schemas.evaluation_schema import (
    DatasetRecord,
    EvaluationMetric,
    EvaluationResult,
    MetricScore,
    RecordSourceInfo,
)
from app.schemas.meeting_schema import MeetingAnalysis
from app.services.analysis_pipeline import PipelineAnalysisResult
from app.services.semantic_matcher import SemanticMatcher


class EvaluationService:
    """Compare analyzer output with annotations using lexical and semantic matching."""

    def evaluate(
        self,
        dataset_name: str,
        requested_limit: int,
        records: list[DatasetRecord],
        skipped_records: int,
        analyze: Callable[[str], MeetingAnalysis | PipelineAnalysisResult | Any],
        pacing_seconds: float = 0.0,
    ) -> EvaluationResult:
        """Run analysis and aggregate dual lexical and semantic metrics."""
        predictions: list[tuple[DatasetRecord, MeetingAnalysis]] = []
        record_sources: list[RecordSourceInfo] = []
        gemini_count = 0
        fallback_count = 0
        rate_limited_count = 0
        skipped = skipped_records

        for i, record in enumerate(records):
            try:
                raw_result = analyze(record.transcript)
                if isinstance(raw_result, PipelineAnalysisResult):
                    analysis = raw_result.analysis
                    source = raw_result.source
                    is_rl = raw_result.rate_limited
                elif hasattr(raw_result, "analysis") and hasattr(raw_result, "source"):
                    analysis = raw_result.analysis
                    source = getattr(raw_result, "source", "UNKNOWN")
                    is_rl = getattr(raw_result, "rate_limited", False)
                else:
                    analysis = raw_result
                    source = "UNKNOWN"
                    is_rl = False

                predictions.append((record, analysis))
                record_sources.append(
                    RecordSourceInfo(
                        record_id=record.id,
                        source=source,
                        rate_limited=is_rl,
                    )
                )
                if source == "GEMINI":
                    gemini_count += 1
                elif "FALLBACK" in source:
                    fallback_count += 1
                if is_rl:
                    rate_limited_count += 1

            except (ValueError, TypeError):
                skipped += 1

            if pacing_seconds > 0.0 and i < len(records) - 1:
                time.sleep(pacing_seconds)

        action_metric = self._dual_overlap_metric(
            predictions,
            lambda analysis: [item.task for item in analysis.action_items],
            lambda record: record.reference_action_items,
            category="action_items",
        )
        decision_metric = self._dual_overlap_metric(
            predictions,
            lambda analysis: analysis.decisions,
            lambda record: record.reference_decisions,
            category="decisions",
        )
        issue_metric = self._dual_overlap_metric(
            predictions,
            lambda analysis: analysis.unresolved_issues,
            lambda record: record.reference_issues,
            category="unresolved_issues",
        )
        summary_metric = self._summary_metric(predictions)

        metrics: dict[str, EvaluationMetric] = {
            "summary_availability": summary_metric,
            "action_items": action_metric,
            "action_items_lexical": self._create_sub_metric(action_metric, action_metric.lexical, "Lexical (token Jaccard)"),
            "action_items_semantic": self._create_sub_metric(action_metric, action_metric.semantic, "Semantic"),
            "decisions": decision_metric,
            "decisions_lexical": self._create_sub_metric(decision_metric, decision_metric.lexical, "Lexical (token Jaccard)"),
            "decisions_semantic": self._create_sub_metric(decision_metric, decision_metric.semantic, "Semantic"),
            "unresolved_issues": issue_metric,
            "unresolved_issues_lexical": self._create_sub_metric(issue_metric, issue_metric.lexical, "Lexical (token Jaccard)"),
            "unresolved_issues_semantic": self._create_sub_metric(issue_metric, issue_metric.semantic, "Semantic"),
        }

        return EvaluationResult(
            dataset_name=dataset_name,
            requested_limit=requested_limit,
            processed_records=len(predictions),
            skipped_records=skipped,
            gemini_records=gemini_count,
            fallback_records=fallback_count,
            rate_limited_records=rate_limited_count,
            record_sources=record_sources,
            metrics=metrics,
        )

    @staticmethod
    def _summary_metric(
        predictions: list[tuple[DatasetRecord, MeetingAnalysis]]
    ) -> EvaluationMetric:
        """Report whether summaries are present where reference summaries exist."""
        labeled = [(record, analysis) for record, analysis in predictions if record.reference_summary]
        if not labeled:
            return EvaluationMetric(available=False, message="No reference summaries are available.")
        matches = sum(bool(analysis.summary.strip()) for _, analysis in labeled)
        return EvaluationMetric(
            available=True,
            evaluated_records=len(labeled),
            reference_count=len(labeled),
            prediction_count=matches,
            match_count=matches,
            message="Measures whether a non-empty summary was produced for labeled records.",
        )

    def _dual_overlap_metric(
        self,
        predictions: list[tuple[DatasetRecord, MeetingAnalysis]],
        prediction_getter: Callable[[MeetingAnalysis], list[str]],
        reference_getter: Callable[[DatasetRecord], list[str] | None],
        category: str,
    ) -> EvaluationMetric:
        """Compute both lexical (token Jaccard) and explainable semantic overlap metrics."""
        labeled = [(record, analysis) for record, analysis in predictions if reference_getter(record) is not None]
        if not labeled:
            return EvaluationMetric(available=False, message="No reference annotations are available.")

        predicted_count = reference_count = 0
        lexical_matches = semantic_matches = 0

        for record, analysis in labeled:
            predicted = prediction_getter(analysis)
            reference = reference_getter(record) or []
            predicted_count += len(predicted)
            reference_count += len(reference)
            lexical_matches += self._match_count(predicted, reference)
            semantic_matches += SemanticMatcher.count_semantic_matches(predicted, reference, category=category)  # type: ignore[arg-type]

        lex_p = round(lexical_matches / predicted_count, 4) if predicted_count else 0.0
        lex_r = round(lexical_matches / reference_count, 4) if reference_count else 0.0
        lex_f1 = round(2 * lex_p * lex_r / (lex_p + lex_r), 4) if lex_p + lex_r else 0.0

        sem_p = round(semantic_matches / predicted_count, 4) if predicted_count else 0.0
        sem_r = round(semantic_matches / reference_count, 4) if reference_count else 0.0
        sem_f1 = round(2 * sem_p * sem_r / (sem_p + sem_r), 4) if sem_p + sem_r else 0.0

        lex_score = MetricScore(
            match_count=lexical_matches,
            precision=lex_p,
            recall=lex_r,
            f1_score=lex_f1,
        )
        sem_score = MetricScore(
            match_count=semantic_matches,
            precision=sem_p,
            recall=sem_r,
            f1_score=sem_f1,
        )

        return EvaluationMetric(
            available=True,
            evaluated_records=len(labeled),
            reference_count=reference_count,
            prediction_count=predicted_count,
            match_count=semantic_matches,
            precision=sem_p,
            recall=sem_r,
            f1_score=sem_f1,
            lexical=lex_score,
            semantic=sem_score,
            message="Reports baseline lexical (token Jaccard >= 0.5) and normalized semantic overlap.",
        )

    @staticmethod
    def _create_sub_metric(
        parent: EvaluationMetric,
        score: MetricScore | None,
        method_name: str,
    ) -> EvaluationMetric:
        """Derive a dedicated EvaluationMetric view for either lexical or semantic scores."""
        if not parent.available or score is None:
            return EvaluationMetric(available=False, message=f"{method_name} metric is not available.")
        return EvaluationMetric(
            available=True,
            evaluated_records=parent.evaluated_records,
            reference_count=parent.reference_count,
            prediction_count=parent.prediction_count,
            match_count=score.match_count,
            precision=score.precision,
            recall=score.recall,
            f1_score=score.f1_score,
            message=f"{method_name} evaluation metric.",
        )

    @staticmethod
    def _match_count(predicted: list[str], reference: list[str]) -> int:
        """Count one-to-one text matches using a transparent token-overlap threshold."""
        unmatched_references = list(reference)
        matches = 0
        for prediction in predicted:
            for reference_item in unmatched_references:
                if EvaluationService._token_overlap(prediction, reference_item) >= 0.5:
                    unmatched_references.remove(reference_item)
                    matches += 1
                    break
        return matches

    @staticmethod
    def _token_overlap(left: str, right: str) -> float:
        """Return Jaccard overlap for lower-cased alphanumeric word sets."""
        left_tokens = set(re.findall(r"\w+", left.lower()))
        right_tokens = set(re.findall(r"\w+", right.lower()))
        if not left_tokens or not right_tokens:
            return 0.0
        return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)
