"""Shared, deterministic metrics used by evaluation and benchmark adapters."""

from __future__ import annotations

import re


def token_overlap(left: str, right: str) -> float:
    """Return token Jaccard overlap using the established evaluation rule."""
    left_tokens = set(re.findall(r"\w+", left.lower()))
    right_tokens = set(re.findall(r"\w+", right.lower()))
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def greedy_match_count(predicted: list[str], reference: list[str], threshold: float = 0.5) -> int:
    """Count one-to-one lexical matches without changing the existing threshold."""
    unmatched = list(reference)
    matches = 0
    for prediction in predicted:
        best_reference = None
        best_score = 0.0
        for reference_item in unmatched:
            score = token_overlap(prediction, reference_item)
            if score >= threshold and score > best_score:
                best_reference = reference_item
                best_score = score
        if best_reference is not None:
            unmatched.remove(best_reference)
            matches += 1
    return matches


def precision_recall_f1(matches: int, predicted_count: int, reference_count: int) -> tuple[float, float, float]:
    """Return rounded precision, recall, and F1 values."""
    precision = matches / predicted_count if predicted_count else 0.0
    recall = matches / reference_count if reference_count else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return round(precision, 4), round(recall, 4), round(f1, 4)