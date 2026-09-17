"""
process_qmsum.py

Converts the raw QMSum dataset (data/{Academic,Committee,Product}/{train,val,test})
into the project's common internal JSON format, one file per split, without
altering the original raw files. Preserves the official train/val/test split.

QMSum provides: transcript, query/answer pairs, relevant transcript spans.
It does NOT provide: action items, decisions, or issues in our schema sense,
so those fields are left as [] per the "do not invent annotations" rule.
"""
import json
import os
from pathlib import Path

RAW_DIR = Path("../../raw/qmsum/data")
OUT_DIR = Path(".")
DOMAINS = ["Academic", "Committee", "Product"]
SPLITS = {"train": "train", "val": "validation", "test": "test"}


def load_split(domain, split_dir):
    folder = RAW_DIR / domain / split_dir
    records = []
    if not folder.exists():
        return records
    for fname in sorted(os.listdir(folder)):
        if not fname.endswith(".json"):
            continue
        with open(folder / fname, encoding="utf-8") as f:
            data = json.load(f)
        transcript_text = " ".join(
            f"{turn.get('speaker', '')}: {turn.get('content', '')}"
            for turn in data.get("meeting_transcripts", [])
        )
        queries = []
        for q in data.get("general_query_list", []) + data.get("specific_query_list", []):
            queries.append({
                "query": q.get("query"),
                "answer": q.get("answer"),
                "relevant_text_span": q.get("relevant_text_span", []),
            })
        records.append({
            "dataset": "QMSum",
            "meeting_id": fname.replace(".json", ""),
            "domain": domain,
            "split": SPLITS[split_dir],
            "transcript": transcript_text,
            "reference_summary": None,
            "queries": queries,
            "reference_actions": [],
            "reference_decisions": [],
            "reference_issues": [],
        })
    return records


def main():
    all_stats = {"train": 0, "validation": 0, "test": 0}
    for split_dir, split_name in SPLITS.items():
        all_records = []
        for domain in DOMAINS:
            all_records.extend(load_split(domain, split_dir))
        out_path = OUT_DIR / f"qmsum_{split_name}.jsonl"
        with open(out_path, "w", encoding="utf-8") as f:
            for rec in all_records:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        all_stats[split_name] = len(all_records)
        print(f"{split_name}: {len(all_records)} meetings -> {out_path}")
    return all_stats


if __name__ == "__main__":
    main()
