# Qwen 2.5 3B v3 Benchmark Report: SC001-SC070

> **Model**: `qwen2.5:3b` via local Ollama
> **Dataset**: `datasets/01_PRIMARY/student_club`, meetings `SC001`-`SC070`
> **Script**: [eval_qwen_SC001_SC070.py](eval_qwen_SC001_SC070.py)
> **Raw results**: [qwen_eval_SC001_SC070_v3_raw.json](qwen_eval_SC001_SC070_v3_raw.json)
> **Metrics**: [qwen_eval_SC001_SC070_v3_metrics.json](qwen_eval_SC001_SC070_v3_metrics.json)
> **Controls**: timeout `120s`, output cap `768` tokens, temperature `0.0`

## Final Result

The benchmark completed all 70 meetings. Fifteen initial Ollama connection failures were retried after correcting checkpoint resume logic; the final artifact contains successful results for every meeting.

| Metric | Result |
|---|---:|
| Meetings evaluated | **70 / 70** |
| JSON validity | **100.0%** |
| Pydantic validity | **100.0%** |
| Summary availability | **100.0%** |
| Total inference latency | **755.71s** |
| Average latency | **10.80s / meeting** |
| Hallucinated owners/deadlines | **0** |

## Quality Metrics

Scores use one-to-one semantic matching with threshold `>= 0.5`.

| Category | Macro F1 | Micro F1 | Matches |
|---|---:|---:|---:|
| Action items | **0.7721** | **0.7625** | 191 / 243 ground-truth items |
| Decisions | **0.8530** | **0.8254** | 104 / 113 ground-truth items |
| Unresolved issues | **0.6929** | **0.7220** | 74 / 98 ground-truth items |

Action-item and decision macro F1 exceed the `0.75` target. Unresolved-issue F1 remains below target and is the primary quality gap.

## Observations

- Structured output reliability is complete: no JSON parse failures and no Pydantic validation failures in the final run.
- The model produces no detected owner or deadline hallucinations.
- Decisions are the strongest category, with macro semantic F1 of `0.8530`.
- Unresolved issues remain harder to extract consistently, with macro semantic F1 of `0.6929`.
- Lexical issue matching is much lower than semantic matching, indicating paraphrase and normalization sensitivity rather than only missing issue extraction.
- Lowest semantic action-item cases include `SC028`, `SC034`, and `SC005`; lowest decision cases include `SC061` and `SC045`; unresolved-issue performance is weakest in several meetings with zero issue matches.

## Resume Fix

The benchmark checkpoint previously treated any record containing `parse_ok` as complete, including `parse_ok: false`. The resume condition now caches only records where `parse_ok is True`, allowing transient Ollama failures to be retried safely.

## Recommendation

Use the v3 artifacts as the authoritative Qwen SC001-SC070 benchmark. Keep the production prompt unchanged for this benchmark comparison. Investigate unresolved-issue extraction separately, especially prompt examples and issue phrasing, before using that category as a production-quality gate.
