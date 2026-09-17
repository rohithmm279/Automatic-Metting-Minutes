"""Controlled Prompt V2 Evaluation for 14 Affected Meetings.

Evaluates the 14 meetings identified by benchmark failure analysis:
  SC012, SC016, SC018, SC025, SC030, SC033, SC037,
  SC043, SC049, SC054, SC056, SC059, SC060, SC064

Compares V1 (production prompt) vs V2 (experimental prompts_v2.py).
Reuses identical:
  - qwen2.5:3b via Ollama (temp=0.0)
  - TranscriptProcessor.clean_transcript()
  - Pydantic validation & MeetingValidator
  - SemanticMatcher (all-MiniLM-L6-v2, threshold >= 0.5)
  - Lexical token-Jaccard (threshold >= 0.5)
  - Ground truth files
"""

import sys
import io
import json
import re
import time
import urllib.request
from pathlib import Path
from typing import Any

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ── Paths ──────────────────────────────────────────────────────────────────────
ROOT = Path(r"r:\S5 mini datasets")
BACKEND = ROOT / "backend"
TRANSCRIPTS = ROOT / "datasets" / "01_PRIMARY" / "student_club" / "transcripts"
GROUND_TRUTH = ROOT / "datasets" / "01_PRIMARY" / "student_club" / "ground_truth"
V1_RAW_FILE = ROOT / "qwen_eval_SC001_SC070_raw.json"
V2_RAW_FILE = ROOT / "qwen_eval_prompt_v2_affected_raw.json"
V2_METRICS_FILE = ROOT / "qwen_eval_prompt_v2_affected_metrics.json"

for _p in (ROOT, BACKEND):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from prompts_v2 import build_prompt_v2
from backend.app.services.transcript_processor import TranscriptProcessor
from backend.app.services.semantic_matcher import SemanticMatcher
from backend.ai.validator import MeetingValidator
from backend.models.meeting import ActionItem, Decision, UnresolvedIssue, MeetingOutput

AFFECTED_MEETINGS = [
    "SC012", "SC016", "SC018", "SC025", "SC030", "SC033", "SC037",
    "SC043", "SC049", "SC054", "SC056", "SC059", "SC060", "SC064"
]


# ── Helpers ───────────────────────────────────────────────────────────────────
def call_ollama(prompt: str, timeout: int = 180) -> tuple[str, float]:
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
    if isinstance(item, str):
        return item.strip()
    if isinstance(item, list):
        return " ".join(_flatten_string_or_list(x) for x in item).strip()
    if isinstance(item, dict):
        return str(item.get("decision", item.get("issue", item.get("task", str(item))))).strip()
    return str(item).strip()


def validate_pydantic_output(parsed: dict, transcript: str) -> tuple[bool, str | None, MeetingOutput | None]:
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


# ── Load Baseline V1 Results for the 14 Meetings ──────────────────────────────
def load_v1_baseline() -> dict[str, dict]:
    if not V1_RAW_FILE.exists():
        raise FileNotFoundError(f"Missing baseline file: {V1_RAW_FILE}")
    with open(V1_RAW_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    v1_map = {}
    for item in data.get("per_meeting", []):
        if item.get("meeting_id") in AFFECTED_MEETINGS:
            v1_map[item["meeting_id"]] = item
    return v1_map


# ── Run Evaluation ────────────────────────────────────────────────────────────
def run_experiment():
    print("=" * 75)
    print("  PROMPT V2 CONTROLLED EXPERIMENT: 14 AFFECTED MEETINGS")
    print("=" * 75)

    v1_baseline = load_v1_baseline()
    print(f"Loaded V1 baseline for {len(v1_baseline)} affected meetings.")

    results_v2: list[dict] = []

    for idx, meeting_id in enumerate(AFFECTED_MEETINGS, 1):
        transcript_path = TRANSCRIPTS / f"{meeting_id}.txt"
        gt_path = GROUND_TRUTH / f"{meeting_id}.json"

        raw_transcript = transcript_path.read_text(encoding="utf-8")
        cleaned_transcript = TranscriptProcessor.clean_transcript(raw_transcript)
        with gt_path.open(encoding="utf-8") as f:
            ground_truth = json.load(f)

        prompt_v2 = build_prompt_v2(cleaned_transcript)

        try:
            raw_output, elapsed = call_ollama(prompt_v2)
        except Exception as exc:
            print(f"[{idx:02d}/14] {meeting_id} ❌ Ollama call failed: {exc}")
            results_v2.append({
                "meeting_id": meeting_id,
                "parse_ok": False,
                "pydantic_ok": False,
                "error": str(exc),
                "elapsed_s": 0.0,
            })
            continue

        parsed = parse_json_output(raw_output)
        if parsed is None:
            print(f"[{idx:02d}/14] {meeting_id} ❌ JSON Parse Failed")
            results_v2.append({
                "meeting_id": meeting_id,
                "parse_ok": False,
                "pydantic_ok": False,
                "error": "JSON parse failed",
                "raw_output": raw_output,
                "elapsed_s": round(elapsed, 2),
            })
            continue

        pyd_ok, pyd_err, m_out = validate_pydantic_output(parsed, cleaned_transcript)

        gt_tasks = gt_task_strings(ground_truth)
        gt_decs = gt_decision_strings(ground_truth)
        gt_issues = gt_issue_strings(ground_truth)

        pred_tasks = pred_task_strings(parsed)
        pred_decs = pred_decision_strings(parsed)
        pred_issues = pred_issue_strings(parsed)

        # Lexical
        lex_ai = greedy_lexical_matches(pred_tasks, gt_tasks)
        lex_dec = greedy_lexical_matches(pred_decs, gt_decs)
        lex_iss = greedy_lexical_matches(pred_issues, gt_issues)

        lex_ai_prf = prf(lex_ai, len(pred_tasks), len(gt_tasks))
        lex_dec_prf = prf(lex_dec, len(pred_decs), len(gt_decs))
        lex_iss_prf = prf(lex_iss, len(pred_issues), len(gt_issues))

        # Semantic
        sem_ai = SemanticMatcher.count_semantic_matches(pred_tasks, gt_tasks, "action_items")
        sem_dec = SemanticMatcher.count_semantic_matches(pred_decs, gt_decs, "decisions")
        sem_iss = SemanticMatcher.count_semantic_matches(pred_issues, gt_issues, "unresolved_issues")

        sem_ai_prf = prf(sem_ai, len(pred_tasks), len(gt_tasks))
        sem_dec_prf = prf(sem_dec, len(pred_decs), len(gt_decs))
        sem_iss_prf = prf(sem_iss, len(pred_issues), len(gt_issues))

        # Hallucinations
        hall = detect_hallucinations(parsed, raw_transcript)

        # Baseline comparison
        v1_rec = v1_baseline.get(meeting_id, {})
        v1_iss_f1 = v1_rec.get("sem_iss_f1", 0.0)
        v1_ai_f1 = v1_rec.get("sem_ai_f1", 0.0)
        v1_dec_f1 = v1_rec.get("sem_dec_f1", 0.0)

        delta_iss = round(sem_iss_prf[2] - v1_iss_f1, 4)
        delta_ai = round(sem_ai_prf[2] - v1_ai_f1, 4)
        delta_dec = round(sem_dec_prf[2] - v1_dec_f1, 4)

        rec = {
            "meeting_id": meeting_id,
            "parse_ok": True,
            "pydantic_ok": pyd_ok,
            "pydantic_error": pyd_err,
            "elapsed_s": round(elapsed, 2),
            "has_summary": bool(parsed.get("summary", "").strip()),
            # Counts
            "n_pred_tasks": len(pred_tasks),
            "n_gt_tasks": len(gt_tasks),
            "n_pred_decs": len(pred_decs),
            "n_gt_decs": len(gt_decs),
            "n_pred_issues": len(pred_issues),
            "n_gt_issues": len(gt_issues),
            # V2 Metrics
            "lex_ai_f1": lex_ai_prf[2],
            "sem_ai_p": sem_ai_prf[0], "sem_ai_r": sem_ai_prf[1], "sem_ai_f1": sem_ai_prf[2],
            "lex_dec_f1": lex_dec_prf[2],
            "sem_dec_p": sem_dec_prf[0], "sem_dec_r": sem_dec_prf[1], "sem_dec_f1": sem_dec_prf[2],
            "lex_iss_f1": lex_iss_prf[2],
            "sem_iss_p": sem_iss_prf[0], "sem_iss_r": sem_iss_prf[1], "sem_iss_f1": sem_iss_prf[2],
            # V1 Comparison
            "v1_sem_iss_f1": v1_iss_f1,
            "delta_sem_iss_f1": delta_iss,
            "v1_sem_ai_f1": v1_ai_f1,
            "delta_sem_ai_f1": delta_ai,
            "v1_sem_dec_f1": v1_dec_f1,
            "delta_sem_dec_f1": delta_dec,
            # Hallucinations
            "hallucinated_owners": hall["owners"],
            "hallucinated_deadlines": hall["deadlines"],
            "hallucination_count": len(hall["owners"]) + len(hall["deadlines"]),
            # Data strings
            "v1_pred_issues": v1_rec.get("pred_issues", []),
            "v2_pred_issues": pred_issues,
            "v1_pred_decs": v1_rec.get("pred_decs", []),
            "v2_pred_decs": pred_decs,
            "v1_pred_tasks": v1_rec.get("pred_tasks", []),
            "v2_pred_tasks": pred_tasks,
            "gt_issues": gt_issues,
            "gt_decs": gt_decs,
            "gt_tasks": gt_tasks,
            "raw_output": raw_output,
            "parsed_output": parsed,
        }

        results_v2.append(rec)
        print(
            f"[{idx:02d}/14] {meeting_id} | Iss F1: {v1_iss_f1:.2f} -> {sem_iss_prf[2]:.2f} (Δ {delta_iss:+.2f}) | "
            f"Dec F1: {v1_dec_f1:.2f} -> {sem_dec_prf[2]:.2f} (Δ {delta_dec:+.2f}) | "
            f"AI F1: {v1_ai_f1:.2f} -> {sem_ai_prf[2]:.2f} (Δ {delta_ai:+.2f})"
        )

    # ── Aggregate Comparison ──────────────────────────────────────────────────
    ok_v2 = [r for r in results_v2 if r.get("parse_ok")]

    def _avg(vals: list[float]) -> float:
        return round(sum(vals) / len(vals), 4) if vals else 0.0

    avg_v1_iss = _avg([r["v1_sem_iss_f1"] for r in ok_v2])
    avg_v2_iss = _avg([r["sem_iss_f1"] for r in ok_v2])
    avg_v1_dec = _avg([r["v1_sem_dec_f1"] for r in ok_v2])
    avg_v2_dec = _avg([r["sem_dec_f1"] for r in ok_v2])
    avg_v1_ai  = _avg([r["v1_sem_ai_f1"] for r in ok_v2])
    avg_v2_ai  = _avg([r["sem_ai_f1"] for r in ok_v2])

    total_hall_owners = sum(len(r["hallucinated_owners"]) for r in ok_v2)
    total_hall_deadlines = sum(len(r["hallucinated_deadlines"]) for r in ok_v2)
    total_hallucinations = total_hall_owners + total_hall_deadlines
    total_pred_tasks = sum(r["n_pred_tasks"] for r in ok_v2)
    hall_rate = round(total_hallucinations / total_pred_tasks, 4) if total_pred_tasks else 0.0

    aggregate_summary = {
        "meetings_evaluated": len(results_v2),
        "json_validity_rate": round(len(ok_v2) / len(results_v2), 4),
        "pydantic_validity_rate": round(sum(1 for r in ok_v2 if r.get("pydantic_ok")) / len(ok_v2), 4),
        "issue_sem_macro_f1": {"v1": avg_v1_iss, "v2": avg_v2_iss, "delta": round(avg_v2_iss - avg_v1_iss, 4)},
        "decision_sem_macro_f1": {"v1": avg_v1_dec, "v2": avg_v2_dec, "delta": round(avg_v2_dec - avg_v1_dec, 4)},
        "action_sem_macro_f1": {"v1": avg_v1_ai, "v2": avg_v2_ai, "delta": round(avg_v2_ai - avg_v1_ai, 4)},
        "hallucinations": {
            "total_owners": total_hall_owners,
            "total_deadlines": total_hall_deadlines,
            "rate": hall_rate
        }
    }

    # Save raw
    with open(V2_RAW_FILE, "w", encoding="utf-8") as f:
        json.dump({"per_meeting": results_v2, "aggregate": aggregate_summary}, f, indent=2, default=str)
    print(f"\n[Saved] Raw results -> {V2_RAW_FILE}")

    # Save clean metrics
    clean_metrics = [
        {k: v for k, v in r.items() if k not in ("raw_output", "parsed_output")}
        for r in results_v2
    ]
    with open(V2_METRICS_FILE, "w", encoding="utf-8") as f:
        json.dump({"aggregate": aggregate_summary, "per_meeting": clean_metrics}, f, indent=2, default=str)
    print(f"[Saved] Metrics -> {V2_METRICS_FILE}")

    print("\n" + "=" * 75)
    print("  SUMMARY: AFFECTED 14 MEETINGS (V1 vs V2)")
    print("=" * 75)
    print(f"  Unresolved Issues Semantic F1 : V1 = {avg_v1_iss:.4f}  ->  V2 = {avg_v2_iss:.4f}  (Δ {avg_v2_iss - avg_v1_iss:+.4f})")
    print(f"  Decisions Semantic F1         : V1 = {avg_v1_dec:.4f}  ->  V2 = {avg_v2_dec:.4f}  (Δ {avg_v2_dec - avg_v1_dec:+.4f})")
    print(f"  Action Items Semantic F1      : V1 = {avg_v1_ai:.4f}  ->  V2 = {avg_v2_ai:.4f}  (Δ {avg_v2_ai - avg_v1_ai:+.4f})")
    print(f"  Hallucination Count           : {total_hallucinations} (Owners: {total_hall_owners}, Deadlines: {total_hall_deadlines})")
    print("=" * 75)


if __name__ == "__main__":
    run_experiment()
