# Synthetic Meeting Action-Item Dataset

60 synthetic meeting transcripts (27-78 turns each, ~48 avg, 2,876 turns total) with ground-truth JSON.
10 meeting styles x 3 length tiers (medium / long / very_long), meeting dates 2026-09-01 to 2026-12-19, weekdays only.

Totals: 378 action items (58 unassigned, 61 completed, 59 with vague deadlines), 148 decisions, 213 unresolved issues.

## Files
| Path | Content |
|---|---|
| `dataset.jsonl` | One meeting per line: id, style, tier, meeting_date, weekday, attendees, transcript, ground_truth |
| `transcripts/*.txt` | Same transcripts as text; line 1 is a `#` header with date and attendees |
| `ground_truth/*.json` | Ground truth per meeting |
| `index.csv` | Per-meeting stats (turns, speakers, counts per label type) |
| `seed_cases/seed_cases.jsonl` | 5 hand-written cases (anchor 2026-10-01) for debugging |
| `evaluate.py` | Per-field P/R/F1 scorer |
| `generate_dataset.py` | Regenerate or extend: `python generate_dataset.py --n 100 --seed 7 --out new/` |

## Schema
```json
{"summary": "...",
 "action_items": [{"task": "...", "owner": "Name or null", "deadline": "original phrase or null",
                   "deadline_iso": "YYYY-MM-DD or YYYY-MM-DD/YYYY-MM-DD or null", "status": "pending|completed"}],
 "decisions": ["..."], "unresolved_issues": ["..."]}
```
`deadline_iso` is added to your schema (policy: keep both original phrase and normalized date).

## Deadline policy (anchor = `meeting_date`)
- `tomorrow` / `by tomorrow` = anchor+1; `today` / `by end of day` = anchor; `in two days` = anchor+2
- `by <Weekday>` = first such weekday strictly after the anchor (the generator never uses the anchor's own weekday)
- `by next Friday` = Friday of the following Mon-Sun week
- `next week` = interval Monday/Sunday of the following week; `this weekend` = Sat/Sun of the current week; `next month` = first/last day of next month
- `by the end of the month` = last day of the anchor month
- Event-dependent phrases (`after the review`, `once the budget is approved`, `before the demo`, `when the hall is confirmed`) keep the phrase and have `deadline_iso: null`
- After a correction, the final phrase wins (original phrase = corrected one)
- `yesterday` on a completed item = anchor-1

## Annotation rules
- Unassigned tasks ("Someone needs to...", "Who's going to...?") are action items with `owner: null`, never also unresolved issues
- Explicit owner = the person who volunteers, is asked and accepts, or is named ("Karthik will..."); on reassignment the final owner wins
- Hedged talk ("I might...", "We could... if we had more people") is NOT an action item
- A retracted commitment creates no action item; the outcome is a decision ("No catering")
- Proposal rejected + counter ("Maybe X" / "No, let's Y") gives decision Y only
- Tentative leanings or conditional plans ("I lean Postgres, confirm with Ravi", "tentatively Saturday, only if the hall is free") are unresolved issues, not decisions
- Blockers and open questions are unresolved issues, not action items
- Work already done = `completed`

## Hard cases covered
interruptions ("--" cut-offs and resumed deadlines), crosstalk, disfluencies ("Um,", "So,"), corrections, reassignment, noise questions ("Did anyone watch the match?"), deadline phrases with and without ISO resolution.

## Limitations
- Synthetic and templated: language is more regular than real speech, and `summary` is templated (use an LLM judge or manual review rather than ROUGE). Expect real transcripts to score lower.
- Real transcripts must be annotated by hand; use this set for regression and ablation, and a smaller real set for final numbers.

## Scoring
```
python evaluate.py dataset.jsonl --self-test
python evaluate.py dataset.jsonl predictions.jsonl --errors 5
```
Predictions: one line per meeting, `{"id": "meeting_001", "prediction": {...same schema...}}`.
Reports loose action F1 (task match only), strict action F1 (task + owner + deadline_iso + status), decision F1, unresolved F1, and balanced F1 (mean of the three fields). Matching is fuzzy token overlap (`--thr 0.6`).
