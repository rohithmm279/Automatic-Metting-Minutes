"""Gemini Benchmark -- SC001 through SC010.

Equivalent to eval_qwen_SC001_SC010.py, using:
  - Identical 10-rule prompt (build_prompt from test_qwen_inference.py)
  - Identical transcript files and ground-truth files (SC001-SC010)
  - Identical evaluator: SemanticMatcher + lexical token-Jaccard (threshold >= 0.5)
  - Identical metrics: Precision / Recall / F1 (macro + micro) for
    action items, decisions, unresolved issues
  - Identical hallucination detection (owners + deadlines)

Key differences vs Qwen script:
  - API backend: google-genai (Gemini) instead of Ollama
  - Model: configurable via GEMINI_MODEL env var (default: gemini-3.6-flash)
  - Output saved to results/gemini/ (never overwrites Qwen results)
  - Raw Gemini response AND parsed structured output saved per meeting
  - Token usage recorded per meeting

Error handling:
  - Missing API key       -> prints error, exits cleanly
  - 429 / 503 transient  -> exponential backoff (up to 5 retries)
  - Malformed JSON        -> logs raw preview, continues to next meeting
  - Empty response        -> logs warning, continues to next meeting
  - Any other API error   -> logs and continues (single failure != abort)
"""

import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import importlib.util
import json
import os
import re
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
ROOT         = Path(r"r:\S5 mini datasets")
BACKEND      = ROOT / "backend"
TRANSCRIPTS  = ROOT / "datasets" / "01_PRIMARY" / "student_club" / "transcripts"
GROUND_TRUTH = ROOT / "datasets" / "01_PRIMARY" / "student_club" / "ground_truth"
RESULTS_DIR  = ROOT / "results" / "gemini"
MEETINGS     = [f"SC{i:03d}" for i in range(1, 11)]

RESULTS_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_JSON = RESULTS_DIR / "SC001_SC010_results.json"
RESULTS_TXT  = RESULTS_DIR / "SC001_SC010_report.txt"

for _p in (ROOT, BACKEND):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

# ---------------------------------------------------------------------------
# Load .env
# ---------------------------------------------------------------------------
try:
    from dotenv import load_dotenv
    load_dotenv(BACKEND / ".env")
    load_dotenv(ROOT / ".env")
except ImportError:
    pass  # environment variable fallback

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    print("ERROR: GEMINI_API_KEY not set in backend/.env or environment.", file=sys.stderr)
    sys.exit(1)

# ---------------------------------------------------------------------------
# google-genai SDK
# ---------------------------------------------------------------------------
try:
    from google import genai
    from google.genai import types as genai_types
except ImportError as _exc:
    print(f"ERROR: google-genai not installed. Run: pip install google-genai\n{_exc}",
          file=sys.stderr)
    sys.exit(1)

# ---------------------------------------------------------------------------
# Import the IDENTICAL prompt used by the Qwen benchmark.
# We dynamically load test_qwen_inference.py so the prompt is never
# duplicated or modified -- Gemini receives exactly the same 10-rule prompt.
# ---------------------------------------------------------------------------
_spec = importlib.util.spec_from_file_location(
    "test_qwen_inference", ROOT / "test_qwen_inference.py"
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
build_prompt = _mod.build_prompt       # canonical 10-rule prompt

# ---------------------------------------------------------------------------
# SemanticMatcher (identical to eval_qwen_SC001_SC010.py)
# ---------------------------------------------------------------------------
try:
    from backend.app.services.semantic_matcher import SemanticMatcher
except ImportError:
    from app.services.semantic_matcher import SemanticMatcher

# ---------------------------------------------------------------------------
# Gemini model & client
# ---------------------------------------------------------------------------
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
_client = genai.Client(api_key=GEMINI_API_KEY)


def call_gemini(prompt: str, max_retries: int = 5) -> tuple:
    """Send prompt to Gemini; return (raw_text, elapsed_s, token_usage).

    Retries up to max_retries times on 429/503 transient errors with
    exponential backoff.  Raises on permanent errors.
    """
    config = genai_types.GenerateContentConfig(temperature=0.0)
    last_err = None
    for attempt in range(1, max_retries + 1):
        t0 = time.perf_counter()
        try:
            resp = _client.models.generate_content(
                model=GEMINI_MODEL, contents=prompt, config=config
            )
            elapsed = time.perf_counter() - t0
            token_usage = {}
            if hasattr(resp, "usage_metadata") and resp.usage_metadata:
                token_usage = {
                    "prompt_tokens":     getattr(resp.usage_metadata, "prompt_token_count",     None),
                    "candidates_tokens": getattr(resp.usage_metadata, "candidates_token_count", None),
                    "total_tokens":      getattr(resp.usage_metadata, "total_token_count",      None),
                }
            return resp.text or "", elapsed, token_usage
        except Exception as exc:
            last_err = exc
            err_msg  = str(exc)
            is_transient = any(
                t in err_msg for t in ("429", "RESOURCE_EXHAUSTED", "503", "UNAVAILABLE")
            )
            if is_transient and attempt < max_retries:
                wait = 2 ** attempt
                print(f"    [Retry {attempt}/{max_retries}] {err_msg[:80]}... waiting {wait}s")
                time.sleep(wait)
            else:
                raise
    raise last_err or RuntimeError("Max retries exceeded")


# ---------------------------------------------------------------------------
# Parsing helpers (identical logic to eval_qwen_SC001_SC010.py)
# ---------------------------------------------------------------------------
def parse_json_output(raw: str):
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1]
        if cleaned.endswith("```"):
            cleaned = cleaned.rsplit("```", 1)[0]
        cleaned = cleaned.strip()
    try:
        data = json.loads(cleaned)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None


def gt_task_strings(gt):
    return [a.get("task", "") for a in gt.get("action_items", [])]

def gt_decision_strings(gt):
    decisions = gt.get("decisions", [])
    return [d.get("decision", d) if isinstance(d, dict) else d for d in decisions]

def gt_issue_strings(gt):
    issues = gt.get("unresolved_issues", [])
    return [i.get("issue", i) if isinstance(i, dict) else i for i in issues]

def pred_task_strings(pred):
    return [a.get("task", "") for a in pred.get("action_items", [])]

def _flatten(item):
    if isinstance(item, str):
        return item
    if isinstance(item, list):
        return " ".join(_flatten(x) for x in item)
    if isinstance(item, dict):
        return item.get("decision", item.get("issue", item.get("task", str(item))))
    return str(item)

def pred_decision_strings(pred):
    return [_flatten(d) for d in pred.get("decisions", [])]

def pred_issue_strings(pred):
    return [_flatten(i) for i in pred.get("unresolved_issues", [])]


# ---------------------------------------------------------------------------
# Lexical Jaccard (identical to eval_qwen_SC001_SC010.py)
# ---------------------------------------------------------------------------
def _token_jaccard(a: str, b: str) -> float:
    ta = set(re.findall(r"\w+", a.lower()))
    tb = set(re.findall(r"\w+", b.lower()))
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def greedy_lexical_matches(preds, refs, threshold=0.5) -> int:
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


def prf(matches, n_pred, n_ref):
    p = matches / n_pred if n_pred else 0.0
    r = matches / n_ref  if n_ref  else 0.0
    f = 2 * p * r / (p + r) if (p + r) else 0.0
    return round(p, 4), round(r, 4), round(f, 4)


# ---------------------------------------------------------------------------
# Hallucination detection (identical to eval_qwen_SC001_SC010.py)
# ---------------------------------------------------------------------------
def detect_hallucinations(pred, transcript):
    hall_owners, hall_dl = [], []
    tl = transcript.lower()
    for item in pred.get("action_items", []):
        owner    = item.get("owner")
        deadline = item.get("deadline")
        if owner    and owner.lower()    not in tl: hall_owners.append(owner)
        if deadline and deadline.lower() not in tl: hall_dl.append(deadline)
    return {"owners": hall_owners, "deadlines": hall_dl}


# ---------------------------------------------------------------------------
# Main benchmark loop
# ---------------------------------------------------------------------------
print(f"\n{chr(61)*70}")
print(f"  GEMINI BENCHMARK  (SC001-SC010)  model={GEMINI_MODEL}")
print(f"{chr(61)*70}")

results = []

for meeting_id in MEETINGS:
    print(f"\n{chr(61)*60}\n  {meeting_id}\n{chr(61)*60}")

    transcript_path = TRANSCRIPTS / f"{meeting_id}.txt"
    gt_path         = GROUND_TRUTH / f"{meeting_id}.json"

    if not transcript_path.exists():
        print(f"  SKIP: transcript not found: {transcript_path}")
        results.append({"meeting_id": meeting_id, "model": GEMINI_MODEL, "parse_ok": False,
                        "error": f"Transcript not found: {transcript_path}", "elapsed_s": None})
        continue
    if not gt_path.exists():
        print(f"  SKIP: ground-truth not found: {gt_path}")
        results.append({"meeting_id": meeting_id, "model": GEMINI_MODEL, "parse_ok": False,
                        "error": f"Ground-truth not found: {gt_path}", "elapsed_s": None})
        continue

    transcript   = transcript_path.read_text(encoding="utf-8")
    ground_truth = json.loads(gt_path.read_text(encoding="utf-8"))

    # IDENTICAL prompt to Qwen benchmark
    prompt = build_prompt(transcript)

    raw_output, elapsed, token_usage = "", 0.0, {}
    try:
        raw_output, elapsed, token_usage = call_gemini(prompt)
    except Exception as exc:
        print(f"  GEMINI API ERROR: {exc}")
        results.append({
            "meeting_id": meeting_id, "model": GEMINI_MODEL, "parse_ok": False,
            "error": str(exc), "raw_response": "", "elapsed_s": None, "token_usage": {},
        })
        continue

    print(f"  Gemini latency : {elapsed:.2f}s")
    if token_usage:
        print(
            f"  Token usage    : "
            f"prompt={token_usage.get('prompt_tokens')}  "
            f"candidates={token_usage.get('candidates_tokens')}  "
            f"total={token_usage.get('total_tokens')}"
        )

    if not raw_output.strip():
        print("  EMPTY RESPONSE from Gemini")
        results.append({
            "meeting_id": meeting_id, "model": GEMINI_MODEL, "parse_ok": False,
            "error": "Empty response from Gemini", "raw_response": "",
            "elapsed_s": round(elapsed, 2), "token_usage": token_usage,
        })
        continue

    parsed = parse_json_output(raw_output)
    if parsed is None:
        print("  JSON parse FAILED")
        print(f"  Raw preview: {raw_output[:300]}")
        results.append({
            "meeting_id": meeting_id, "model": GEMINI_MODEL, "parse_ok": False,
            "error": "JSON parse failed", "raw_response": raw_output,
            "raw_preview": raw_output[:300], "elapsed_s": round(elapsed, 2),
            "token_usage": token_usage,
        })
        continue

    print("  JSON parsed OK")

    gt_tasks  = gt_task_strings(ground_truth)
    gt_decs   = gt_decision_strings(ground_truth)
    gt_issues = gt_issue_strings(ground_truth)

    pred_tasks  = pred_task_strings(parsed)
    pred_decs   = pred_decision_strings(parsed)
    pred_issues = pred_issue_strings(parsed)

    lex_ai  = greedy_lexical_matches(pred_tasks,  gt_tasks)
    lex_dec = greedy_lexical_matches(pred_decs,   gt_decs)
    lex_iss = greedy_lexical_matches(pred_issues, gt_issues)

    lex_ai_prf  = prf(lex_ai,  len(pred_tasks),  len(gt_tasks))
    lex_dec_prf = prf(lex_dec, len(pred_decs),   len(gt_decs))
    lex_iss_prf = prf(lex_iss, len(pred_issues), len(gt_issues))

    sem_ai  = SemanticMatcher.count_semantic_matches(pred_tasks,  gt_tasks,  "action_items")
    sem_dec = SemanticMatcher.count_semantic_matches(pred_decs,   gt_decs,   "decisions")
    sem_iss = SemanticMatcher.count_semantic_matches(pred_issues, gt_issues, "unresolved_issues")

    sem_ai_prf  = prf(sem_ai,  len(pred_tasks),  len(gt_tasks))
    sem_dec_prf = prf(sem_dec, len(pred_decs),   len(gt_decs))
    sem_iss_prf = prf(sem_iss, len(pred_issues), len(gt_issues))

    hall = detect_hallucinations(parsed, transcript)

    rec = {
        "meeting_id": meeting_id, "model": GEMINI_MODEL, "parse_ok": True,
        "elapsed_s":   round(elapsed, 2), "token_usage": token_usage,
        "has_summary": bool(parsed.get("summary", "").strip()),
        "n_pred_tasks": len(pred_tasks),  "n_gt_tasks": len(gt_tasks),
        "n_pred_decs":  len(pred_decs),   "n_gt_decs":  len(gt_decs),
        "n_pred_issues":len(pred_issues), "n_gt_issues":len(gt_issues),
        "lex_ai_matches":  lex_ai,  "lex_ai_p":  lex_ai_prf[0],  "lex_ai_r":  lex_ai_prf[1],  "lex_ai_f1":  lex_ai_prf[2],
        "lex_dec_matches": lex_dec, "lex_dec_p": lex_dec_prf[0], "lex_dec_r": lex_dec_prf[1], "lex_dec_f1": lex_dec_prf[2],
        "lex_iss_matches": lex_iss, "lex_iss_p": lex_iss_prf[0], "lex_iss_r": lex_iss_prf[1], "lex_iss_f1": lex_iss_prf[2],
        "sem_ai_matches":  sem_ai,  "sem_ai_p":  sem_ai_prf[0],  "sem_ai_r":  sem_ai_prf[1],  "sem_ai_f1":  sem_ai_prf[2],
        "sem_dec_matches": sem_dec, "sem_dec_p": sem_dec_prf[0], "sem_dec_r": sem_dec_prf[1], "sem_dec_f1": sem_dec_prf[2],
        "sem_iss_matches": sem_iss, "sem_iss_p": sem_iss_prf[0], "sem_iss_r": sem_iss_prf[1], "sem_iss_f1": sem_iss_prf[2],
        "hallucinated_owners":   hall["owners"],
        "hallucinated_deadlines":hall["deadlines"],
        "pred_tasks":  pred_tasks, "pred_decs":  pred_decs,  "pred_issues":  pred_issues,
        "gt_tasks":    gt_tasks,   "gt_decs":    gt_decs,    "gt_issues":    gt_issues,
        "raw_response":            raw_output,
        "parsed_summary":          parsed.get("summary", ""),
        "parsed_action_items":     parsed.get("action_items", []),
        "parsed_decisions":        parsed.get("decisions", []),
        "parsed_unresolved_issues":parsed.get("unresolved_issues", []),
    }
    results.append(rec)

    print(f"  Action items  : pred={len(pred_tasks)}  gt={len(gt_tasks)}  lex_F1={lex_ai_prf[2]:.4f}  sem_F1={sem_ai_prf[2]:.4f}")
    print(f"  Decisions     : pred={len(pred_decs)}   gt={len(gt_decs)}   lex_F1={lex_dec_prf[2]:.4f}  sem_F1={sem_dec_prf[2]:.4f}")
    print(f"  Unres. issues : pred={len(pred_issues)} gt={len(gt_issues)}  lex_F1={lex_iss_prf[2]:.4f}  sem_F1={sem_iss_prf[2]:.4f}")
    if hall["owners"] or hall["deadlines"]:
        print(f"  HALLUCINATIONS : owners={hall['owners']}  deadlines={hall['deadlines']}")

    time.sleep(1)


# ---------------------------------------------------------------------------
# Aggregate
# ---------------------------------------------------------------------------
ok     = [r for r in results if r.get("parse_ok")]
failed = [r for r in results if not r.get("parse_ok")]

def _avg(vals):
    return round(sum(vals) / len(vals), 4) if vals else 0.0

agg = {}
for m in ("lex_ai_f1","lex_dec_f1","lex_iss_f1","sem_ai_f1","sem_dec_f1","sem_iss_f1",
          "lex_ai_p","lex_ai_r","lex_dec_p","lex_dec_r","lex_iss_p","lex_iss_r",
          "sem_ai_p","sem_ai_r","sem_dec_p","sem_dec_r","sem_iss_p","sem_iss_r"):
    agg[m] = _avg([r[m] for r in ok])

total_gt_ai   = sum(r["n_gt_tasks"]    for r in ok)
total_pred_ai = sum(r["n_pred_tasks"]  for r in ok)
total_lex_ai  = sum(r["lex_ai_matches"] for r in ok)
total_sem_ai  = sum(r["sem_ai_matches"] for r in ok)

total_gt_dec   = sum(r["n_gt_decs"]      for r in ok)
total_pred_dec = sum(r["n_pred_decs"]    for r in ok)
total_lex_dec  = sum(r["lex_dec_matches"] for r in ok)
total_sem_dec  = sum(r["sem_dec_matches"] for r in ok)

total_gt_iss   = sum(r["n_gt_issues"]    for r in ok)
total_pred_iss = sum(r["n_pred_issues"]  for r in ok)
total_lex_iss  = sum(r["lex_iss_matches"] for r in ok)
total_sem_iss  = sum(r["sem_iss_matches"] for r in ok)

macro = {
    "lex_ai_f1_macro":  agg["lex_ai_f1"],  "sem_ai_f1_macro":  agg["sem_ai_f1"],
    "lex_dec_f1_macro": agg["lex_dec_f1"], "sem_dec_f1_macro": agg["sem_dec_f1"],
    "lex_iss_f1_macro": agg["lex_iss_f1"], "sem_iss_f1_macro": agg["sem_iss_f1"],
    "micro_lex_ai":  prf(total_lex_ai,  total_pred_ai,  total_gt_ai),
    "micro_sem_ai":  prf(total_sem_ai,  total_pred_ai,  total_gt_ai),
    "micro_lex_dec": prf(total_lex_dec, total_pred_dec, total_gt_dec),
    "micro_sem_dec": prf(total_sem_dec, total_pred_dec, total_gt_dec),
    "micro_lex_iss": prf(total_lex_iss, total_pred_iss, total_gt_iss),
    "micro_sem_iss": prf(total_sem_iss, total_pred_iss, total_gt_iss),
}

all_hall_owners = [o for r in ok for o in r["hallucinated_owners"]]
all_hall_dl     = [d for r in ok for d in r["hallucinated_deadlines"]]
times = [r["elapsed_s"] for r in ok if r.get("elapsed_s") is not None]

aggregate_section = {
    "model": GEMINI_MODEL,
    "benchmark_timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    "meetings_attempted": len(results), "meetings_succeeded": len(ok), "meetings_failed": len(failed),
    "json_validity_rate": round(len(ok)/len(results), 4) if results else 0.0,
    "summary_availability_rate": round(sum(r.get("has_summary", False) for r in ok)/len(ok), 4) if ok else 0.0,
    "total_latency_s": round(sum(times), 2),
    "avg_latency_s":   round(sum(times)/len(times), 2) if times else 0.0,
    "hallucinated_owners_total":    len(all_hall_owners),
    "hallucinated_deadlines_total": len(all_hall_dl),
    "action_items": {
        "macro_lex": {"precision": agg["lex_ai_p"], "recall": agg["lex_ai_r"], "f1": agg["lex_ai_f1"]},
        "macro_sem": {"precision": agg["sem_ai_p"], "recall": agg["sem_ai_r"], "f1": agg["sem_ai_f1"]},
        "micro_lex": {"precision": macro["micro_lex_ai"][0], "recall": macro["micro_lex_ai"][1],
                      "f1": macro["micro_lex_ai"][2], "matches": total_lex_ai,
                      "gt_total": total_gt_ai, "pred_total": total_pred_ai},
        "micro_sem": {"precision": macro["micro_sem_ai"][0], "recall": macro["micro_sem_ai"][1],
                      "f1": macro["micro_sem_ai"][2], "matches": total_sem_ai,
                      "gt_total": total_gt_ai, "pred_total": total_pred_ai},
    },
    "decisions": {
        "macro_lex": {"precision": agg["lex_dec_p"], "recall": agg["lex_dec_r"], "f1": agg["lex_dec_f1"]},
        "macro_sem": {"precision": agg["sem_dec_p"], "recall": agg["sem_dec_r"], "f1": agg["sem_dec_f1"]},
        "micro_lex": {"precision": macro["micro_lex_dec"][0], "recall": macro["micro_lex_dec"][1],
                      "f1": macro["micro_lex_dec"][2], "matches": total_lex_dec,
                      "gt_total": total_gt_dec, "pred_total": total_pred_dec},
        "micro_sem": {"precision": macro["micro_sem_dec"][0], "recall": macro["micro_sem_dec"][1],
                      "f1": macro["micro_sem_dec"][2], "matches": total_sem_dec,
                      "gt_total": total_gt_dec, "pred_total": total_pred_dec},
    },
    "unresolved_issues": {
        "macro_lex": {"precision": agg["lex_iss_p"], "recall": agg["lex_iss_r"], "f1": agg["lex_iss_f1"]},
        "macro_sem": {"precision": agg["sem_iss_p"], "recall": agg["sem_iss_r"], "f1": agg["sem_iss_f1"]},
        "micro_lex": {"precision": macro["micro_lex_iss"][0], "recall": macro["micro_lex_iss"][1],
                      "f1": macro["micro_lex_iss"][2], "matches": total_lex_iss,
                      "gt_total": total_gt_iss, "pred_total": total_pred_iss},
        "micro_sem": {"precision": macro["micro_sem_iss"][0], "recall": macro["micro_sem_iss"][1],
                      "f1": macro["micro_sem_iss"][2], "matches": total_sem_iss,
                      "gt_total": total_gt_iss, "pred_total": total_pred_iss},
    },
    "note_owner_deadline_eval": (
        "Owner/deadline evaluation is not a standalone scoring metric. "
        "Hallucination detection (verbatim substring check) is applied instead: "
        "owners and deadlines not found verbatim in the transcript are flagged."
    ),
}

with RESULTS_JSON.open("w", encoding="utf-8") as f:
    json.dump({"per_meeting": results, "aggregate": aggregate_section}, f, indent=2, default=str)
print(f"\nJSON results saved -> {RESULTS_JSON}")

# ---------------------------------------------------------------------------
# Human-readable report
# ---------------------------------------------------------------------------
lines = []
lines.append("=" * 75)
lines.append(f"  GEMINI BENCHMARK REPORT  (SC001-SC010)  model={GEMINI_MODEL}")
lines.append("=" * 75)
lines.append(f"  Benchmark timestamp : {aggregate_section['benchmark_timestamp']}")
lines.append(f"  Meetings attempted  : {len(results)}")
lines.append(f"  Succeeded           : {len(ok)}")
lines.append(f"  Failed              : {len(failed)}")
lines.append(f"  JSON validity rate  : {aggregate_section['json_validity_rate']*100:.1f}%")
lines.append(f"  Summary availability: {aggregate_section['summary_availability_rate']*100:.1f}%")
lines.append(f"  Total latency       : {aggregate_section['total_latency_s']:.1f}s")
lines.append(f"  Avg latency/meeting : {aggregate_section['avg_latency_s']:.2f}s")
lines.append(f"  Hallucinated owners : {len(all_hall_owners)}  {all_hall_owners}")
lines.append(f"  Hallucinated deadlines: {len(all_hall_dl)}  {all_hall_dl}")
lines.append("")
lines.append("  Per-meeting results:")
lines.append("  " + "-" * 100)
for r in results:
    mid = r["meeting_id"]
    if not r.get("parse_ok"):
        lines.append(f"  {mid:>8}  FAILED -- {r.get('error', 'unknown')[:60]}")
        continue
    lines.append(
        f"  {mid:>8}  {r['elapsed_s']:>6.2f}s  "
        f"AI:{r['n_pred_tasks']}/{r['n_gt_tasks']}  "
        f"AILex={r['lex_ai_f1']:.4f} AISem={r['sem_ai_f1']:.4f}  "
        f"Dec:{r['n_pred_decs']}/{r['n_gt_decs']}  "
        f"DecLex={r['lex_dec_f1']:.4f} DecSem={r['sem_dec_f1']:.4f}  "
        f"Iss:{r['n_pred_issues']}/{r['n_gt_issues']}  "
        f"IssLex={r['lex_iss_f1']:.4f} IssSem={r['sem_iss_f1']:.4f}"
    )
lines.append("")
for cat, label in [("action_items","ACTION ITEMS"),("decisions","DECISIONS"),("unresolved_issues","UNRESOLVED ISSUES")]:
    ai = aggregate_section[cat]
    lines.append(f"  AGGREGATE -- {label}:")
    lines.append(f"    Lex  macro-F1={ai['macro_lex']['f1']:.4f}  P={ai['macro_lex']['precision']:.4f}  R={ai['macro_lex']['recall']:.4f}")
    lines.append(f"    Sem  macro-F1={ai['macro_sem']['f1']:.4f}  P={ai['macro_sem']['precision']:.4f}  R={ai['macro_sem']['recall']:.4f}")
    lines.append(f"    Lex  micro   P={ai['micro_lex']['precision']:.4f}  R={ai['micro_lex']['recall']:.4f}  F1={ai['micro_lex']['f1']:.4f}  ({ai['micro_lex']['matches']}/{ai['micro_lex']['gt_total']})")
    lines.append(f"    Sem  micro   P={ai['micro_sem']['precision']:.4f}  R={ai['micro_sem']['recall']:.4f}  F1={ai['micro_sem']['f1']:.4f}  ({ai['micro_sem']['matches']}/{ai['micro_sem']['gt_total']})")
    lines.append("")
lines.append("  NOTE: Owner/deadline eval is not a standalone metric.")
lines.append("        Hallucination detection (verbatim substring check) is used instead.")
lines.append("=" * 75)

with RESULTS_TXT.open("w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print(f"Text report saved -> {RESULTS_TXT}")

# ---------------------------------------------------------------------------
# Final console printout (mirrors eval_qwen_SC001_SC010.py format)
# ---------------------------------------------------------------------------
SEP = "=" * 70
print(f"\n{SEP}")
print(f"  AGGREGATE RESULTS  (SC001-SC010)  model={GEMINI_MODEL}")
print(SEP)
print(f"  Parse successes : {len(ok)} / {len(results)}")
print(f"  Parse failures  : {len(failed)}")
print(f"  Summary present : {sum(r.get('has_summary', False) for r in ok)} / {len(ok)}")
if times:
    print(f"  Total latency   : {sum(times):.1f}s  |  avg per meeting: {sum(times)/len(times):.2f}s")
else:
    print("  No timing data.")
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
print(f"  Hallucinated owners    : {len(all_hall_owners)}  -- {all_hall_owners}")
print(f"  Hallucinated deadlines : {len(all_hall_dl)}  -- {all_hall_dl}")
print(SEP)
print(f"\n  Results dir -> {RESULTS_DIR}")
print(f"  JSON        -> {RESULTS_JSON}")
print(f"  Report      -> {RESULTS_TXT}")
