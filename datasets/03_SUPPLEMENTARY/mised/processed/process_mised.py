"""
process_mised.py

Converts the raw MISeD dataset (mised/{train,validation,test}.jsonl) into the
project's common internal JSON format. Preserves the official split.

Correction to the original task assumption: MISeD's meeting IDs follow the
AMI/ICSI naming conventions (e.g. "ES2004a" = AMI, "Bmr006"/"Bro004" = ICSI),
not QMSum. Each MISeD record embeds its own transcript segments directly, so
it is self-contained and does not require joining against QMSum files.

MISeD provides: information-seeking dialog turns (query/response pairs) over
meeting transcript segments. It does NOT provide action items, decisions, or
issue annotations, so those fields are left as [] per the "do not invent
annotations" rule.
"""
import json
from pathlib import Path

RAW_DIR = Path("../../raw/mised/mised")
OUT_DIR = Path(".")
SPLIT_FILES = {"train": "train", "validation": "validation", "test": "test"}


def convert_split(split_file, split_name):
    records = []
    path = RAW_DIR / f"{split_file}.jsonl"
    if not path.exists():
        return records
    with open(path, encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            meeting = d.get("meeting", {})
            transcript_text = " ".join(
                f"{seg.get('speakerName', '')}: {seg.get('text', '')}"
                for seg in meeting.get("transcriptSegments", [])
            )
            dialog_turns = d.get("dialog", {}).get("dialogTurns", [])
            records.append({
                "dataset": "MISeD",
                "meeting_id": meeting.get("meetingId"),
                "dialog_id": d.get("dialogId"),
                "source_corpus": "AMI" if meeting.get("meetingId", "").startswith(("ES", "IS", "TS")) else "ICSI",
                "split": split_name,
                "transcript": transcript_text,
                "reference_summary": None,
                "dialog_turns": [
                    {"query": t.get("query"), "response": t.get("response")}
                    for t in dialog_turns
                ],
                "reference_actions": [],
                "reference_decisions": [],
                "reference_issues": [],
            })
    return records


def main():
    stats = {}
    for split_file, split_name in SPLIT_FILES.items():
        recs = convert_split(split_file, split_name)
        out_path = OUT_DIR / f"mised_{split_name}.jsonl"
        with open(out_path, "w", encoding="utf-8") as f:
            for r in recs:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        stats[split_name] = len(recs)
        print(f"{split_name}: {len(recs)} dialogs -> {out_path}")
    return stats


if __name__ == "__main__":
    main()
