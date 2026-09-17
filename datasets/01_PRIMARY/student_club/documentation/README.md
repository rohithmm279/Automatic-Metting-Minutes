# Student Club Meeting Evaluation Dataset

**Student Club Meeting Evaluation Dataset — Project-created dataset**
(NOT an existing public benchmark.)

70 synthetic multi-speaker meeting transcripts across 9 student-club
categories (event_planning, technical_club, cultural_club,
project_meetings, recruitment, budget_finance, workshops_seminars,
competitions, mixed), generated deterministically (random seed=42) by
scripts/generate_student_club_dataset.py.

Every ground-truth action item, decision, and unresolved issue includes
an `evidence` field that is a verbatim substring of its transcript —
verified programmatically (454/454 evidence items pass, 0 errors).

Split: train_dev/validation/test = 49/10/11 (~70/15/15%).

Files:
  transcripts/SC001.txt ... SC070.txt
  ground_truth/SC001.json ... SC070.json
  metadata.csv
  statistics.json
