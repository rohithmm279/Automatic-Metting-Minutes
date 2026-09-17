# Student Club Dataset Schema Audit

This report is based only on the actual files in [datasets/01_PRIMARY/student_club](datasets/01_PRIMARY/student_club). No dataset files were modified.

## 1. Dataset file inventory

### File counts
- Transcript files: 70
- Ground-truth JSON files: 70
- Metadata CSV files: 1
- Documentation files: 2

### File naming patterns
- Transcript files: `SC###.txt`
- Ground-truth files: `SC###.json`
- Meeting IDs: `SC001` through `SC070`

### Pairing check
- Every transcript file has a matching JSON file by the same base ID.
- Example:
  - [datasets/01_PRIMARY/student_club/transcripts/SC001.txt](datasets/01_PRIMARY/student_club/transcripts/SC001.txt)
  - [datasets/01_PRIMARY/student_club/ground_truth/SC001.json](datasets/01_PRIMARY/student_club/ground_truth/SC001.json)

### Missing pairs
- None found.

### Duplicate IDs
- No duplicate transcript IDs found.
- No duplicate ground-truth IDs found.

### Available metadata and documentation
- Metadata CSV: [datasets/01_PRIMARY/student_club/metadata/metadata.csv](datasets/01_PRIMARY/student_club/metadata/metadata.csv)
- Documentation: [datasets/01_PRIMARY/student_club/documentation/README.md](datasets/01_PRIMARY/student_club/documentation/README.md)
- Statistics: [datasets/01_PRIMARY/student_club/documentation/statistics.json](datasets/01_PRIMARY/student_club/documentation/statistics.json)

---

## 2. Metadata schema audit

### Exact file path
[datasets/01_PRIMARY/student_club/metadata/metadata.csv](datasets/01_PRIMARY/student_club/metadata/metadata.csv)

### Exact column names
1. `meeting_id`
2. `category`
3. `num_speakers`
4. `num_action_items`
5. `num_decisions`
6. `num_issues`
7. `transcript_word_count`
8. `split`

### Inferred data type of each column
| Column | Inferred type | Notes |
|---|---|---|
| meeting_id | string | Example: SC001 |
| category | string | Example: event_planning |
| num_speakers | integer | Count of speakers |
| num_action_items | integer | Count from ground truth |
| num_decisions | integer | Count from ground truth |
| num_issues | integer | Count from ground truth |
| transcript_word_count | integer | Word count per transcript |
| split | string | Values observed: validation, train_dev, test |

### Number of records
- 70 records

### Unique meeting IDs
- 70 unique meeting IDs

### Split column and counts
- Split column present: `split`
- Counts observed:
  - `validation`: 10
  - `train_dev`: 49
  - `test`: 11

### Missing values
- No missing values observed in the CSV header row or sample rows inspected.

### Duplicate records
- No duplicate rows found.

---

## 3. Transcript schema audit

### Sample transcript files inspected
- [datasets/01_PRIMARY/student_club/transcripts/SC001.txt](datasets/01_PRIMARY/student_club/transcripts/SC001.txt)
- [datasets/01_PRIMARY/student_club/transcripts/SC010.txt](datasets/01_PRIMARY/student_club/transcripts/SC010.txt)
- [datasets/01_PRIMARY/student_club/transcripts/SC030.txt](datasets/01_PRIMARY/student_club/transcripts/SC030.txt)
- [datasets/01_PRIMARY/student_club/transcripts/SC050.txt](datasets/01_PRIMARY/student_club/transcripts/SC050.txt)
- [datasets/01_PRIMARY/student_club/transcripts/SC070.txt](datasets/01_PRIMARY/student_club/transcripts/SC070.txt)

### Transcript file structure
Each transcript is plain text conversation content with:
- a header line such as `[Meeting: Annual Fest Planning | Attendees: Priya, Meera, Vikram, Aditya]`
- speaker turns in the form `Speaker: ...`
- one speaker turn per line
- newline-separated turns

### Speaker names present?
- Yes. Speaker names are explicit and repeated in the format `Name: message`.

### Timestamps present?
- No timestamps were found in the inspected files.

### Speaker turns clearly separated?
- Yes. Each utterance is a separate line and begins with a speaker label followed by a colon.

### Metadata embedded in transcripts?
- Yes, a header line includes meeting title and attendees list, but there is no formal JSON metadata block inside the transcript.

### Approximate transcript length
- Average approximate transcript length: 265.8 words
- Minimum: 197 words
- Maximum: 322 words

### Formatting inconsistencies
- Minor conversational formatting artifacts appear, including:
  - parentheses such as `(interrupting)`
  - dashes and ellipses in the text
  - repeated or corrected statements such as “Wait, let me correct that — it’s actually by Friday.”
- No transcript was empty.

---

## 4. Ground-truth JSON schema audit

### Sample JSON files inspected
- [datasets/01_PRIMARY/student_club/ground_truth/SC001.json](datasets/01_PRIMARY/student_club/ground_truth/SC001.json)
- [datasets/01_PRIMARY/student_club/ground_truth/SC010.json](datasets/01_PRIMARY/student_club/ground_truth/SC010.json)
- [datasets/01_PRIMARY/student_club/ground_truth/SC030.json](datasets/01_PRIMARY/student_club/ground_truth/SC030.json)
- [datasets/01_PRIMARY/student_club/ground_truth/SC050.json](datasets/01_PRIMARY/student_club/ground_truth/SC050.json)
- [datasets/01_PRIMARY/student_club/ground_truth/SC070.json](datasets/01_PRIMARY/student_club/ground_truth/SC070.json)

### Top-level keys
Observed structure across the inspected files:
- `meeting_id`
- `category`
- `summary`
- `key_topics`
- `action_items`
- `decisions`
- `unresolved_issues`

### Nested keys and field types
#### 1. `meeting_id`
- Type: string
- Example: `"SC001"`
- Required: yes

#### 2. `category`
- Type: string
- Example: `"event_planning"`
- Required: yes

#### 3. `summary`
- Type: string
- Example: `"The club discussed annual fest planning, covering 3 action item(s), 1 decision(s), and 2 open issue(s)."`
- Required: yes

#### 4. `key_topics`
- Type: array of strings
- Example: `["Set up the registration desk", "annual fest planning", "Book the auditorium"]`
- Required: yes

#### 5. `action_items`
- Type: array of objects
- Required: yes
- Each item contains:
  - `task`: string
  - `owner`: string
  - `deadline`: string
  - `evidence`: string
  - `confidence`: string

#### 6. `decisions`
- Type: array of objects
- Required: yes
- Each item contains:
  - `decision`: string
  - `evidence`: string

#### 7. `unresolved_issues`
- Type: array of objects
- Required: yes
- Each item contains:
  - `issue`: string
  - `evidence`: string

### Fields containing the target semantics
- Meeting summary: `summary`
- Action items: `action_items`
- Decisions: `decisions`
- Issues: `unresolved_issues`
- Participants: not directly stored as a dedicated field; speakers are visible in transcripts, not in the JSON object itself
- Deadlines: `action_items[].deadline`
- Owners: `action_items[].owner`
- Evidence: `action_items[].evidence`, `decisions[].evidence`, and `unresolved_issues[].evidence`

### Consistency across files
- All inspected JSON files used the same top-level key set.
- The exact key set was identical across all 70 JSON files inspected programmatically: `('action_items', 'category', 'decisions', 'key_topics', 'meeting_id', 'summary', 'unresolved_issues')`

### Optional or missing fields
- No missing top-level keys were observed in the inspected files.
- Some values are intentionally generic such as `"Not specified"` for owner or deadline.
- No null values were found in the inspected subset.

### Empty arrays or nulls
- Empty arrays were not observed in the inspected files.
- Null values were not observed in the inspected subset.

### Schema inconsistencies between files
- No structural schema inconsistencies were observed among the inspected JSON files.
- Only the content values change by meeting.

---

## 5. Transcript ↔ ground-truth relationship

### Meeting ID matching rule
- The matching rule is the base file name, excluding extension.
- Example:
  - Transcript: `SC001.txt`
  - Ground truth: `SC001.json`

### Relationship type
- One transcript corresponds to one ground-truth JSON record.
- Relationship is one-to-one.

### Metadata references
- Metadata CSV contains `meeting_id` values matching the transcript and JSON IDs.
- The metadata file therefore references transcript IDs and indirectly the corresponding ground-truth records.

### Joinability
- All 70 transcripts have a matching JSON and matching metadata row.
- The dataset can be joined by `meeting_id`.

---

## 6. Data quality checks

### Read-only checks performed
- Missing transcript files: none
- Missing ground-truth files: none
- Empty transcripts: none
- Invalid JSON: none
- Duplicate IDs: none
- Unmatched transcript/JSON pairs: none
- Missing metadata: none
- Inconsistent split labels: none in the CSV; observed values are `validation`, `train_dev`, and `test`
- Malformed records: none found in the inspected sample and programmatic checks

### Observed quality notes
- The dataset is structurally consistent.
- The schema is stable across all 70 records.
- Ground truth records include textual evidence spans that are consistent with transcript content.

---

## Final conclusion

The Student Club dataset has a stable, one-to-one schema: each meeting has one transcript and one ground-truth JSON, tied together by `meeting_id`. The primary annotation schema is centered on `summary`, `key_topics`, `action_items`, `decisions`, and `unresolved_issues`, with evidence stored under each object.
