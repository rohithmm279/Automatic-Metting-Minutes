# Student Club Data Quality Report

This report is a read-only quality check based on the actual files in [datasets/01_PRIMARY/student_club](datasets/01_PRIMARY/student_club).

## Summary
- Transcript files: 70
- Ground-truth JSON files: 70
- Matched transcript/JSON pairs: 70
- Duplicate meeting IDs: 0
- Missing transcript files: 0
- Missing JSON files: 0
- Empty transcripts: 0
- Invalid JSON: 0
- Duplicate metadata records: 0

## 1. Inventory checks
- Transcript naming pattern: `SC###.txt`
- Ground-truth naming pattern: `SC###.json`
- Matching rule: same numeric ID before extension
- Matching result: all 70 transcript files matched 70 JSON files exactly

## 2. Metadata checks
- Metadata file: [datasets/01_PRIMARY/student_club/metadata/metadata.csv](datasets/01_PRIMARY/student_club/metadata/metadata.csv)
- Columns observed:
  - `meeting_id`
  - `category`
  - `num_speakers`
  - `num_action_items`
  - `num_decisions`
  - `num_issues`
  - `transcript_word_count`
  - `split`
- Record count: 70
- Unique meeting IDs: 70
- Duplicate rows: 0
- Split counts: validation = 10, train_dev = 49, test = 11

## 3. Transcript checks
- All 70 transcript files are non-empty.
- Speaker names are explicit in the text: `Speaker:`
- No timestamps were detected.
- Each transcript follows a similar conversational structure with a header line and one speaker turn per line.
- Transcript lengths are consistent, with average length around 265.8 words; min 197, max 322.

## 4. JSON checks
- All 70 JSON files parsed successfully.
- No invalid JSON files were found.
- Structural schema remained consistent across all inspected files.
- Top-level keys observed:
  - `meeting_id`
  - `category`
  - `summary`
  - `key_topics`
  - `action_items`
  - `decisions`
  - `unresolved_issues`
- No empty arrays were observed in the inspected subset.
- No null-value anomalies were observed in the inspected subset.

## 5. Cross-file integrity checks
- Every transcript file matched one metadata row by `meeting_id`.
- Every transcript file matched one ground-truth JSON file by `meeting_id`.
- Dataset can be joined via `meeting_id` without ambiguity.

## 6. Observed inconsistencies
- No major schema inconsistencies were found.
- Only textual value variations exist by meeting, which is expected.
- Some action items contain generic values such as `"Not specified"` for `owner` or `deadline`; this is a value-level variation, not a schema issue.

## 7. Conclusion
The Student Club dataset is structurally sound and internally consistent for one-to-one meeting matching by `meeting_id`. There are no unmatched pairs, duplicate IDs, or invalid records in the inspected dataset.
