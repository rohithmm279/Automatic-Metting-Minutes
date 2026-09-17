"""Schemas for dataset discovery and analyzer evaluation."""

from typing import Literal, Optional

from pydantic import BaseModel, Field


class DatasetInfo(BaseModel):
    """Basic metadata for a discovered selectable file or collection."""

    name: str
    entry_type: Literal["file", "directory"]
    file_format: str
    size_bytes: int
    supported_file_count: int = 1


class DatasetRecord(BaseModel):
    """A normalized record loaded without changing its source dataset."""

    id: str
    transcript: str
    reference_summary: Optional[str] = None
    reference_action_items: Optional[list[str]] = None
    reference_decisions: Optional[list[str]] = None
    reference_issues: Optional[list[str]] = None
    source_dataset: str


class MetricScore(BaseModel):
    """Specific metric values for lexical or semantic matching."""

    match_count: int = 0
    precision: Optional[float] = None
    recall: Optional[float] = None
    f1_score: Optional[float] = None


class EvaluationMetric(BaseModel):
    """An explainable aggregate metric; unavailable fields are ``None``."""

    available: bool
    evaluated_records: int = 0
    reference_count: int = 0
    prediction_count: int = 0
    match_count: int = 0
    precision: Optional[float] = None
    recall: Optional[float] = None
    f1_score: Optional[float] = None
    message: str
    lexical: Optional[MetricScore] = None
    semantic: Optional[MetricScore] = None


class RecordSourceInfo(BaseModel):
    """Metadata detailing the execution source for a processed record."""

    record_id: str
    source: str
    rate_limited: bool = False


class EvaluationRequest(BaseModel):
    """Request a bounded evaluation of one discovered dataset file."""

    dataset_name: str = Field(..., min_length=1)
    limit: int = Field(default=10, ge=1, le=50)
    pacing_seconds: float = Field(default=0.0, ge=0.0, le=10.0)


class EvaluationResult(BaseModel):
    """Aggregate result for a limited dataset evaluation run."""

    dataset_name: str
    requested_limit: int
    processed_records: int
    skipped_records: int
    gemini_records: int = 0
    fallback_records: int = 0
    rate_limited_records: int = 0
    record_sources: list[RecordSourceInfo] = []
    metrics: dict[str, EvaluationMetric]
