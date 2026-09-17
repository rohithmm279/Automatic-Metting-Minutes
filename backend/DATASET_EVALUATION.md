# Dataset ingestion and evaluation

`GET /datasets` recursively lists supported files and selectable parent
directories under the repository-level `datasets/` directory. Each result has
an `entry_type` of `file` or `directory`. Supported formats are CSV, JSON,
JSONL, TXT, and `.transcript`. Source files are read only and are never
modified.

Use a returned file or directory `name` as `dataset_name` in `POST /evaluate`.
Directories are scanned recursively and records are processed only until the
requested limit. Evaluation is bounded to 10 records by default and accepts
`limit` from 1 through 50. Directory requests above the number of valid records
return a clear validation error; single-file requests continue to return their
available record(s).

Normalized records contain `id`, `transcript`, optional reference summary,
actions, decisions, issues, and `source_dataset`. Missing annotations remain
`null`; the service does not invent labels. TXT transcripts in a `transcripts/`
directory automatically use a same-ID JSON file in sibling `ground_truth/` when
present, such as the student-club `SC001` files.

`POST /evaluate` runs the same shared pipeline as `/analyze-meeting`: transcript
cleaning, Gemini when available, then rule-based fallback. It reports summary
availability and action, decision, and issue metrics. Label metrics use greedy
one-to-one token Jaccard matches of at least 0.5 and report precision, recall,
F1, counts, or an unavailable message when reference annotations do not exist.

Example request:

```json
{
  "dataset_name": "01_PRIMARY/student_club/transcripts/SC001.txt",
  "limit": 1
}
```

Evaluate several primary transcripts:

```json
{
  "dataset_name": "01_PRIMARY/student_club/transcripts",
  "limit": 10
}
```
