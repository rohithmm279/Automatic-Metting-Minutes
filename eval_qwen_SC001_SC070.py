"""Qwen 2.5 3B Full Batch Evaluation -- SC001 through SC070.

Reuses the established benchmark methodology from SC001-SC010:
  - build_prompt() from test_qwen_inference.py / backend.ai.prompts
  - TranscriptProcessor from backend.app.services.transcript_processor
  - SemanticMatcher from backend.app.services.semantic_matcher
  - MeetingValidator from backend.ai.validator
  - MeetingOutput & Pydantic models from backend.models.meeting

Computes per-meeting and aggregate:
  - JSON parse validity
  - Pydantic validation success
  - Lexical token-Jaccard (P, R, F1 at threshold >= 0.5)
  - Semantic similarity (P, R, F1 via all-MiniLM-L6-v2 at threshold >= 0.5)
  - Hallucinated owners and deadlines
  - Inference latency per meeting and total
  - Summary availability

Features checkpointing to resume safely without re-running completed cases.
"""

import sys
import io
import json
import re
import time
import urllib.request
from pathlib import Path
from typing import Any

# Ensure UTF-8 output
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ── Paths ──────────────────────────────────────────────────────────────────────
ROOT = Path(r"r:\S5 mini datasets")
BACKEND = ROOT / "backend"
TRANSCRIPTS = ROOT / "datasets" / "01_PRIMARY" / "student_club" / "transcripts"
GROUND_TRUTH = ROOT / "datasets" / "01_PRIMARY" / "student_club" / "ground_truth"
CHECKPOINT_FILE = ROOT / "qwen_eval_SC001_SC070_checkpoint.json"
RAW_OUT_FILE = ROOT / "qwen_eval_SC001_SC070_raw.json"
METRICS_OUT_FILE = ROOT / "qwen_eval_SC001_SC070_metrics.json"

for _p in (ROOT, BACKEND):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

# ── Imports from project ──────────────────────────────────────────────────────
from backend.ai.prompts import build_meeting_analysis_prompt
from backend.app.services.transcript_processor import TranscriptProcessor
from backend.app.services.semantic_matcher import SemanticMatcher
from backend.ai.validator import MeetingValidator, MeetingValidationError
from backend.models.meeting import ActionItem, Decision, UnresolvedIssue, MeetingOutput

ALL_MEETINGS = [f"SC{i:03d}" for i in range(1, 71)]


# ── Helpers ───────────────────────────────────────────────────────────────────
def call_ollama(prompt: str, timeout: int = 180) -> tuple[str, float]:
    """POST to local Ollama and return (raw_response_text, elapsed_seconds)."""
    payload = json.dumps(
        {
            "model": "qwen2.5:3b",
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.0},
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        "http://localhost:11434/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    elapsed = time.perf_counter() - t0
    return data.get("response", ""), elapsed


def parse_json_output(raw: str) -> dict | None:
    """Strip optional markdown fences and parse JSON."""
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1]
        if cleaned.endswith("```"):
            cleaned = cleaned.rsplit("```", 1)[0]
        cleaned = cleaned.strip()
    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            return data
        return None
    except json.JSONDecodeError:
        return None


def _flatten_string_or_list(item: Any) -> str:
    """Recursively flatten nested lists/dicts to a single string."""
    if isinstance(item, str):
        return item.strip()
    if isinstance(item, list):
        return " ".join(_flatten_string_or_list(x) for x in item).strip()
    if isinstance(item, dict):
        return str(item.get("decision", item.get("issue", item.get("task", str(item))))).strip()
    return str(item).strip()


def validate_pydantic_output(parsed: dict, transcript: str) -> tuple[bool, str | None, MeetingOutput | None]:
    """Check whether parsed dictionary conforms to MeetingOutput and passes MeetingValidator."""
    try:
        summary = str(parsed.get("summary", "")).strip()

        action_items: list[ActionItem] = []
        for item in parsed.get("action_items", []):
            if not isinstance(item, dict):
                continue
            task = str(item.get("task", "")).strip()
            owner = item.get("owner")
            if owner is not None:
                owner = str(owner).strip() or None
            deadline = item.get("deadline")
            if deadline is not None:
                deadline = str(deadline).strip() or None
            status = str(item.get("status", "pending")).strip() or "pending"
            action_items.append(
                ActionItem(
                    task=task,
                    owner=owner,
                    deadline=deadline,
                    status=status,
                    confidence=1.0,
                )
            )

        decisions: list[Decision] = []
        for dec in parsed.get("decisions", []):
            dec_text = _flatten_string_or_list(dec)
            if dec_text:
                decisions.append(Decision(decision=dec_text, confidence=1.0))

        unresolved_issues: list[UnresolvedIssue] = []
        for iss in parsed.get("unresolved_issues", []):
            iss_text = _flatten_string_or_list(iss)
            if iss_text:
                unresolved_issues.append(UnresolvedIssue(issue=iss_text, confidence=1.0))

        m_out = MeetingOutput(
            summary=summary,
            action_items=action_items,
            decisions=decisions,
            unresolved_issues=unresolved_issues,
        )

        validator = MeetingValidator()
        validator.validate(m_out, transcript)
        return True, None, m_out
    except Exception as exc:
        return False, str(exc), None


def gt_task_strings(gt: dict) -> list[str]:
    return [a.get("task", "").strip() for a in gt.get("action_items", []) if a.get("task", "").strip()]


def gt_decision_strings(gt: dict) -> list[str]:
    decisions = gt.get("decisions", [])
    res = []
    for d in decisions:
        s = d.get("decision", d) if isinstance(d, dict) else d
        s = _flatten_string_or_list(s)
        if s:
            res.append(s)
    return res


def gt_issue_strings(gt: dict) -> list[str]:
    issues = gt.get("unresolved_issues", [])
    res = []
    for i in issues:
        s = i.get("issue", i) if isinstance(i, dict) else i
        s = _flatten_string_or_list(s)
        if s:
            res.append(s)
    return res


def pred_task_strings(pred: dict) -> list[str]:
    return [a.get("task", "").strip() for a in pred.get("action_items", []) if isinstance(a, dict) and a.get("task", "").strip()]


def pred_decision_strings(pred: dict) -> list[str]:
    items = pred.get("decisions", [])
    return [_flatten_string_or_list(d) for d in items if _flatten_string_or_list(d)]


def pred_issue_strings(pred: dict) -> list[str]:
    items = pred.get("unresolved_issues", [])
    return [_flatten_string_or_list(i) for i in items if _flatten_string_or_list(i)]


def _token_jaccard(a: str, b: str) -> float:
    ta = set(re.findall(r"\w+", a.lower()))
    tb = set(re.findall(r"\w+", b.lower()))
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def greedy_lexical_matches(preds: list[str], refs: list[str], threshold: float = 0.5) -> int:
    unmatched = list(refs)
    matches = 0
    for p in preds:
        best, best_score = None, 0.0
        for r in unmatched:
            s = _token_jaccard(p, r)
            if s >= threshold and s > best_score:
                best_score, best = s, r
        if best is not None:
            unmatched.remove(best)
            matches += 1
    return matches


def prf(matches: int, n_pred: int, n_ref: int) -> tuple[float, float, float]:
    p = matches / n_pred if n_pred else 0.0
    r = matches / n_ref if n_ref else 0.0
    f = 2 * p * r / (p + r) if (p + r) else 0.0
    return round(p, 4), round(r, 4), round(f, 4)


def detect_hallucinations(pred: dict, transcript: str) -> dict:
    """Flag owners / deadlines that cannot be found in the transcript text."""
    hallucinated_owners = []
    hallucinated_deadlines = []
    tl = transcript.lower()
    for item in pred.get("action_items", []):
        if not isinstance(item, dict):
            continue
        owner = item.get("owner")
        deadline = item.get("deadline")
        if owner and str(owner).strip().lower() not in tl:
            hallucinated_owners.append(str(owner).strip())
        if deadline and str(deadline).strip().lower() not in tl:
            hallucinated_deadlines.append(str(deadline).strip())
    return {"owners": hallucinated_owners, "deadlines": hallucinated_deadlines}


# ── Checkpoint management ─────────────────────────────────────────────────────
def load_checkpoint() -> dict[str, dict]:
    if CHECKPOINT_FILE.exists():
        try:
            with open(CHECKPOINT_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {item["meeting_id"]: item for item in data}
        except Exception:
            return {}
    return {}


def save_checkpoint(results: list[dict]):
    with open(CHECKPOINT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=str)


# ── Main benchmark loop ───────────────────────────────────────────────────────
def run_benchmark():
    print("=" * 75)
    print("  QWEN 2.5 3B FULL EVALUATION BENCHMARK: SC001 -> SC070")
    print("=" * 75)

    cached_results = load_checkpoint()
    if cached_results:
        print(f"Loaded {len(cached_results)} previously completed evaluations from checkpoint.")

    results: list[dict] = []

    total_meetings = len(ALL_MEETINGS)

    for idx, meeting_id in enumerate(ALL_MEETINGS, 1):
        # Check if already in checkpoint
        if meeting_id in cached_results and cached_results[meeting_id].get("parse_ok") is not None:
            rec = cached_results[meeting_id]
            results.append(rec)
            status_str = "OK" if rec.get("parse_ok") else "FAIL"
            print(f"[{idx:02d}/{total_meetings}] {meeting_id} (CACHED) -> Status: {status_str}, AI F1: {rec.get('sem_ai_f1', 0.0):.4f}, Dec F1: {rec.get('sem_dec_f1', 0.0):.4f}, Iss F1: {rec.get('sem_iss_f1', 0.0):.4f}")
            continue

        transcript_path = TRANSCRIPTS / f"{meeting_id}.txt"
        gt_path = GROUND_TRUTH / f"{meeting_id}.json"

        if not transcript_path.exists() or not gt_path.exists():
            print(f"[{idx:02d}/{total_meetings}] {meeting_id} ❌ Missing file(s)")
            results.append({
                "meeting_id": meeting_id,
                "parse_ok": False,
                "error": "Missing transcript or ground truth file",
                "elapsed_s": 0.0,
            })
            save_checkpoint(results)
            continue

        raw_transcript = transcript_path.read_text(encoding="utf-8")
        cleaned_transcript = TranscriptProcessor.clean_transcript(raw_transcript)
        with gt_path.open(encoding="utf-8") as f:
            ground_truth = json.load(f)

        prompt = build_meeting_analysis_prompt(cleaned_transcript)

        try:
            raw_output, elapsed = call_ollama(prompt)
        except Exception as exc:
            print(f"[{idx:02d}/{total_meetings}] {meeting_id} ❌ Ollama call failed: {exc}")
            rec = {
                "meeting_id": meeting_id,
                "parse_ok": False,
                "pydantic_ok": False,
                "error": str(exc),
                "elapsed_s": 0.0,
                "raw_output": "",
            }
            results.append(rec)
            save_checkpoint(results)
            continue

        parsed = parse_json_output(raw_output)

        if parsed is None:
            print(f"[{idx:02d}/{total_meetings}] {meeting_id} ❌ JSON Parse Failed ({elapsed:.1f}s)")
            rec = {
                "meeting_id": meeting_id,
                "parse_ok": False,
                "pydantic_ok": False,
                "error": "JSON parse failed",
                "raw_output": raw_output,
                "elapsed_s": round(elapsed, 2),
            }
            results.append(rec)
            save_checkpoint(results)
            continue

        # Check Pydantic validation
        pyd_ok, pyd_err, m_out = validate_pydantic_output(parsed, cleaned_transcript)

        # Extract tasks, decisions, issues
        gt_tasks = gt_task_strings(ground_truth)
        gt_decs = gt_decision_strings(ground_truth)
        gt_issues = gt_issue_strings(ground_truth)

        pred_tasks = pred_task_strings(parsed)
        pred_decs = pred_decision_strings(parsed)
        pred_issues = pred_issue_strings(parsed)

        # Lexical scores
        lex_ai = greedy_lexical_matches(pred_tasks, gt_tasks)
        lex_dec = greedy_lexical_matches(pred_decs, gt_decs)
        lex_iss = greedy_lexical_matches(pred_issues, gt_issues)

        lex_ai_prf = prf(lex_ai, len(pred_tasks), len(gt_tasks))
        lex_dec_prf = prf(lex_dec, len(pred_decs), len(gt_decs))
        lex_iss_prf = prf(lex_iss, len(pred_issues), len(gt_issues))

        # Semantic scores
        sem_ai = SemanticMatcher.count_semantic_matches(pred_tasks, gt_tasks, "action_items")
        sem_dec = SemanticMatcher.count_semantic_matches(pred_decs, gt_decs, "decisions")
        sem_iss = SemanticMatcher.count_semantic_matches(pred_issues, gt_issues, "unresolved_issues")

        sem_ai_prf = prf(sem_ai, len(pred_tasks), len(gt_tasks))
        sem_dec_prf = prf(sem_dec, len(pred_decs), len(gt_decs))
        sem_iss_prf = prf(sem_iss, len(pred_issues), len(gt_issues))

        # Hallucinations
        hall = detect_hallucinations(parsed, raw_transcript)

        rec = {
            "meeting_id": meeting_id,
            "parse_ok": True,
            "pydantic_ok": pyd_ok,
            "pydantic_error": pyd_err,
            "elapsed_s": round(elapsed, 2),
            "has_summary": bool(parsed.get("summary", "").strip()),
            "n_pred_tasks": len(pred_tasks),
            "n_gt_tasks": len(gt_tasks),
            "n_pred_decs": len(pred_decs),
            "n_gt_decs": len(gt_decs),
            "n_pred_issues": len(pred_issues),
            "n_gt_issues": len(gt_issues),
            # Lexical metrics
            "lex_ai_matches": lex_ai,
            "lex_ai_p": lex_ai_prf[0], "lex_ai_r": lex_ai_prf[1], "lex_ai_f1": lex_ai_prf[2],
            "lex_dec_matches": lex_dec,
            "lex_dec_p": lex_dec_prf[0], "lex_dec_r": lex_dec_prf[1], "lex_dec_f1": lex_dec_prf[2],
            "lex_iss_matches": lex_iss,
            "lex_iss_p": lex_iss_prf[0], "lex_iss_r": lex_iss_prf[1], "lex_iss_f1": lex_iss_prf[2],
            # Semantic metrics
            "sem_ai_matches": sem_ai,
            "sem_ai_p": sem_ai_prf[0], "sem_ai_r": sem_ai_prf[1], "sem_ai_f1": sem_ai_prf[2],
            "sem_dec_matches": sem_dec,
            "sem_dec_p": sem_dec_prf[0], "sem_dec_r": sem_dec_prf[1], "sem_dec_f1": sem_dec_prf[2],
            "sem_iss_matches": sem_iss,
            "sem_iss_p": sem_iss_prf[0], "sem_iss_r": sem_iss_prf[1], "sem_iss_f1": sem_iss_prf[2],
            # Hallucinations
            "hallucinated_owners": hall["owners"],
            "hallucinated_deadlines": hall["deadlines"],
            "hallucination_count": len(hall["owners"]) + len(hall["deadlines"]),
            # Raw string artifacts & structured output
            "raw_output": raw_output,
            "parsed_output": parsed,
            "pred_tasks": pred_tasks,
            "pred_decs": pred_decs,
            "pred_issues": pred_issues,
            "gt_tasks": gt_tasks,
            "gt_decs": gt_decs,
            "gt_issues": gt_issues,
        }

        results.append(rec)
        save_checkpoint(results)

        pyd_label = "OK" if pyd_ok else f"FAIL({pyd_err[:30]})"
        print(
            f"[{idx:02d}/{total_meetings}] {meeting_id} ({elapsed:.1f}s) | "
            f"Pydantic:{pyd_label} | "
            f"AI(Sem):{sem_ai_prf[2]:.2f} | Dec(Sem):{sem_dec_prf[2]:.2f} | Iss(Sem):{sem_iss_prf[2]:.2f} | "
            f"Halluc:{len(hall['owners']) + len(hall['deadlines'])}"
        )

    # ── Aggregate Results Computation ─────────────────────────────────────────
    ok = [r for r in results if r.get("parse_ok")]
    failed = [r for r in results if not r.get("parse_ok")]

    def _avg(vals: list[float]) -> float:
        return round(sum(vals) / len(vals), 4) if vals else 0.0

    agg_keys = (
        "lex_ai_f1", "lex_dec_f1", "lex_iss_f1",
        "sem_ai_f1", "sem_dec_f1", "sem_iss_f1",
        "lex_ai_p", "lex_ai_r", "lex_dec_p", "lex_dec_r",
        "lex_iss_p", "lex_iss_r",
        "sem_ai_p", "sem_ai_r", "sem_dec_p", "sem_dec_r",
        "sem_iss_p", "sem_iss_r"
    )
    agg = {k: _avg([r[k] for r in ok]) for k in agg_keys}

    total_gt_ai   = sum(r["n_gt_tasks"] for r in ok)
    total_pred_ai = sum(r["n_pred_tasks"] for r in ok)
    total_lex_ai  = sum(r["lex_ai_matches"] for r in ok)
    total_sem_ai  = sum(r["sem_ai_matches"] for r in ok)

    total_gt_dec   = sum(r["n_gt_decs"] for r in ok)
    total_pred_dec = sum(r["n_pred_decs"] for r in ok)
    total_lex_dec  = sum(r["lex_dec_matches"] for r in ok)
    total_sem_dec  = sum(r["sem_dec_matches"] for r in ok)

    total_gt_iss   = sum(r["n_gt_issues"] for r in ok)
    total_pred_iss = sum(r["n_pred_issues"] for r in ok)
    total_lex_iss  = sum(r["lex_iss_matches"] for r in ok)
    total_sem_iss  = sum(r["sem_iss_matches"] for r in ok)

    total_hall_owners = sum(len(r["hallucinated_owners"]) for r in ok)
    total_hall_deadlines = sum(len(r["hallucinated_deadlines"]) for r in ok)
    total_hallucinations = total_hall_owners + total_hall_deadlines
    hallucination_rate = round(total_hallucinations / total_pred_ai, 4) if total_pred_ai else 0.0

    times = [r["elapsed_s"] for r in ok if r.get("elapsed_s")]
    total_runtime = round(sum(times), 2)
    avg_runtime = round(total_runtime / len(times), 2) if times else 0.0

    pydantic_successes = sum(1 for r in ok if r.get("pydantic_ok"))
    summary_successes = sum(1 for r in ok if r.get("has_summary"))

    micro_lex_ai = prf(total_lex_ai, total_pred_ai, total_gt_ai)
    micro_sem_ai = prf(total_sem_ai, total_pred_ai, total_gt_ai)
    micro_lex_dec = prf(total_lex_dec, total_pred_dec, total_gt_dec)
    micro_sem_dec = prf(total_sem_dec, total_pred_dec, total_gt_dec)
    micro_lex_iss = prf(total_lex_iss, total_pred_iss, total_gt_iss)
    micro_sem_iss = prf(total_sem_iss, total_pred_iss, total_gt_iss)

    aggregate_data = {
        "total_meetings_evaluated": len(results),
        "parse_successes": len(ok),
        "parse_failures": len(failed),
        "json_validity_rate": round(len(ok) / len(results), 4) if results else 0.0,
        "pydantic_successes": pydantic_successes,
        "pydantic_validity_rate": round(pydantic_successes / len(ok), 4) if ok else 0.0,
        "summary_availability_rate": round(summary_successes / len(ok), 4) if ok else 0.0,
        "total_runtime_s": total_runtime,
        "avg_runtime_s": avg_runtime,
        "action_items": {
            "macro_lex": {"precision": agg["lex_ai_p"], "recall": agg["lex_ai_r"], "f1": agg["lex_ai_f1"]},
            "macro_sem": {"precision": agg["sem_ai_p"], "recall": agg["sem_ai_r"], "f1": agg["sem_ai_f1"]},
            "micro_lex": {"precision": micro_lex_ai[0], "recall": micro_lex_ai[1], "f1": micro_lex_ai[2], "matches": total_lex_ai, "gt_total": total_gt_ai, "pred_total": total_pred_ai},
            "micro_sem": {"precision": micro_sem_ai[0], "recall": micro_sem_ai[1], "f1": micro_sem_ai[2], "matches": total_sem_ai, "gt_total": total_gt_ai, "pred_total": total_pred_ai},
        },
        "decisions": {
            "macro_lex": {"precision": agg["lex_dec_p"], "recall": agg["lex_dec_r"], "f1": agg["lex_dec_f1"]},
            "macro_sem": {"precision": agg["sem_dec_p"], "recall": agg["sem_dec_r"], "f1": agg["sem_dec_f1"]},
            "micro_lex": {"precision": micro_lex_dec[0], "recall": micro_lex_dec[1], "f1": micro_lex_dec[2], "matches": total_lex_dec, "gt_total": total_gt_dec, "pred_total": total_pred_dec},
            "micro_sem": {"precision": micro_sem_dec[0], "recall": micro_sem_dec[1], "f1": micro_sem_dec[2], "matches": total_sem_dec, "gt_total": total_gt_dec, "pred_total": total_pred_dec},
        },
        "unresolved_issues": {
            "macro_lex": {"precision": agg["lex_iss_p"], "recall": agg["lex_iss_r"], "f1": agg["lex_iss_f1"]},
            "macro_sem": {"precision": agg["sem_iss_p"], "recall": agg["sem_iss_r"], "f1": agg["sem_iss_f1"]},
            "micro_lex": {"precision": micro_lex_iss[0], "recall": micro_lex_iss[1], "f1": micro_lex_iss[2], "matches": total_lex_iss, "gt_total": total_gt_iss, "pred_total": total_pred_iss},
            "micro_sem": {"precision": micro_sem_iss[0], "recall": micro_sem_iss[1], "f1": micro_sem_iss[2], "matches": total_sem_iss, "gt_total": total_gt_iss, "pred_total": total_pred_iss},
        },
        "hallucinations": {
            "total_hallucinated_owners": total_hall_owners,
            "total_hallucinated_deadlines": total_hall_deadlines,
            "total_hallucinations": total_hallucinations,
            "hallucination_rate_per_action_item": hallucination_rate,
        }
    }

    # ── Save Artifacts ────────────────────────────────────────────────────────
    # 1. Raw output
    with open(RAW_OUT_FILE, "w", encoding="utf-8") as f:
        json.dump({"per_meeting": results, "aggregate": aggregate_data}, f, indent=2, default=str)
    print(f"\n[Saved] Raw results -> {RAW_OUT_FILE}")

    # 2. Metrics only (lightweight summary artifact)
    clean_metrics_per_meeting = [
        {
            k: v for k, v in r.items()
            if k not in ("raw_output", "parsed_output")
        }
        for r in results
    ]
    with open(METRICS_OUT_FILE, "w", encoding="utf-8") as f:
        json.dump({"aggregate": aggregate_data, "per_meeting": clean_metrics_per_meeting}, f, indent=2, default=str)
    print(f"[Saved] Metrics summary -> {METRICS_OUT_FILE}")

    # ── Print Final Summary ───────────────────────────────────────────────────
    print("\n" + "=" * 75)
    print("  QWEN 2.5 3B FULL EVALUATION BENCHMARK: SC001 - SC070 RESULTS")
    print("=" * 75)
    print(f"  Total Meetings Evaluated : {len(results)}")
    print(f"  JSON Validity Rate       : {aggregate_data['json_validity_rate']*100:.1f}% ({len(ok)}/{len(results)})")
    print(f"  Pydantic Validity Rate   : {aggregate_data['pydantic_validity_rate']*100:.1f}% ({pydantic_successes}/{len(ok)})")
    print(f"  Summary Availability     : {aggregate_data['summary_availability_rate']*100:.1f}%")
    print(f"  Total Latency            : {total_runtime:.1f}s | Avg Latency: {avg_runtime:.2f}s")
    print(f"  Hallucination Rate       : {hallucination_rate*100:.2f}% (Owners: {total_hall_owners}, Deadlines: {total_hall_deadlines})")
    print()
    print(f"  Action Items Semantic F1 : Macro = {agg['sem_ai_f1']:.4f} | Micro = {micro_sem_ai[2]:.4f} (P={agg['sem_ai_p']:.4f}, R={agg['sem_ai_r']:.4f})")
    print(f"  Decisions Semantic F1    : Macro = {agg['sem_dec_f1']:.4f} | Micro = {micro_sem_dec[2]:.4f} (P={agg['sem_dec_p']:.4f}, R={agg['sem_dec_r']:.4f})")
    print(f"  Issues Semantic F1       : Macro = {agg['sem_iss_f1']:.4f} | Micro = {micro_sem_iss[2]:.4f} (P={agg['sem_iss_p']:.4f}, R={agg['sem_iss_r']:.4f})")
    print("=" * 75)


if __name__ == "__main__":
    run_benchmark()
