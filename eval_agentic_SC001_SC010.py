"""End-to-End Evaluation of the Agentic AI Pipeline on SC001 through SC010.

Features:
  - Per-meeting timeout (default: 60s) with concurrent.futures so no hanging call blocks execution
  - Real-time flushed console progress: [1/10] SC001 START ... [1/10] SC001 COMPLETE
  - Incremental Checkpointing to results/agentic/SC001_SC010_checkpoint.json after every meeting
  - Resume support: Skips already completed meetings from checkpoint
  - Saves final results to results/agentic/SC001_SC010_results.json and results/agentic/SC001_SC010_report.txt
  - Exact same Lexical Jaccard (threshold >= 0.5) and SemanticMatcher evaluation
"""

import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import concurrent.futures
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
ROOT         = Path(r"r:\S5 mini datasets")
BACKEND      = ROOT / "backend"
TRANSCRIPTS  = ROOT / "datasets" / "01_PRIMARY" / "student_club" / "transcripts"
GROUND_TRUTH = ROOT / "datasets" / "01_PRIMARY" / "student_club" / "ground_truth"
RESULTS_DIR  = ROOT / "results" / "agentic"
MEETINGS     = [f"SC{i:03d}" for i in range(1, 11)]
TIMEOUT_SEC  = 75  # per-meeting timeout limit

RESULTS_DIR.mkdir(parents=True, exist_ok=True)
CHECKPOINT_JSON = RESULTS_DIR / "SC001_SC010_checkpoint.json"
RESULTS_JSON    = RESULTS_DIR / "SC001_SC010_results.json"
RESULTS_TXT     = RESULTS_DIR / "SC001_SC010_report.txt"

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
    pass

# ---------------------------------------------------------------------------
# Imports from backend
# ---------------------------------------------------------------------------
try:
    from backend.app.agents.orchestrator import AgentOrchestrator
    from backend.app.services.semantic_matcher import SemanticMatcher
    from backend.app.schemas.meeting_schema import MeetingAnalysis
except ImportError:
    from app.agents.orchestrator import AgentOrchestrator
    from app.services.semantic_matcher import SemanticMatcher
    from app.schemas.meeting_schema import MeetingAnalysis


# ---------------------------------------------------------------------------
# Metric and Grounding Helpers (Identical to previous benchmarks)
# ---------------------------------------------------------------------------
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


def detect_hallucinations(pred, transcript):
    hall_owners, hall_dl = [], []
    tl = transcript.lower()
    for item in pred.get("action_items", []):
        owner    = item.get("owner")
        deadline = item.get("deadline")
        if owner and str(owner).strip().lower() not in ("not specified", "null", "none", "unassigned", ""):
            if str(owner).strip().lower() not in tl:
                hall_owners.append(str(owner))
        if deadline and str(deadline).strip().lower() not in ("not specified", "null", "none", "no deadline", ""):
            dl_words = [w for w in re.findall(r"\b[A-Za-z0-9]{3,}\b", str(deadline).lower())]
            if dl_words and not any(w in tl for w in dl_words):
                hall_dl.append(str(deadline))
    return {"owners": hall_owners, "deadlines": hall_dl}


def load_checkpoint() -> tuple[list[str], list[dict]]:
    if CHECKPOINT_JSON.exists():
        try:
            data = json.loads(CHECKPOINT_JSON.read_text(encoding="utf-8"))
            completed = data.get("completed_meetings", [])
            results = data.get("results", [])
            return completed, results
        except Exception:
            return [], []
    return [], []


def save_checkpoint(completed: list[str], results: list[dict]):
    payload = {
        "completed_meetings": completed,
        "results": results,
        "updated_at": datetime.now().isoformat(),
    }
    CHECKPOINT_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------------------
# Main Evaluation Loop
# ---------------------------------------------------------------------------
def run_agentic_evaluation():
    print(f"\n{chr(61)*70}", flush=True)
    print("  AGENTIC AI PIPELINE BENCHMARK (SC001-SC010)", flush=True)
    print(f"{chr(61)*70}", flush=True)

    completed_ids, results = load_checkpoint()
    if completed_ids:
        print(f"Resuming from checkpoint: {len(completed_ids)}/{len(MEETINGS)} completed.", flush=True)

    orchestrator = AgentOrchestrator()

    for idx, meeting_id in enumerate(MEETINGS, 1):
        if meeting_id in completed_ids:
            print(f"[{idx}/{len(MEETINGS)}] {meeting_id} ALREADY COMPLETED (skipping).", flush=True)
            continue

        print(f"\n[{idx}/{len(MEETINGS)}] {meeting_id} START", flush=True)

        transcript_path = TRANSCRIPTS / f"{meeting_id}.txt"
        gt_path         = GROUND_TRUTH / f"{meeting_id}.json"

        if not transcript_path.exists():
            print(f"  [{idx}/{len(MEETINGS)}] {meeting_id} FAILED: transcript not found", flush=True)
            rec = {"meeting_id": meeting_id, "parse_ok": False, "error": "Transcript not found", "elapsed_s": None}
            results.append(rec)
            completed_ids.append(meeting_id)
            save_checkpoint(completed_ids, results)
            continue
        if not gt_path.exists():
            print(f"  [{idx}/{len(MEETINGS)}] {meeting_id} FAILED: ground-truth not found", flush=True)
            rec = {"meeting_id": meeting_id, "parse_ok": False, "error": "Ground-truth not found", "elapsed_s": None}
            results.append(rec)
            completed_ids.append(meeting_id)
            save_checkpoint(completed_ids, results)
            continue

        transcript   = transcript_path.read_text(encoding="utf-8")
        ground_truth = json.loads(gt_path.read_text(encoding="utf-8"))

        t0 = time.perf_counter()
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        future = executor.submit(orchestrator.process_transcript, transcript)
        try:
            analysis, source, is_rl = future.result(timeout=TIMEOUT_SEC)
            elapsed = time.perf_counter() - t0
            executor.shutdown(wait=False)
        except concurrent.futures.TimeoutError:
            elapsed = time.perf_counter() - t0
            print(f"  [{idx}/{len(MEETINGS)}] {meeting_id} TIMEOUT ({TIMEOUT_SEC}s exceeded)", flush=True)
            executor.shutdown(wait=False)
            rec = {
                "meeting_id": meeting_id,
                "parse_ok": False,
                "error": f"TimeoutError: exceeded {TIMEOUT_SEC}s",
                "elapsed_s": round(elapsed, 2),
                "source": "TIMEOUT",
            }
            results.append(rec)
            completed_ids.append(meeting_id)
            save_checkpoint(completed_ids, results)
            continue
        except Exception as exc:
            elapsed = time.perf_counter() - t0
            print(f"  [{idx}/{len(MEETINGS)}] {meeting_id} ERROR: {exc}", flush=True)
            executor.shutdown(wait=False)
            rec = {
                "meeting_id": meeting_id,
                "parse_ok": False,
                "error": str(exc),
                "elapsed_s": round(elapsed, 2),
                "source": "ERROR",
            }
            results.append(rec)
            completed_ids.append(meeting_id)
            save_checkpoint(completed_ids, results)
            continue

        pred = analysis.model_dump()
        summary_text = pred.get("summary", "")

        # Ground truth extractions
        ref_tasks     = gt_task_strings(ground_truth)
        ref_decisions = gt_decision_strings(ground_truth)
        ref_issues    = gt_issue_strings(ground_truth)

        pred_tasks     = pred_task_strings(pred)
        pred_decisions = pred_decision_strings(pred)
        pred_issues    = pred_issue_strings(pred)

        # Lexical matching
        lex_ai_m  = greedy_lexical_matches(pred_tasks,     ref_tasks,     threshold=0.5)
        lex_dec_m = greedy_lexical_matches(pred_decisions, ref_decisions, threshold=0.5)
        lex_iss_m = greedy_lexical_matches(pred_issues,    ref_issues,    threshold=0.5)

        lex_ai_p,  lex_ai_r,  lex_ai_f  = prf(lex_ai_m,  len(pred_tasks),     len(ref_tasks))
        lex_dec_p, lex_dec_r, lex_dec_f = prf(lex_dec_m, len(pred_decisions), len(ref_decisions))
        lex_iss_p, lex_iss_r, lex_iss_f = prf(lex_iss_m, len(pred_issues),    len(ref_issues))

        # Semantic matching (using static count_semantic_matches)
        sem_ai_m  = SemanticMatcher.count_semantic_matches(pred_tasks,     ref_tasks,     "action_items")
        sem_dec_m = SemanticMatcher.count_semantic_matches(pred_decisions, ref_decisions, "decisions")
        sem_iss_m = SemanticMatcher.count_semantic_matches(pred_issues,    ref_issues,    "unresolved_issues")

        sem_ai_p,  sem_ai_r,  sem_ai_f  = prf(sem_ai_m,  len(pred_tasks),     len(ref_tasks))
        sem_dec_p, sem_dec_r, sem_dec_f = prf(sem_dec_m, len(pred_decisions), len(ref_decisions))
        sem_iss_p, sem_iss_r, sem_iss_f = prf(sem_iss_m, len(pred_issues),    len(ref_issues))

        hall = detect_hallucinations(pred, transcript)
        has_summary = bool(summary_text.strip())
        val_data = pred.get("validation", {}) or {}

        print(f"[{idx}/{len(MEETINGS)}] {meeting_id} COMPLETE", flush=True)
        print(f"  Source        : {source} (Rate-limited: {is_rl})", flush=True)
        print(f"  Latency       : {elapsed:.2f}s", flush=True)
        print(f"  Action items  : {len(pred_tasks)} (gt={len(ref_tasks)}, sem_F1={sem_ai_f:.4f})", flush=True)
        print(f"  Decisions     : {len(pred_decisions)} (gt={len(ref_decisions)}, sem_F1={sem_dec_f:.4f})", flush=True)
        print(f"  Unres. issues : {len(pred_issues)} (gt={len(ref_issues)}, sem_F1={sem_iss_f:.4f})", flush=True)
        print(f"  Summary       : {summary_text[:90]}...", flush=True)

        rec = {
            "meeting_id":    meeting_id,
            "source":        source,
            "rate_limited":  is_rl,
            "parse_ok":      True,
            "elapsed_s":     round(elapsed, 2),
            "has_summary":   has_summary,
            "validation":    val_data,
            "hallucinations": hall,
            "predictions":   pred,
            "metrics": {
                "action_items": {
                    "pred_count": len(pred_tasks), "ref_count": len(ref_tasks),
                    "lex_matches": lex_ai_m, "lex_p": lex_ai_p, "lex_r": lex_ai_r, "lex_f1": lex_ai_f,
                    "sem_matches": sem_ai_m, "sem_p": sem_ai_p, "sem_r": sem_ai_r, "sem_f1": sem_ai_f,
                },
                "decisions": {
                    "pred_count": len(pred_decisions), "ref_count": len(ref_decisions),
                    "lex_matches": lex_dec_m, "lex_p": lex_dec_p, "lex_r": lex_dec_r, "lex_f1": lex_dec_f,
                    "sem_matches": sem_dec_m, "sem_p": sem_dec_p, "sem_r": sem_dec_r, "sem_f1": sem_dec_f,
                },
                "unresolved_issues": {
                    "pred_count": len(pred_issues), "ref_count": len(ref_issues),
                    "lex_matches": lex_iss_m, "lex_p": lex_iss_p, "lex_r": lex_iss_r, "lex_f1": lex_iss_f,
                    "sem_matches": sem_iss_m, "sem_p": sem_iss_p, "sem_r": sem_iss_r, "sem_f1": sem_iss_f,
                },
            }
        }
        results.append(rec)
        completed_ids.append(meeting_id)
        save_checkpoint(completed_ids, results)

    # Save final structured outputs
    RESULTS_JSON.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n[OK] Final JSON saved to: {RESULTS_JSON}", flush=True)

    # Generate Aggregate Report
    generate_report(results)


def generate_report(results: list[dict]):
    succeeded = [r for r in results if r.get("parse_ok")]
    n_attempted = len(results)
    n_succeeded = len(succeeded)
    n_failed    = n_attempted - n_succeeded

    total_latency = sum(r["elapsed_s"] for r in succeeded if r.get("elapsed_s"))
    avg_latency   = total_latency / n_succeeded if n_succeeded else 0.0

    gemini_count   = sum(1 for r in succeeded if "GEMINI" in r.get("source", ""))
    fallback_count = sum(1 for r in succeeded if "FALLBACK" in r.get("source", ""))

    all_hall_owners = []
    all_hall_dl     = []
    for r in succeeded:
        all_hall_owners.extend(r.get("hallucinations", {}).get("owners", []))
        all_hall_dl.extend(r.get("hallucinations", {}).get("deadlines", []))

    summary_avail = sum(1 for r in succeeded if r.get("has_summary")) / n_succeeded if n_succeeded else 0.0

    def macro(cat, metric_key):
        vals = [r["metrics"][cat][metric_key] for r in succeeded if "metrics" in r]
        return sum(vals) / len(vals) if vals else 0.0

    def micro(cat, match_key):
        tot_m = sum(r["metrics"][cat][match_key] for r in succeeded if "metrics" in r)
        tot_p = sum(r["metrics"][cat]["pred_count"] for r in succeeded if "metrics" in r)
        tot_r = sum(r["metrics"][cat]["ref_count"] for r in succeeded if "metrics" in r)
        p, r_val, f = prf(tot_m, tot_p, tot_r)
        return p, r_val, f, tot_m, tot_r

    # Macro & Micro for actions
    ai_lex_macro_f = macro("action_items", "lex_f1")
    ai_lex_macro_p = macro("action_items", "lex_p")
    ai_lex_macro_r = macro("action_items", "lex_r")
    ai_sem_macro_f = macro("action_items", "sem_f1")
    ai_sem_macro_p = macro("action_items", "sem_p")
    ai_sem_macro_r = macro("action_items", "sem_r")
    ai_lex_mic_p, ai_lex_mic_r, ai_lex_mic_f, ai_lex_m, ai_tot_r = micro("action_items", "lex_matches")
    ai_sem_mic_p, ai_sem_mic_r, ai_sem_mic_f, ai_sem_m, _        = micro("action_items", "sem_matches")

    # Macro & Micro for decisions
    dec_lex_macro_f = macro("decisions", "lex_f1")
    dec_lex_macro_p = macro("decisions", "lex_p")
    dec_lex_macro_r = macro("decisions", "lex_r")
    dec_sem_macro_f = macro("decisions", "sem_f1")
    dec_sem_macro_p = macro("decisions", "sem_p")
    dec_sem_macro_r = macro("decisions", "sem_r")
    dec_lex_mic_p, dec_lex_mic_r, dec_lex_mic_f, dec_lex_m, dec_tot_r = micro("decisions", "lex_matches")
    dec_sem_mic_p, dec_sem_mic_r, dec_sem_mic_f, dec_sem_m, _         = micro("decisions", "sem_matches")

    # Macro & Micro for issues
    iss_lex_macro_f = macro("unresolved_issues", "lex_f1")
    iss_lex_macro_p = macro("unresolved_issues", "lex_p")
    iss_lex_macro_r = macro("unresolved_issues", "lex_r")
    iss_sem_macro_f = macro("unresolved_issues", "sem_f1")
    iss_sem_macro_p = macro("unresolved_issues", "sem_p")
    iss_sem_macro_r = macro("unresolved_issues", "sem_r")
    iss_lex_mic_p, iss_lex_mic_r, iss_lex_mic_f, iss_lex_m, iss_tot_r = micro("unresolved_issues", "lex_matches")
    iss_sem_mic_p, iss_sem_mic_r, iss_sem_mic_f, iss_sem_m, _         = micro("unresolved_issues", "sem_matches")

    lines = []
    lines.append("=" * 75)
    lines.append("  AGENTIC AI PIPELINE BENCHMARK REPORT  (SC001-SC010)")
    lines.append("=" * 75)
    lines.append(f"  Benchmark timestamp : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"  Meetings attempted  : {n_attempted}")
    lines.append(f"  Succeeded           : {n_succeeded}")
    lines.append(f"  Failed              : {n_failed}")
    lines.append(f"  Agentic Gemini used : {gemini_count}/{n_succeeded}")
    lines.append(f"  Fallback used       : {fallback_count}/{n_succeeded}")
    lines.append(f"  Summary availability: {summary_avail * 100:.1f}%")
    lines.append(f"  Total latency       : {total_latency:.1f}s")
    lines.append(f"  Avg latency/meeting : {avg_latency:.2f}s")
    lines.append(f"  Hallucinated owners : {len(all_hall_owners)}  {all_hall_owners}")
    lines.append(f"  Hallucinated dl     : {len(all_hall_dl)}  {all_hall_dl}")
    lines.append("")
    lines.append("  Per-meeting results:")
    lines.append("  " + "-" * 88)
    for r in succeeded:
        mid = r["meeting_id"]
        el  = f"{r['elapsed_s']:.2f}s" if r.get('elapsed_s') else "N/A"
        src = r.get("source", "UNKNOWN")
        m   = r["metrics"]
        ai_pred = m["action_items"]["pred_count"]
        ai_ref  = m["action_items"]["ref_count"]
        ai_sem_f = m["action_items"]["sem_f1"]
        dec_pred = m["decisions"]["pred_count"]
        dec_ref  = m["decisions"]["ref_count"]
        dec_sem_f = m["decisions"]["sem_f1"]
        iss_pred = m["unresolved_issues"]["pred_count"]
        iss_ref  = m["unresolved_issues"]["ref_count"]
        iss_sem_f = m["unresolved_issues"]["sem_f1"]

        lines.append(
            f"   {mid}  [{src:<19}] {el:>7} | "
            f"AI:{ai_pred}/{ai_ref} (SemF1={ai_sem_f:.2f}) | "
            f"Dec:{dec_pred}/{dec_ref} (SemF1={dec_sem_f:.2f}) | "
            f"Iss:{iss_pred}/{iss_ref} (SemF1={iss_sem_f:.2f})"
        )

    lines.append("")
    lines.append("  AGGREGATE -- ACTION ITEMS:")
    lines.append(f"    Lex  macro-F1={ai_lex_macro_f:.4f}  P={ai_lex_macro_p:.4f}  R={ai_lex_macro_r:.4f}")
    lines.append(f"    Sem  macro-F1={ai_sem_macro_f:.4f}  P={ai_sem_macro_p:.4f}  R={ai_sem_macro_r:.4f}")
    lines.append(f"    Lex  micro   P={ai_lex_mic_p:.4f}  R={ai_lex_mic_r:.4f}  F1={ai_lex_mic_f:.4f}  ({ai_lex_m}/{ai_tot_r})")
    lines.append(f"    Sem  micro   P={ai_sem_mic_p:.4f}  R={ai_sem_mic_r:.4f}  F1={ai_sem_mic_f:.4f}  ({ai_sem_m}/{ai_tot_r})")
    lines.append("")
    lines.append("  AGGREGATE -- DECISIONS:")
    lines.append(f"    Lex  macro-F1={dec_lex_macro_f:.4f}  P={dec_lex_macro_p:.4f}  R={dec_lex_macro_r:.4f}")
    lines.append(f"    Sem  macro-F1={dec_sem_macro_f:.4f}  P={dec_sem_macro_p:.4f}  R={dec_sem_macro_r:.4f}")
    lines.append(f"    Lex  micro   P={dec_lex_mic_p:.4f}  R={dec_lex_mic_r:.4f}  F1={dec_lex_mic_f:.4f}  ({dec_lex_m}/{dec_tot_r})")
    lines.append(f"    Sem  micro   P={dec_sem_mic_p:.4f}  R={dec_sem_mic_r:.4f}  F1={dec_sem_mic_f:.4f}  ({dec_sem_m}/{dec_tot_r})")
    lines.append("")
    lines.append("  AGGREGATE -- UNRESOLVED ISSUES:")
    lines.append(f"    Lex  macro-F1={iss_lex_macro_f:.4f}  P={iss_lex_macro_p:.4f}  R={iss_lex_macro_r:.4f}")
    lines.append(f"    Sem  macro-F1={iss_sem_macro_f:.4f}  P={iss_sem_macro_p:.4f}  R={iss_sem_macro_r:.4f}")
    lines.append(f"    Lex  micro   P={iss_lex_mic_p:.4f}  R={iss_lex_mic_r:.4f}  F1={iss_lex_mic_f:.4f}  ({iss_lex_m}/{iss_tot_r})")
    lines.append(f"    Sem  micro   P={iss_sem_mic_p:.4f}  R={iss_sem_mic_r:.4f}  F1={iss_sem_mic_f:.4f}  ({iss_sem_m}/{iss_tot_r})")
    lines.append("=" * 75)

    report_text = "\n".join(lines)
    RESULTS_TXT.write_text(report_text, encoding="utf-8")
    print(f"\n[OK] Report saved to: {RESULTS_TXT}\n", flush=True)
    print(report_text, flush=True)


if __name__ == "__main__":
    run_agentic_evaluation()
