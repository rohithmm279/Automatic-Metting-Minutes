# Preprocessing Pipeline Design

## Scope
This document defines a read-only preprocessing design for the Student Club dataset only. No dataset files are modified, converted, or regenerated in this phase.

## Input dataset
Location:
- datasets/01_PRIMARY/student_club/

Required inputs:
- transcripts/: SC###.txt
- ground_truth/: SC###.json
- metadata/metadata.csv
- documentation/README.md
- documentation/statistics.json

## Design goals
Produce one canonical meeting-level dataset view and four task-specific dataset views while preserving:
- original transcript text
- original meeting IDs
- original split assignments
- evidence text exactly as stored
- owner values exactly as stored, including `Not specified`
- deadline values exactly as stored, including `Not specified`
- confidence values as categorical strings
- all original dataset files without modification

## Output policy
The preprocessing phase should generate outputs under a separate directory, not inside the raw dataset tree:

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

This design intentionally keeps generated outputs separate from source data.

The canonical view uses JSONL. Each line is one complete meeting record. The four task-specific views remain separate derived views and are not replaced by the canonical view.

## Core transformation rules

### 1. Record identity
Each processed record must retain:
- `meeting_id`
- `split`
- `category`
- original transcript text
- original evidence values
- original metadata counts when available

### 2. Split preservation
The source metadata CSV defines the split column. The preprocessing logic must:
- read split from metadata/metadata.csv
- keep split values exactly as stored:
  - `train_dev`
  - `validation`
  - `test`
- never create a new split assignment
- never re-balance or move records across splits

### 3. Source pairing rule
Join transcript and ground truth by the base filename:
- `SC001.txt` ↔ `SC001.json`
- Use `meeting_id` as the canonical identifier

### 4. Evidence preservation rule
For every action item, decision, and issue:
- preserve `evidence` as-is
- do not remove whitespace beyond the original string representation
- do not normalize the evidence text for training
- preserve the exact original wording so downstream schema validation can match transcript text exactly

### 5. Owner / deadline preservation rule
Preserve owner and deadline strings exactly as they appear in the source JSON, including values such as:
- `Not specified`
- `sometime next week`
- generic free-form strings

The preprocessing pipeline must not invent missing values or replace them with placeholders.

### 6. Confidence preservation rule
`confidence` is treated as a categorical string, not a numeric score.
Allowed examples from the observed schema:
- `low`
- `medium`
This field must remain a string in the canonical processed view.

### 7. Canonical meeting-level transformation rule
For each valid meeting, create one canonical JSON object with exactly these top-level fields:

```json
{
  "meeting_id": "SC001",
  "split": "train_dev",
  "category": "...",
  "transcript": "...",
  "target": {
    "summary": "...",
    "key_topics": [],
    "action_items": [],
    "decisions": [],
    "unresolved_issues": []
  }
}
```

The target preserves the complete source ground-truth structure. Do not add source paths, metadata copies, task labels, inferred values, or other fields to canonical records. Preserve nested action-item, decision, and unresolved-issue objects and their source values exactly where possible.

### 8. Canonical output format and counts
- Write canonical records as JSONL, with one complete meeting object per line.
- Write canonical records under `preprocessed/canonical/{split}/`.
- Expected canonical counts are `train_dev`: 49, `validation`: 10, `test`: 11, total: 70.
- Use metadata/metadata.csv as the only source of canonical split assignments.

## Discovery and validation rules

### Input validation
Before generating any dataset view, validate:
- transcript file exists for meeting_id
- ground-truth file exists for meeting_id
- metadata row exists for meeting_id
- split value is present and valid
- JSON parses successfully
- action_items, decisions, unresolved_issues are arrays
- canonical target contains `summary`, `key_topics`, `action_items`, `decisions`, and `unresolved_issues`

### Value validation
Validate that:
- `meeting_id` is present and matches the filename stem
- `summary` is a string
- `key_topics` is a list of strings
- each `action_items[]` item contains `task`, `owner`, `deadline`, `evidence`, `confidence`
- each `decisions[]` item contains `decision`, `evidence`
- each `unresolved_issues[]` item contains `issue`, `evidence`

### Duplicate prevention
The pipeline must ensure:
- no duplicate `meeting_id` entries within a task split
- exactly one canonical record per `meeting_id`
- a canonical record is written only to the metadata-assigned split
- no duplicate processed records produced by repeated runs
- no duplication of original source files
- output generation is idempotent by meeting_id + task + split

## Task-specific dataset views

### 1. Summary dataset view
Purpose:
- create meeting-level summary supervision records

Required fields:
- `meeting_id`
- `split`
- `category`
- `summary`
- `key_topics`
- `transcript`

Optional fields:
- `metadata` dictionary (counts and transcript_word_count)

Notes:
- Keep the original meeting summary text and transcript verbatim.
- Do not rephrase or compress the summary.

### 2. Action item extraction dataset view
Purpose:
- generate one record per action item instance

Required fields:
- `meeting_id`
- `split`
- `category`
- `transcript`
- `task`
- `owner`
- `deadline`
- `evidence`
- `confidence`

Notes:
- One meeting may produce multiple action records.
- Each element of `action_items[]` becomes one row or one record in the task dataset.
- Preserve owner and deadline strings exactly, even if they are `Not specified`.

### 3. Decision extraction dataset view
Purpose:
- generate one record per decision instance

Required fields:
- `meeting_id`
- `split`
- `category`
- `transcript`
- `decision`
- `evidence`

Notes:
- One meeting may generate multiple decisions.
- Preserve decision evidence exactly.

### 4. Unresolved issue extraction dataset view
Purpose:
- generate one record per unresolved issue instance

Required fields:
- `meeting_id`
- `split`
- `category`
- `transcript`
- `issue`
- `evidence`

Notes:
- One meeting may generate multiple issue entries.
- Preserve issue evidence exactly.

## Canonical meeting-level dataset view
The canonical view represents one complete meeting as one complete record:

```
{
  "meeting_id": "SC001",
  "split": "train_dev",
  "category": "event_planning",
  "transcript": "...raw transcript text...",
  "target": {
    "summary": "...",
    "key_topics": [],
    "action_items": [],
    "decisions": [],
    "unresolved_issues": []
  }
}
```

The canonical output is JSONL, with one object per line. Canonical meeting-level records contain the complete target, while task-specific records contain one meeting summary or one extracted item for their individual task. The task-specific datasets remain unchanged and are not required to include the canonical `target` wrapper.

Canonical validation must confirm:
- exactly 70 records overall
- exactly 49 `train_dev`, 10 `validation`, and 11 `test` records
- each `meeting_id` occurs exactly once
- each record has only the defined canonical top-level fields
- transcript and nested target values match their source records

## Error handling

### Missing transcript
- Log an error and skip the record for that task
- Do not create placeholder content

### Missing JSON
- Log an error and skip the record for that task
- Do not fabricate summary or extraction labels

### Missing metadata row
- Log and skip the record for all derived task outputs
- Keep source raw files untouched

### Invalid JSON
- Log parse error
- Skip the affected record

### Empty transcript
- Log as warning
- Do not create processed rows unless explicitly allowed by downstream design

### Empty action_items / decisions / unresolved_issues arrays
- Valid dataset record if the array is empty, but the task-specific derived dataset will contain zero items for that meeting
- Do not synthesize values

### Duplicate meeting IDs
- Raise a validation error
- Prevent writing duplicates downstream

## Split preservation rules
- Use metadata/metadata.csv as the single authoritative split source
- Write records to output folders matching the split value exactly:
  - `train_dev/`
  - `validation/`
  - `test/`
- Keep record counts equal to the source metadata counts for each split
- Do not shuffle or resplit the data during this phase

## Expected dataset cardinality
For the original dataset:
- total meetings: 70
- `train_dev`: 49
- `validation`: 10
- `test`: 11

Expected task-specific cardinality:
- Summary dataset: 70 records total; same split distribution as the source
- Action item extraction dataset: equal to total number of action items across all meetings, not number of meetings
- Decision extraction dataset: equal to total number of decision items across all meetings
- Unresolved issue extraction dataset: equal to total number of unresolved issue items across all meetings

The exact per-split counts should be derived from metadata and the source JSON arrays.

## Recommended validation checks before execution
1. Confirm all 70 meeting IDs exist in transcript, JSON, and metadata sets
2. Confirm no duplicate meeting IDs exist
3. Confirm all `split` values are valid
4. Confirm every extracted item keeps its original evidence and fields
5. Confirm output files are written only to the separate preprocessed directory

## Design decision requiring review
- The design currently treats `owner` and `deadline` as exact strings instead of normalizing them to canonical values.
- This preserves fidelity but requires downstream consumers to handle free-form strings such as `Not specified` consistently.
- This is intentional and should be reviewed before execution.

## Final recommendation
Review preprocessing design before executing preprocessing.
