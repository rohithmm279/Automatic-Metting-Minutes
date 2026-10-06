#!/usr/bin/env python3
"""Score predictions against ground truth, per field.

Usage:
  python evaluate.py dataset.jsonl predictions.jsonl [--thr 0.6] [--errors 5]
  python evaluate.py dataset.jsonl --self-test        # gold vs gold, expect 1.0

predictions.jsonl: one line per meeting: {"id": "meeting_001", "prediction": {summary, action_items, decisions, unresolved_issues}}
Matching is fuzzy (token overlap), so wording can differ; owner / deadline_iso / status must match exactly in strict mode.
Overlap-based matching is a rough proxy: use an LLM judge for final numbers.
"""
import argparse
import json
import re

STOP = {"the", "a", "an", "to", "of", "for", "on", "in", "and", "is", "be", "will", "we", "it", "that", "this", "with", "by", "at"}


def toks(s):
    return {w for w in re.findall(r"[a-z0-9]+", (s or "").lower()) if w not in STOP}


def overlap(a, b):
    ta, tb = toks(a), toks(b)
    return len(ta & tb) / min(len(ta), len(tb)) if ta and tb else 0.0


def greedy(gold, pred, score, thr):
    pairs = sorted(((score(g, p), gi, pi) for gi, g in enumerate(gold) for pi, p in enumerate(pred)), reverse=True)
    ug, up, out = set(), set(), []
    for s, gi, pi in pairs:
        if s >= thr and gi not in ug and pi not in up:
            ug.add(gi)
            up.add(pi)
            out.append((gi, pi))
    return out


def prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return p, r, (2 * p * r / (p + r) if p + r else 0.0)


def norm(x):
    return (x or "").strip().lower() or None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset")
    ap.add_argument("predictions", nargs="?")
    ap.add_argument("--thr", type=float, default=0.6)
    ap.add_argument("--errors", type=int, default=0)
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()

    gold = {}
    for line in open(a.dataset, encoding="utf-8"):
        d = json.loads(line)
        gold[d["id"]] = d["ground_truth"]
    if a.self_test:
        pred = dict(gold)
    else:
        pred = {}
        for line in open(a.predictions, encoding="utf-8"):
            d = json.loads(line)
            pred[d["id"]] = d["prediction"]

    c = {k: [0, 0, 0] for k in ("act_loose", "act_strict", "decisions", "unresolved")}
    attr = {"owner": [0, 0], "deadline_iso": [0, 0], "status": [0, 0]}
    errs = {k: [] for k in c}
    for mid, g in gold.items():
        p = pred.get(mid, {"action_items": [], "decisions": [], "unresolved_issues": []})
        ga, pa = g["action_items"], p.get("action_items", [])
        m = greedy(ga, pa, lambda x, y: overlap(x["task"], y.get("task", "")), a.thr)
        strict = 0
        for gi, pi in m:
            x, y = ga[gi], pa[pi]
            ok = [norm(x["owner"]) == norm(y.get("owner")), norm(x["deadline_iso"]) == norm(y.get("deadline_iso")), x["status"] == y.get("status")]
            for k, v in zip(attr, ok):
                attr[k][0] += v
                attr[k][1] += 1
            strict += all(ok)
            if not all(ok):
                errs["act_strict"].append((mid, x, y))
        c["act_loose"][0] += len(m); c["act_loose"][1] += len(pa) - len(m); c["act_loose"][2] += len(ga) - len(m)
        c["act_strict"][0] += strict; c["act_strict"][1] += len(pa) - strict; c["act_strict"][2] += len(ga) - strict
        for key, pk in (("decisions", "decisions"), ("unresolved", "unresolved_issues")):
            gl, pl = g[pk], p.get(pk, [])
            mm = greedy(gl, pl, overlap, a.thr)
            c[key][0] += len(mm); c[key][1] += len(pl) - len(mm); c[key][2] += len(gl) - len(mm)
            hit_g = {x for x, _ in mm}
            hit_p = {y for _, y in mm}
            errs[key] += [(mid, "MISSED", s) for i, s in enumerate(gl) if i not in hit_g]
            errs[key] += [(mid, "EXTRA", s) for i, s in enumerate(pl) if i not in hit_p]

    print(f"{'field':<14}{'P':>7}{'R':>7}{'F1':>7}")
    f1 = {}
    for k, (tp, fp, fn) in c.items():
        P, R, F = prf(tp, fp, fn)
        f1[k] = F
        print(f"{k:<14}{P:7.3f}{R:7.3f}{F:7.3f}")
    print(f"\nbalanced F1 (loose actions) : {(f1['act_loose'] + f1['decisions'] + f1['unresolved']) / 3:.3f}")
    print(f"balanced F1 (strict actions): {(f1['act_strict'] + f1['decisions'] + f1['unresolved']) / 3:.3f}")
    print("\nattribute accuracy on matched action items:")
    for k, (ok, n) in attr.items():
        print(f"  {k:<13}{(ok / n if n else 0):.3f}  ({ok}/{n})")
    if a.errors:
        for k, v in errs.items():
            print(f"\n--- first {a.errors} errors: {k}")
            for e in v[:a.errors]:
                print("  ", e)


if __name__ == "__main__":
    main()
