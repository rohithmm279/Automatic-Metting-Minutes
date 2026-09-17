# Preprocessing Execution Report

## Final status
**SUCCESS**

The approved preprocessing pipeline was executed using only `datasets/01_PRIMARY/student_club/`. Original source files were read-only throughout execution.

## Source dataset counts

| Source | Count |
|---|---:|
| Transcripts | 70 |
| Ground-truth JSON files | 70 |
| Metadata records | 70 |

## Source validation results

- Expected source directories: PASSED
- Transcript and ground-truth matching: PASSED
- Metadata validation: PASSED
- Unique metadata meeting IDs: PASSED
- JSON parsing: PASSED
- Required source fields: PASSED
- Split validation: PASSED
- Pre-execution validation: PASSED

## Canonical dataset

Output format: JSONL, one complete meeting record per line.

| Split | Records |
|---|---:|
| train_dev | 49 |
| validation | 10 |
| test | 11 |
| **Total** | **70** |

Canonical meeting IDs are unique, and each canonical record contains the complete transcript-to-target relationship with summary, key topics, action items, decisions, and unresolved issues.

## Task-specific dataset counts

| View | Records |
|---|---:|
| summary | 70 |
| action_item_extraction | 243 |
| decision_extraction | 113 |
| unresolved_issue_extraction | 98 |

The item-level views may contain multiple records for one meeting as specified by the approved design.

## Split counts

All generated views preserve the metadata assignments. Canonical and summary counts are 49 train_dev, 10 validation, and 11 test. Item-level views were generated from the source items without cross-split leakage.

## Processed-output validation

- JSONL syntax: PASSED
- Required fields: PASSED
- Canonical schema shape: PASSED
- Canonical duplicate check: PASSED
- Canonical split counts: PASSED
- Task-specific split validation: PASSED
- Malformed records: 0
- Generation errors: 0
- Warnings: 0

## Source integrity results

- Source transcripts remain present: PASSED, 70 files
- Source ground-truth JSON files remain present: PASSED, 70 files
- Source metadata records remain present: PASSED, 70 records
- No source files were modified, moved, renamed, deleted, or overwritten by this execution: PASSED
- No derived files were written inside `transcripts/`, `ground_truth/`, or `metadata/`: PASSED

## Files created

- `canonical/{train_dev,validation,test}/data.jsonl`
- `summary/{train_dev,validation,test}/data.jsonl`
- `action_item_extraction/{train_dev,validation,test}/data.jsonl`
- `decision_extraction/{train_dev,validation,test}/data.jsonl`
- `unresolved_issue_extraction/{train_dev,validation,test}/data.jsonl`
- `metadata/processed_meeting_manifest.json`
- `manifest/preprocessing_manifest.json`
- `logs/preprocessing_execution_log.json`
- `PREPROCESSING_EXECUTION_REPORT.md`

All files are under `datasets/01_PRIMARY/student_club/preprocessed/`.

## Errors and warnings

- Errors: 0
- Warnings: 0
- Records skipped: 0
