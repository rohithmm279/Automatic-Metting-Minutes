# DATASET_SOURCES.md

Record of every dataset considered for the Automatic Meeting Minutes &
Action Item Generator for Student Clubs project: where it comes from, what
was actually downloaded, and what was intentionally skipped.

**Environment note:** dataset acquisition was performed inside a sandboxed
environment whose outbound network access is restricted to an allowlist of
domains (github.com, codeload.github.com, pypi.org, npmjs.com, and similar
package registries/mirrors). Any source below marked "NOT ACQUIRED — network
blocked" was not reachable from this sandbox; it is not a licensing or
availability problem. Exact instructions to acquire those sources from a
normal internet connection are provided in each dataset's `raw/<name>/`
folder.

---

## 1. AMI Meeting Corpus

- **Official source URL:** https://groups.inf.ed.ac.uk/ami/download/
- **Download method attempted:** direct HTTPS request from the sandbox.
- **Result:** HTTP 403 — domain not on the sandbox network allowlist.
- **Version/date:** Manual annotations v1.6.2 (targeted, not obtained).
- **License:** AMI Corpus is released under a Creative Commons license
  requiring attribution (see AMI site for exact terms); not independently
  re-verified here since the corpus itself was not downloaded.
- **What was downloaded:** Nothing.
- **What was intentionally NOT downloaded:** The full audio/video collection
  (never intended — spec explicitly excludes it).
- **Number of examples:** N/A (not acquired).
- **File size:** N/A.
- **Processing performed:** None.
- **Citation:** Carletta, J. et al. (2005). "The AMI Meeting Corpus: A
  Pre-announcement." MLMI 2005.
- **Status:** NOT ACQUIRED — network blocked. See
  `datasets/raw/ami/NOT_DOWNLOADED.txt` for exact re-acquisition steps.

---

## 2. QMSum

- **Official source URL:** https://github.com/Yale-LILY/QMSum
- **Download method:** `git clone --depth 1` (GitHub is on the allowlist).
- **Result:** SUCCESS.
- **Version/date:** Latest `main` branch at time of cloning (2026-08-21).
- **License:** MIT License (see `datasets/raw/qmsum/LICENSE`).
- **What was downloaded:** Full `data/` folder (Academic, Committee, Product
  domains, each with train/val/test JSON files) — official train/val/test
  splits preserved unmodified. The `figures/` and `model_output/` folders
  from the repo (irrelevant to dataset content) and `.git` history were
  removed to save space.
- **What was intentionally NOT downloaded:** Nothing relevant was skipped;
  QMSum ships as data files directly in the repo (no separate large media).
- **Number of examples:** 232 meetings, 1,810 query-summary pairs (spec
  cites 1,808; the small discrepancy is likely due to a minor difference in
  how empty/duplicate queries are counted across repo versions).
- **File size:** ~120 MB (after trimming non-data folders).
- **Processing performed:** Converted into the project's common JSON format
  per split (`datasets/processed/qmsum/qmsum_{train,validation,test}.jsonl`)
  via `process_qmsum.py`. Raw files were not modified.
- **Citation:** Zhong, M. et al. (2021). "QMSum: A New Benchmark for
  Query-based Multi-domain Meeting Summarization." NAACL 2021.
- **Status:** ACQUIRED.

---

## 3. MeetingBank

- **Official source URL (utils/code):** https://github.com/YebowenHu/MeetingBank-utils
- **Official source URL (data):** https://huggingface.co/datasets/huuuyeah/meetingbank
- **Official source URL (transcripts, alt.):** https://zenodo.org/record/7989108
- **Download method attempted:** `git clone` for the utils repo (succeeded,
  GitHub allowlisted); direct HTTPS requests to huggingface.co and
  zenodo.org for the actual data (both returned HTTP 403 — not allowlisted).
- **Result:** Utility scripts only; NO dataset content acquired.
- **License:** MeetingBank is released for research use; see the
  HuggingFace dataset card for exact terms (not independently re-verified
  here since the data was not downloaded).
- **What was downloaded:** `MeetingBank-utils` repo (`load_data.py`,
  `ResultsEval.py`, `utils/MoverScore.py`, README) — code only.
- **What was intentionally NOT downloaded:** The transcripts/summaries/
  metadata themselves (blocked by network policy, not by choice), and the
  video/audio archives (never intended — spec explicitly excludes them).
- **Number of examples:** N/A (not acquired). Per the dataset's own
  documentation: 1,366 meetings, 6,892 segment-level summarization
  instances.
- **File size:** ~232 KB (utils repo only).
- **Processing performed:** None (no data to process).
- **Citation:** Hu, Y. et al. (2023). "MeetingBank: A Benchmark Dataset for
  Meeting Summarization." ACL 2023.
- **Status:** NOT ACQUIRED (data) — network blocked. See
  `datasets/raw/meetingbank/NOT_DOWNLOADED.txt` for exact re-acquisition
  steps (three lines of Python once `huggingface.co` is reachable).

---

## 4. ICSI Meeting Corpus

- **Official source URL:** https://groups.inf.ed.ac.uk/ami/icsi/download/
- **Download method attempted:** direct HTTPS request from the sandbox.
- **Result:** HTTP 403 — same blocked host family as AMI.
- **License:** Distributed under similar terms to AMI; not independently
  re-verified here since the corpus itself was not downloaded.
- **What was downloaded:** Nothing.
- **What was intentionally NOT downloaded:** Full audio archive (never
  intended).
- **Number of examples:** N/A (not acquired).
- **File size:** N/A.
- **Processing performed:** None.
- **Citation:** Janin, A. et al. (2003). "The ICSI Meeting Corpus." ICASSP
  2003.
- **Status:** NOT ACQUIRED — network blocked. See
  `datasets/raw/icsi/NOT_DOWNLOADED.txt`.

---

## 5. ELITR-Bench

- **Official source URL:** https://github.com/utter-project/ELITR-Bench
- **Download method:** `git clone --depth 1` (GitHub allowlisted).
- **Result:** SUCCESS for the benchmark questions/answers; the underlying
  meeting transcripts are a SEPARATE download (ELITR-minuting-corpus,
  hosted on LINDAT, `lindat.mff.cuni.cz`), which is NOT on the allowlist,
  so transcripts themselves were not obtained.
- **Version/date:** Latest `main` branch at time of cloning (2026-08-21),
  includes the December 2024 Czech-language update.
- **License:** Code under `LICENSE-CODE.txt`; data under `LICENSE-DATA.txt`
  (CC BY 4.0 — Creative Commons Attribution).
- **What was downloaded:** `data.zip` (26.6 KB, password-protected —
  extracted using the password `utter`, which is openly published in the
  repo's own README as a documented anti-contamination step, not an access
  restriction — see spec section: "follow repository instructions exactly").
  This contains the benchmark questions, ground-truth answers, and
  metadata for the `dev` and `test2` splits, in both QA and conversational
  (`conv`) formats.
- **What was intentionally NOT downloaded:** `generated-responses.zip`
  (existing model outputs — not needed at this stage per spec section 6);
  `czech.zip` (translation variant, out of scope for now); the
  `ELITR-minuting-corpus` transcripts (blocked — hosted on `lindat.mff.cuni.cz`,
  not on the sandbox allowlist).
- **Number of examples:** 36 meeting records (10 dev QA + 8 test2 QA + 10 dev
  conv + 8 test2 conv), spanning dozens of individual questions.
- **File size:** ~180 KB (questions/answers only; no transcripts).
- **Processing performed:** Converted into the project's common JSON format
  (`datasets/processed/elitr_bench/elitr_bench_all.jsonl`) via
  `process_elitr_bench.py`. The `transcript` field is `null` for every
  record until the LINDAT corpus is joined in outside this sandbox.
- **Citation:** Thonet, T. et al. (2024). "ELITR-Bench: A Meeting Assistant
  Benchmark for Long-Context Language Models."
- **Status:** PARTIALLY ACQUIRED (questions/answers yes, transcripts no).

---

## 6. MISeD (Meeting Information Seeking Dialogs)

- **Official source URL:** https://github.com/google-research-datasets/MISeD
- **Download method:** `git clone --depth 1` (GitHub allowlisted).
- **Result:** SUCCESS.
- **Version/date:** Latest `main` branch at time of cloning (2026-08-21).
- **License:** No standalone LICENSE file was present in the cloned repo at
  clone time; check the repository directly before redistribution.
- **What was downloaded:** `mised/{train,validation,test}.jsonl` (432 dialogs
  total, matching the spec's expected count) and `woz/woz.jsonl` (the fully
  manual WOZ variant, included since it shipped in the same repo).
- **What was intentionally NOT downloaded:** Nothing — the full repo content
  is textual and was pulled in its entirety (~33 MB after removing `.git`).
- **Number of examples:** 432 dialogs (303 train / 63 validation / 66 test).
- **File size:** ~33 MB.
- **Processing performed:** Converted into the project's common JSON format
  (`datasets/processed/mised/mised_{train,validation,test}.jsonl`) via
  `process_mised.py`.
- **IMPORTANT CORRECTION vs. original task assumption:** the spec assumed
  MISeD's transcripts were derived from QMSum. On inspection, each MISeD
  record's `meeting.meetingId` follows AMI (`ES2004a`) or ICSI (`Bmr006`,
  `Bro004`) naming conventions, not QMSum, and each record embeds its own
  transcript segments directly (self-contained, not a reference to an
  external QMSum file). This is documented here rather than silently
  followed, per the "do not invent/assume relationships" principle.
- **Citation:** Golany, L. et al. (2024). "Efficient Data Generation for
  Source-grounded Information-seeking Dialogs: A Use Case for Meeting
  Transcripts." Findings of EMNLP 2024.
- **Status:** ACQUIRED.

---

## 7. Student Club Meeting Evaluation Dataset (project-created)

- **Source:** Not a public dataset. Synthesized for this project by a
  deterministic Python generator (`datasets/student_club/scripts/
  generate_student_club_dataset.py`, fixed random seed = 42).
- **License:** Original project content — no third-party license applies.
  Free to redistribute as part of this project.
- **What was created:** 70 synthetic multi-speaker meeting transcripts
  (`SC001`–`SC070`) across 9 student-club categories, each with a matching
  ground-truth JSON file containing summary, key topics, action items
  (task/owner/deadline/evidence/confidence), decisions, and unresolved
  issues. Every evidence string is a programmatically verified verbatim
  substring of its transcript (454/454 evidence items verified, 0 errors).
- **Number of examples:** 70 meetings — 243 action items, 113 decisions, 98
  unresolved issues.
- **File size:** ~239 KB.
- **Processing performed:** Generation + automated evidence-grounding
  verification + train_dev/validation/test split (49/10/11, ~70/15/15%).
- **Status:** CREATED (clearly labeled "Student Club Meeting Evaluation
  Dataset — Project-created dataset", per spec section 8).

---

## Summary table

| Dataset | Status | Reason if not acquired |
|---|---|---|
| AMI | NOT ACQUIRED | groups.inf.ed.ac.uk not reachable from sandbox |
| QMSum | ACQUIRED | — |
| MeetingBank | NOT ACQUIRED (data) | huggingface.co / zenodo.org not reachable from sandbox |
| ICSI | NOT ACQUIRED | groups.inf.ed.ac.uk not reachable from sandbox |
| ELITR-Bench | PARTIAL (QA yes, transcripts no) | transcripts hosted on lindat.mff.cuni.cz, not reachable |
| MISeD | ACQUIRED | — |
| Student Club Dataset | CREATED | project-original, not a download |
