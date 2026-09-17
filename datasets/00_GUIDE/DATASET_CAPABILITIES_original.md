# DATASET_CAPABILITIES.md

What each dataset actually provides. Only fields confirmed present in the
acquired/generated files are listed as "Available" — nothing here is
assumed or invented.

---

### Dataset: AMI
**Status:** Not acquired in this environment (see DATASET_SOURCES.md).
**Available (per official documentation, not independently verified here):**
- transcript (orthographic)
- abstractive/extractive summary annotations
- dialogue act annotations
- topic segmentation
**Not available / not confirmed:** structured action items, owners,
deadlines, or decisions in this project's schema — AMI provides annotation
layers that a downstream pipeline could derive these from, but does not
ship them pre-extracted in this schema.

---

### Dataset: QMSum
**Status:** Acquired.
**Available (confirmed from downloaded files):**
- transcript (full meeting transcript, speaker-tagged)
- queries (general and specific)
- answers (human-written, query-specific)
- relevant transcript spans (evidence spans for each query/answer)
- official train/validation/test split
**Not available:**
- pre-extracted action items
- pre-extracted decisions
- pre-extracted unresolved issues
- reference summary field (query-answers serve a similar role, but QMSum
  does not ship one canonical whole-meeting summary per meeting)

---

### Dataset: MeetingBank
**Status:** Not acquired (data) in this environment (see DATASET_SOURCES.md).
**Available (per official documentation, not independently verified here):**
- transcript
- reference summary / meeting minutes
- meeting ID and metadata (city, date, etc.)
- official train/validation/test split
**Not available / not confirmed:**
- action items, owners, deadlines
- decisions
- unresolved issues

---

### Dataset: ICSI
**Status:** Not acquired in this environment (see DATASET_SOURCES.md).
**Available (per official documentation, not independently verified here):**
- transcripts
- contributed annotation layers (topic, dialogue act — varies by
  contribution)
**Not available / not confirmed:**
- action items, owners, deadlines
- decisions, unresolved issues (not shipped pre-extracted)

---

### Dataset: ELITR-Bench
**Status:** Partially acquired (questions/answers yes, transcripts no).
**Available (confirmed from downloaded files):**
- long-context questions (36 meeting records, dev + test2 splits, QA and
  conversational formats)
- ground-truth answers
- question metadata (question type, answer position in transcript)
**Not available (in this download):**
- the underlying meeting transcripts themselves (hosted separately on
  LINDAT, not reachable from this sandbox — see DATASET_SOURCES.md)
- action items, decisions, unresolved issues (out of scope for this
  benchmark; it targets QA/long-context retrieval, not minutes generation)

---

### Dataset: MISeD
**Status:** Acquired.
**Available (confirmed from downloaded files):**
- information-seeking dialogs (query/response turns) grounded in AMI/ICSI
  meeting transcript segments
- transcript segments (embedded directly in each record — self-contained)
- source corpus attribution (AMI or ICSI, inferred from meeting ID format)
- official train/validation/test split
- a separate fully-manual "WOZ" variant (`woz/woz.jsonl`)
**Not available:**
- action items, owners, deadlines
- decisions
- unresolved issues
- whole-meeting reference summaries

---

### Dataset: Student Club Meeting Evaluation Dataset (project-created)
**Status:** Created (project-original, not a public benchmark).
**Available (confirmed from generated files):**
- transcript (synthetic multi-speaker dialogue)
- summary (auto-generated one-sentence summary per meeting)
- key_topics
- action_items (task, owner, deadline, evidence, confidence) — including
  deliberately missing owners, missing deadlines, and ambiguous deadlines
  to stress-test extraction robustness
- decisions (decision, evidence)
- unresolved_issues (issue, evidence)
- category label (9 student-club categories)
- train_dev/validation/test split (49/10/11)
- every evidence field is a verbatim substring of its transcript (verified
  programmatically, 454/454 evidence items pass, 0 errors)

---

## Field-availability matrix

| Dataset | transcript | summary | actions | owners | deadlines | decisions | issues | evidence | split |
|---|---|---|---|---|---|---|---|---|---|
| AMI | (not acquired) | (not acquired) | – | – | – | – | – | – | (not acquired) |
| QMSum | yes | – (query/answer instead) | – | – | – | – | – | yes (spans) | yes |
| MeetingBank | (not acquired) | (not acquired) | – | – | – | – | – | – | (not acquired) |
| ICSI | (not acquired) | (not acquired) | – | – | – | – | – | – | (not acquired) |
| ELITR-Bench | no (blocked) | – | – | – | – | – | – | – (QA only) | yes |
| MISeD | yes | – | – | – | – | – | – | – (dialog only) | yes |
| Student Club | yes | yes | yes | yes | yes | yes | yes | yes | yes |

"–" = the dataset's own design does not include this field, not a download
gap. "(not acquired)" = blocked by sandbox network policy; unknown/assumed
per official docs only, not verified.
