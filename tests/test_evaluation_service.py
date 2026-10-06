"""Regression tests for evaluation accounting."""

from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.schemas.evaluation_schema import DatasetRecord
from backend.app.services.evaluation_service import EvaluationService


def test_failed_labeled_record_contributes_zero_matches():
    record = DatasetRecord(
        id="bad-1",
        transcript="unrelated text",
        reference_action_items=["Prepare the report"],
        reference_decisions=[],
        reference_issues=[],
        source_dataset="fixture.json",
    )

    result = EvaluationService().evaluate(
        dataset_name="fixture.json",
        requested_limit=1,
        records=[record],
        skipped_records=0,
        analyze=lambda _: (_ for _ in ()).throw(ValueError("invalid transcript")),
    )

    metric = result.metrics["action_items_semantic"]
    assert result.processed_records == 1
    assert result.skipped_records == 1
    assert metric.match_count == 0
    assert metric.f1_score == 0.0