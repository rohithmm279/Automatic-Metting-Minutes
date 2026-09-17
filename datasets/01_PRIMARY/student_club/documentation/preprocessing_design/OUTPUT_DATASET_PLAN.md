# Output Dataset Plan

## Design objective
This document specifies the intended output structure for one canonical meeting-level dataset view and four task-specific dataset views derived from the Student Club dataset without modifying the source files.

## Proposed output root
```
datasets/01_PRIMARY/student_club/preprocessed/
├── canonical/
│   ├── train_dev/
│   ├── validation/
│   └── test/
├── summary/
│   ├── train_dev/
│   ├── validation/
│   └── test/
├── action_item_extraction/
│   ├── train_dev/
│   ├── validation/
│   └── test/
├── decision_extraction/
│   ├── train_dev/
│   ├── validation/
│   └── test/
├── unresolved_issue_extraction/
│   ├── train_dev/
│   ├── validation/
│   └── test/
├── metadata/
├── manifest/
└── logs/
```

## Output file conventions
- Canonical outputs use JSONL.
- One canonical meeting record occupies one JSON object per JSONL line.
- Use the same `meeting_id` naming convention as the source dataset where possible.
- Keep one split folder per task output.
- Preserve source splits exactly:
  - `train_dev`
  - `validation`
  - `test`

## 1. Canonical meeting-level output
Location:
- `preprocessed/canonical/{split}/`

Record type:
- one complete meeting record per meeting

Canonical record fields:
- `meeting_id`
- `split`
- `category`
- `transcript`
- `target`

The target contains exactly:
- `summary`
- `key_topics`
- `action_items`
- `decisions`
- `unresolved_issues`

The nested action items, decisions, and unresolved issues preserve their source fields and values. No source paths, task labels, metadata copies, or inferred fields are added.

Expected canonical record count:
- train_dev: 49
- validation: 10
- test: 11
- total: 70

Canonical records are meeting-level complete records. Task-specific outputs below remain filtered views for individual tasks and may contain multiple item records per meeting.

## 2. Summary output
Location:
- `preprocessed/summary/{split}/`

Record type:
- one record per meeting

Example fields:
- `meeting_id`
- `split`
- `category`
- `summary`
- `key_topics`
- `transcript`

Expected count:
- 70 total records
- train_dev: 49
- validation: 10
- test: 11

## 3. Action item extraction output
Location:
- `preprocessed/action_item_extraction/{split}/`

Record type:
- one record per action item

Example fields:
- `meeting_id`
- `split`
- `category`
- `transcript`
- `task`
- `owner`
- `deadline`
- `evidence`
- `confidence`

Expected count:
- equal to total number of `action_items` entries across all meetings
- split counts should follow the source metadata and the meeting-level action-item counts

## 4. Decision extraction output
Location:
- `preprocessed/decision_extraction/{split}/`

Record type:
- one record per decision

Example fields:
- `meeting_id`
- `split`
- `category`
- `transcript`
- `decision`
- `evidence`

Expected count:
- equal to total number of `decisions` entries across all meetings
- split counts follow the source assignment and grounds-truth content

## 5. Unresolved issue extraction output
Location:
- `preprocessed/unresolved_issue_extraction/{split}/`

Record type:
- one record per unresolved issue

Example fields:
- `meeting_id`
- `split`
- `category`
- `transcript`
- `issue`
- `evidence`

Expected count:
- equal to total number of `unresolved_issues` entries across all meetings
- split counts follow the source assignment and grounds-truth content

## Metadata directory
Location:
- `preprocessed/metadata/`

Purpose:
- store a processed metadata manifest describing the source meeting IDs, split mapping, and task coverage

Suggested manifest content:
- `meeting_id`
- `source_transcript`
- `source_ground_truth`
- `split`
- `summary_record_present`
- `action_item_count`
- `decision_count`
- `issue_count`

## Manifest directory
Location:
- `preprocessed/manifest/`

Purpose:
- track which source meeting IDs contribute to each task-specific dataset

## Logs directory
Location:
- `preprocessed/logs/`

Purpose:
- store validation and error logs
- record skipped meetings due to missing metadata, invalid JSON, or missing files

## Validation and safety rules
- Use metadata as the split source of truth
- Validate exactly 49/10/11 canonical records for train_dev/validation/test before accepting the canonical output
- Reject duplicate canonical meeting IDs
- Validate canonical JSONL lines against the canonical schema
- Keep original dataset untouched
- Keep outputs in a dedicated preprocessed directory
- Do not alter or regenerate existing raw files
- Do not precompute embeddings or training sets in this design phase

## Notes for downstream use
- All task outputs are derived views over the same underlying meeting dataset.
- Evidence strings and source values remain faithful to the original data.
- This design intentionally avoids normalization, inference, or value reconstruction beyond preserving observed data exactly.
