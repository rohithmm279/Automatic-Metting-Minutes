# Preprocessing Rules

## Purpose
This document defines the read-only design rules for preprocessing the Student Club dataset into one canonical meeting-level view and four task-specific views. No dataset content is modified.

## Rule 1: Never modify source files
- Do not edit transcript TXT files.
- Do not edit ground-truth JSON files.
- Do not change metadata CSV values.
- Do not alter documentation or statistics.

## Rule 2: Keep all outputs separate
Generated outputs must be written under:
- datasets/01_PRIMARY/student_club/preprocessed/

Not inside:
- transcripts/
- ground_truth/
- metadata/
- documentation/

## Rule 3: Preserve split assignments exactly
Use metadata/metadata.csv as the authoritative split source.
The only valid split labels are:
- `train_dev`
- `validation`
- `test`

Do not create new split labels.
Do not reshuffle records.

## Rule 4: Preserve meeting_id exactly
Each source record is keyed by `meeting_id` and by filename stem:
- `SC001.txt` and `SC001.json` belong to the same meeting

## Rule 5: Build one canonical record per meeting
The canonical dataset must contain one complete record for each valid meeting. Its only top-level fields are:
- `meeting_id`
- `split`
- `category`
- `transcript`
- `target`

The `target` contains only `summary`, `key_topics`, `action_items`, `decisions`, and `unresolved_issues`, preserving the nested source structures and values.

Canonical records must be written as JSONL, with one JSON object per line, under `preprocessed/canonical/{split}/`.

## Rule 6: Keep canonical and task-specific views distinct
Canonical records contain the complete meeting and all available ground truth in one target. The four task-specific views remain separate outputs: summary is meeting-level, while action-item, decision, and unresolved-issue views are item-level. Do not replace or merge the four existing views with the canonical view.

## Rule 7: Preserve raw evidence text
For any extracted item, evidence must remain verbatim from the original JSON file.
Do not rewrite or paraphrase evidence.

## Rule 8: Preserve owner and deadline values exactly
This is a critical fidelity rule.
Values like:
- `Not specified`
- `sometime next week`
must remain exactly as written.

Do not replace with NULL, empty string, or guessed values.

## Rule 9: Preserve confidence as categorical string
Confidence field is a string label, not a numeric score.
Examples observed:
- `low`
- `medium`
Do not convert to numeric values during preprocessing design.

## Rule 10: Never invent missing information
If a value is absent or generic, keep it as-is.
Do not infer owners, deadlines, or topics.

## Rule 11: Keep one-to-one relationship intact
Each meeting has:
- one transcript
- one JSON annotation record
- one metadata row

Derived task records should be created as views over this one-to-one relationship, not as new or duplicate source records.

## Rule 12: Prevent duplicates
When generating outputs:
- never emit duplicate `meeting_id` records per split and task
- emit exactly one canonical record per `meeting_id` across the canonical dataset
- reject a canonical record whose split differs from metadata/metadata.csv
- never create multiple copies of the same source file
- never create duplicate output files by rerun

## Rule 13: Validate before writing output
Before writing any processed row or file:
- confirm transcript exists
- confirm JSON exists
- confirm metadata row exists
- confirm split label is valid
- confirm meeting_id matches source file stem

## Rule 14: Keep output schemas strict
Each task output must contain only the fields needed for that task and preserve `meeting_id`, `split`, and `category`.
Canonical output must use the exact canonical top-level schema and the complete nested `target` structure.

## Rule 15: Canonical split and count validation
Use metadata/metadata.csv as the source of truth and require exactly:
- `train_dev`: 49 canonical records
- `validation`: 10 canonical records
- `test`: 11 canonical records
- total: 70 canonical records

Do not reshuffle, regenerate, combine, or repartition these assignments.

## Rule 16: Error handling policy
Errors must be logged, not silently ignored:
- missing transcript file
- missing JSON file
- missing metadata row
- invalid JSON
- invalid split
- duplicate meeting record

## Rule 17: Output writing policy
- Write task outputs into separate folders by task and split
- Write canonical output as JSONL under `preprocessed/canonical/{split}/`
- Use a manifest to track source-to-output mapping
- Keep source dataset and generated outputs separated

## Rule 18: No execution in this design phase
This file only defines design logic.
Preprocessing itself is not executed here.
