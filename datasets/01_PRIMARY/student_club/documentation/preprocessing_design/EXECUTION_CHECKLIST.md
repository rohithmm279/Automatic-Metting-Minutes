# Execution Checklist

## Scope
This checklist is for future preprocessing execution only. It does not perform any transformation now.

## Phase 1: Verify source integrity
- [ ] Confirm metadata file exists
- [ ] Confirm transcript directory contains all expected meeting files
- [ ] Confirm ground_truth directory contains matching JSON files
- [ ] Confirm 70 transcript files and 70 JSON files match by meeting_id
- [ ] Confirm metadata row count matches the source set
- [ ] Validate all split values are one of: `train_dev`, `validation`, `test`

## Phase 2: Build the derived manifest
- [ ] Read metadata rows
- [ ] Join transcripts and JSON annotations on `meeting_id`
- [ ] Record each meeting's source paths and split
- [ ] Count action_items, decisions, unresolved_issues per meeting
- [ ] Build outputs by split and task, including the canonical meeting-level JSONL view
- [ ] Confirm canonical output is planned under `preprocessed/canonical/{split}/`
- [ ] Confirm no canonical JSONL files are created during this design-only phase

## Phase 3: Validate canonical and task-specific schema rules
- [ ] Ensure each canonical JSONL line contains exactly `meeting_id`, `split`, `category`, `transcript`, and `target`
- [ ] Ensure each canonical `target` contains `summary`, `key_topics`, `action_items`, `decisions`, and `unresolved_issues`
- [ ] Ensure canonical nested action items, decisions, and unresolved issues preserve source fields and values
- [ ] Ensure canonical records use metadata splits without reshuffling
- [ ] Confirm canonical counts are train_dev=49, validation=10, test=11, total=70
- [ ] Confirm exactly one canonical record exists per meeting_id
- [ ] Ensure each summary row includes `meeting_id`, `split`, `category`, `summary`, `key_topics`, `transcript`
- [ ] Ensure each action item row includes `meeting_id`, `split`, `category`, `transcript`, `task`, `owner`, `deadline`, `evidence`, `confidence`
- [ ] Ensure each decision row includes `meeting_id`, `split`, `category`, `transcript`, `decision`, `evidence`
- [ ] Ensure each unresolved issue row includes `meeting_id`, `split`, `category`, `transcript`, `issue`, `evidence`
- [ ] Ensure evidence strings are preserved verbatim
- [ ] Ensure owner, deadline, and confidence remain as source strings

## Phase 4: Write outputs safely
- [ ] Create `preprocessed/` root only if needed
- [ ] Create split folders under each task output, including canonical
- [ ] Write canonical output as JSONL, one meeting object per line
- [ ] Write task outputs without modifying original files
- [ ] Save metadata manifest under `preprocessed/metadata/`
- [ ] Save source-to-output mapping under `preprocessed/manifest/`
- [ ] Save logs under `preprocessed/logs/`

## Phase 5: Run verification checks
- [ ] Confirm no source files changed
- [ ] Confirm split totals equal source counts
- [ ] Confirm no duplicate `meeting_id` records per split/task
- [ ] Confirm no duplicate canonical `meeting_id` records and no canonical split mismatch
- [ ] Confirm no missing values in required fields
- [ ] Confirm all processing logs are recorded

## Phase 6: Sign-off
- [ ] Review generated outputs with source dataset
- [ ] Verify preservation of evidence and raw strings
- [ ] Verify downstream tasks can read the outputs without raw data mutation
- [ ] Approve execution only after design review is complete
