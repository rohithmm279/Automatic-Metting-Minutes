"""
process_elitr_bench.py

Converts the raw ELITR-Bench QA/conversational benchmark files into the
project's common internal JSON format, preserving the dev/test2 splits as
provided by the official archive.

IMPORTANT LIMITATION: The ELITR-Bench data.zip (unlocked with the
repository's published password) contains ONLY the benchmark questions and
ground-truth answers, keyed by meeting id. It does NOT contain the underlying
meeting transcripts. Per the official README, transcripts must be obtained
separately from the ELITR-minuting-corpus archive hosted on LINDAT
(https://lindat.mff.cuni.cz/...), a domain not reachable from this sandbox's
allowlisted network. Therefore "transcript" is left as null here; the field
should be populated later by joining on meeting id once the transcript
corpus has been downloaded outside this environment.
"""
import json
from pathlib import Path

RAW_DIR = Path(".")
OUT_DIR = Path(".")


def process_file(fname, kind):
    path = RAW_DIR / fname
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    split = d.get("split")
    records = []
    for m in d.get("meetings", []):
        records.append({
            "dataset": "ELITR-Bench",
            "meeting_id": m.get("id"),
            "split": split,
            "kind": kind,  # "qa" (single questions) or "conv" (conversational)
            "transcript": None,  # see module docstring: not included in data.zip
            "reference_summary": None,
            "questions": m.get("questions", []),
            "reference_actions": [],
            "reference_decisions": [],
            "reference_issues": [],
        })
    return records


def main():
    files = {
        "elitr-bench-qa_dev.json": "qa",
        "elitr-bench-qa_test2.json": "qa",
        "elitr-bench-conv_dev.json": "conv",
        "elitr-bench-conv_test2.json": "conv",
    }
    all_records = []
    for fname, kind in files.items():
        recs = process_file(fname, kind)
        all_records.extend(recs)
        print(f"{fname}: {len(recs)} meetings")
    out_path = OUT_DIR / "elitr_bench_all.jsonl"
    with open(out_path, "w", encoding="utf-8") as f:
        for r in all_records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"Total: {len(all_records)} meeting records -> {out_path}")


if __name__ == "__main__":
    main()
