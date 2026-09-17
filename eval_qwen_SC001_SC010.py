"""Qwen 2.5 3B Batch Evaluation -- SC001 through SC010.

Reuses:
  - build_prompt() from test_qwen_inference.py (prompt unchanged)
  - SemanticMatcher from backend/app/services/semantic_matcher.py (unmodified)

Computes per-meeting and aggregate:
  - lexical token-Jaccard F1  (threshold >= 0.5)
  - semantic F1               (SemanticMatcher, threshold >= 0.5)
  - summary availability
  - JSON parse failures
  - hallucinated owners / deadlines
  - inference time
"""

import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import importlib.util
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

# ── path setup ────────────────────────────────────────────────────────────────
ROOT = Path(r"r:\S5 mini datasets")
BACKEND = ROOT / "backend"
TRANSCRIPTS = ROOT / "datasets" / "01_PRIMARY" / "student_club" / "transcripts"
GROUND_TRUTH = ROOT / "datasets" / "01_PRIMARY" / "student_club" / "ground_truth"
MEETINGS = [f"SC{i:03d}" for i in range(1, 11)]

# Add project root and backend to sys.path
for _p in (ROOT, BACKEND):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

try:
    from backend.app.services.semantic_matcher import SemanticMatcher  # noqa: E402
except ImportError:
    from app.services.semantic_matcher import SemanticMatcher  # noqa: E402

# ── import build_prompt from test_qwen_inference.py (no copy, no modification)
spec = importlib.util.spec_from_file_location(
    "test_qwen_inference", ROOT / "test_qwen_inference.py"
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
build_prompt = mod.build_prompt


# ── helpers ───────────────────────────────────────────────────────────────────
def call_ollama(prompt: str) -> tuple[str, float]:
    """POST to Ollama and return (raw_response_text, elapsed_seconds)."""
    payload = json.dumps(
        {"model": "qwen2.5:3b", "prompt": prompt, "stream": False,
         "options": {"temperature": 0.0}}
    ).encode("utf-8")
    req = urllib.request.Request(
        "http://localhost:11434/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=120) as resp:
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
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return None


def gt_task_strings(gt: dict) -> list[str]:
    return [a.get("task", "") for a in gt.get("action_items", [])]


def gt_decision_strings(gt: dict) -> list[str]:
    decisions = gt.get("decisions", [])
    return [
        d.get("decision", d) if isinstance(d, dict) else d
        for d in decisions
    ]


def gt_issue_strings(gt: dict) -> list[str]:
    issues = gt.get("unresolved_issues", [])
    return [
        i.get("issue", i) if isinstance(i, dict) else i
        for i in issues
    ]


def pred_task_strings(pred: dict) -> list[str]:
    return [a.get("task", "") for a in pred.get("action_items", [])]


def _flatten_string_or_list(item) -> str:
    """Recursively flatten nested lists/dicts to a single string."""
    if isinstance(item, str):
        return item
    if isinstance(item, list):
        return " ".join(_flatten_string_or_list(x) for x in item)
    if isinstance(item, dict):
        return item.get("decision", item.get("issue", item.get("task", str(item))))
    return str(item)


def pred_decision_strings(pred: dict) -> list[str]:
    items = pred.get("decisions", [])
    return [_flatten_string_or_list(d) for d in items]


def pred_issue_strings(pred: dict) -> list[str]:
    items = pred.get("unresolved_issues", [])
    return [_flatten_string_or_list(i) for i in items]


# Lexical Jaccard (same implementation as evaluation_service.py)
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
        owner = item.get("owner")
        deadline = item.get("deadline")
        if owner and owner.lower() not in tl:
            hallucinated_owners.append(owner)
        if deadline and deadline.lower() not in tl:
            hallucinated_deadlines.append(deadline)
    return {"owners": hallucinated_owners, "deadlines": hallucinated_deadlines}


# ── main loop ─────────────────────────────────────────────────────────────────
results = []

for meeting_id in MEETINGS:
    print(f"\n{'=' * 60}")
    print(f"  {meeting_id}")
    print(f"{'=' * 60}")

    transcript_path = TRANSCRIPTS / f"{meeting_id}.txt"
    gt_path = GROUND_TRUTH / f"{meeting_id}.json"

    transcript = transcript_path.read_text(encoding="utf-8")
    with gt_path.open(encoding="utf-8") as f:
        ground_truth = json.load(f)

    prompt = build_prompt(transcript)

    try:
        raw_output, elapsed = call_ollama(prompt)
    except Exception as exc:
        print(f"  ❌ Ollama API error: {exc}")
        results.append({
            "meeting_id": meeting_id,
            "parse_ok": False,
            "error": str(exc),
            "elapsed_s": None,
        })
        continue

    print(f"  Inference time: {elapsed:.1f}s")
    parsed = parse_json_output(raw_output)

    if parsed is None:
        print(f"  ❌ JSON parse FAILED")
        print(f"  Raw output preview: {raw_output[:300]}")
        results.append({
            "meeting_id": meeting_id,
            "parse_ok": False,
            "error": "JSON parse failed",
            "raw_preview": raw_output[:300],
            "elapsed_s": round(elapsed, 2),
        })
        continue

    print(f"  ✅ JSON parsed OK")

    # Extract strings
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

    # Hallucination detection
    hall = detect_hallucinations(parsed, transcript)

    rec = {
        "meeting_id": meeting_id,
        "parse_ok": True,
        "elapsed_s": round(elapsed, 2),
        "has_summary": bool(parsed.get("summary", "").strip()),
        "n_pred_tasks": len(pred_tasks),
        "n_gt_tasks": len(gt_tasks),
        "n_pred_decs": len(pred_decs),
        "n_gt_decs": len(gt_decs),
        "n_pred_issues": len(pred_issues),
        "n_gt_issues": len(gt_issues),
        # lexical
        "lex_ai_matches": lex_ai,
        "lex_ai_p": lex_ai_prf[0], "lex_ai_r": lex_ai_prf[1], "lex_ai_f1": lex_ai_prf[2],
        "lex_dec_matches": lex_dec,
        "lex_dec_p": lex_dec_prf[0], "lex_dec_r": lex_dec_prf[1], "lex_dec_f1": lex_dec_prf[2],
        "lex_iss_matches": lex_iss,
        "lex_iss_p": lex_iss_prf[0], "lex_iss_r": lex_iss_prf[1], "lex_iss_f1": lex_iss_prf[2],
        # semantic
        "sem_ai_matches": sem_ai,
        "sem_ai_p": sem_ai_prf[0], "sem_ai_r": sem_ai_prf[1], "sem_ai_f1": sem_ai_prf[2],
        "sem_dec_matches": sem_dec,
        "sem_dec_p": sem_dec_prf[0], "sem_dec_r": sem_dec_prf[1], "sem_dec_f1": sem_dec_prf[2],
        "sem_iss_matches": sem_iss,
        "sem_iss_p": sem_iss_prf[0], "sem_iss_r": sem_iss_prf[1], "sem_iss_f1": sem_iss_prf[2],
        # hallucinations
        "hallucinated_owners": hall["owners"],
        "hallucinated_deadlines": hall["deadlines"],
        # raw for inspection
        "pred_tasks": pred_tasks,
        "pred_decs": pred_decs,
        "pred_issues": pred_issues,
        "gt_tasks": gt_tasks,
        "gt_decs": gt_decs,
        "gt_issues": gt_issues,
    }
    results.append(rec)

    print(f"  Action items  : pred={len(pred_tasks)}  gt={len(gt_tasks)}  lex_F1={lex_ai_prf[2]:.4f}  sem_F1={sem_ai_prf[2]:.4f}")
    print(f"  Decisions     : pred={len(pred_decs)}   gt={len(gt_decs)}   lex_F1={lex_dec_prf[2]:.4f}  sem_F1={sem_dec_prf[2]:.4f}")
    print(f"  Unres. issues : pred={len(pred_issues)} gt={len(gt_issues)}  lex_F1={lex_iss_prf[2]:.4f}  sem_F1={sem_iss_prf[2]:.4f}")
    if hall["owners"] or hall["deadlines"]:
        print(f"  ⚠️  Hallucinations — owners:{hall['owners']}  deadlines:{hall['deadlines']}")


# ── aggregate ─────────────────────────────────────────────────────────────────
ok = [r for r in results if r.get("parse_ok")]
failed = [r for r in results if not r.get("parse_ok")]

def _avg(vals):
    return round(sum(vals) / len(vals), 4) if vals else 0.0

agg = {}
for metric in ("lex_ai_f1", "lex_dec_f1", "lex_iss_f1",
               "sem_ai_f1", "sem_dec_f1", "sem_iss_f1",
               "lex_ai_p", "lex_ai_r", "lex_dec_p", "lex_dec_r",
               "lex_iss_p", "lex_iss_r",
               "sem_ai_p", "sem_ai_r", "sem_dec_p", "sem_dec_r",
               "sem_iss_p", "sem_iss_r"):
    agg[metric] = _avg([r[metric] for r in ok])

total_gt_ai  = sum(r["n_gt_tasks"] for r in ok)
total_pred_ai= sum(r["n_pred_tasks"] for r in ok)
total_lex_ai = sum(r["lex_ai_matches"] for r in ok)
total_sem_ai = sum(r["sem_ai_matches"] for r in ok)

total_gt_dec  = sum(r["n_gt_decs"] for r in ok)
total_pred_dec= sum(r["n_pred_decs"] for r in ok)
total_lex_dec = sum(r["lex_dec_matches"] for r in ok)
total_sem_dec = sum(r["sem_dec_matches"] for r in ok)

total_gt_iss  = sum(r["n_gt_issues"] for r in ok)
total_pred_iss= sum(r["n_pred_issues"] for r in ok)
total_lex_iss = sum(r["lex_iss_matches"] for r in ok)
total_sem_iss = sum(r["sem_iss_matches"] for r in ok)

# macro F1 averages + micro PRF
macro = {
    "lex_ai_f1_macro":  agg["lex_ai_f1"],
    "sem_ai_f1_macro":  agg["sem_ai_f1"],
    "lex_dec_f1_macro": agg["lex_dec_f1"],
    "sem_dec_f1_macro": agg["sem_dec_f1"],
    "lex_iss_f1_macro": agg["lex_iss_f1"],
    "sem_iss_f1_macro": agg["sem_iss_f1"],
    "micro_lex_ai":  prf(total_lex_ai, total_pred_ai, total_gt_ai),
    "micro_sem_ai":  prf(total_sem_ai, total_pred_ai, total_gt_ai),
    "micro_lex_dec": prf(total_lex_dec, total_pred_dec, total_gt_dec),
    "micro_sem_dec": prf(total_sem_dec, total_pred_dec, total_gt_dec),
    "micro_lex_iss": prf(total_lex_iss, total_pred_iss, total_gt_iss),
    "micro_sem_iss": prf(total_sem_iss, total_pred_iss, total_gt_iss),
}

# hallucination summary
all_hall_owners = [o for r in ok for o in r["hallucinated_owners"]]
all_hall_dl = [d for r in ok for d in r["hallucinated_deadlines"]]

# timing
times = [r["elapsed_s"] for r in ok]

# ── save raw results for the report
output_path = ROOT / "qwen_eval_SC001_SC010_raw.json"
with output_path.open("w", encoding="utf-8") as f:
    json.dump({"per_meeting": results, "aggregate": macro}, f, indent=2, default=str)
print(f"\nRaw results saved → {output_path}")


# ── final printout ─────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("  AGGREGATE RESULTS  (SC001–SC010)")
print("=" * 70)
print(f"  Parse successes : {len(ok)} / {len(results)}")
print(f"  Parse failures  : {len(failed)}")
print(f"  Summary present : {sum(r.get('has_summary',False) for r in ok)} / {len(ok)}")
print(f"  Total inference : {sum(times):.1f}s  |  avg per meeting: {sum(times)/len(times):.1f}s" if times else "  No timing data.")
print()
print("  ACTION ITEMS:")
print(f"    Lex  macro-F1={agg['lex_ai_f1']:.4f}  P={agg['lex_ai_p']:.4f}  R={agg['lex_ai_r']:.4f}")
print(f"    Sem  macro-F1={agg['sem_ai_f1']:.4f}  P={agg['sem_ai_p']:.4f}  R={agg['sem_ai_r']:.4f}")
print(f"    Lex  micro  P={macro['micro_lex_ai'][0]:.4f}  R={macro['micro_lex_ai'][1]:.4f}  F1={macro['micro_lex_ai'][2]:.4f}  ({total_lex_ai}/{total_gt_ai})")
print(f"    Sem  micro  P={macro['micro_sem_ai'][0]:.4f}  R={macro['micro_sem_ai'][1]:.4f}  F1={macro['micro_sem_ai'][2]:.4f}  ({total_sem_ai}/{total_gt_ai})")
print()
print("  DECISIONS:")
print(f"    Lex  macro-F1={agg['lex_dec_f1']:.4f}  P={agg['lex_dec_p']:.4f}  R={agg['lex_dec_r']:.4f}")
print(f"    Sem  macro-F1={agg['sem_dec_f1']:.4f}  P={agg['sem_dec_p']:.4f}  R={agg['sem_dec_r']:.4f}")
print(f"    Lex  micro  P={macro['micro_lex_dec'][0]:.4f}  R={macro['micro_lex_dec'][1]:.4f}  F1={macro['micro_lex_dec'][2]:.4f}  ({total_lex_dec}/{total_gt_dec})")
print(f"    Sem  micro  P={macro['micro_sem_dec'][0]:.4f}  R={macro['micro_sem_dec'][1]:.4f}  F1={macro['micro_sem_dec'][2]:.4f}  ({total_sem_dec}/{total_gt_dec})")
print()
print("  UNRESOLVED ISSUES:")
print(f"    Lex  macro-F1={agg['lex_iss_f1']:.4f}  P={agg['lex_iss_p']:.4f}  R={agg['lex_iss_r']:.4f}")
print(f"    Sem  macro-F1={agg['sem_iss_f1']:.4f}  P={agg['sem_iss_p']:.4f}  R={agg['sem_iss_r']:.4f}")
print(f"    Lex  micro  P={macro['micro_lex_iss'][0]:.4f}  R={macro['micro_lex_iss'][1]:.4f}  F1={macro['micro_lex_iss'][2]:.4f}  ({total_lex_iss}/{total_gt_iss})")
print(f"    Sem  micro  P={macro['micro_sem_iss'][0]:.4f}  R={macro['micro_sem_iss'][1]:.4f}  F1={macro['micro_sem_iss'][2]:.4f}  ({total_sem_iss}/{total_gt_iss})")
print()
print(f"  Hallucinated owners   : {len(all_hall_owners)}  — {all_hall_owners}")
print(f"  Hallucinated deadlines: {len(all_hall_dl)}  — {all_hall_dl}")
