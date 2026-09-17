# Gemini Baseline Benchmark Report: SC001–SC070 Evaluation

> **Model Tested**: `gemini-3.5-flash` (via Google Gemini Developer API, temperature 0.0)  
> **Evaluation Dataset**: `datasets/01_PRIMARY/student_club` (`SC001` through `SC070`, 70 meetings attempted)  
> **Benchmark Script**: [`eval_gemini_SC001_SC070.py`](file:///r:/S5%20mini%20datasets/eval_gemini_SC001_SC070.py)  
> **Raw Results Artifact**: [`gemini_eval_SC001_SC070_raw.json`](file:///r:/S5%20mini%20datasets/gemini_eval_SC001_SC070_raw.json)  
> **Metrics Artifact**: [`gemini_eval_SC001_SC070_metrics.json`](file:///r:/S5%20mini%20datasets/gemini_eval_SC001_SC070_metrics.json)  
> **Date**: 2026-09-15  
> **Status**: ⚠️ PARTIAL — Free-Tier Daily Quota Exhausted

---

## 1. Objective

Obtain an unbiased Gemini baseline evaluation on the same SC001–SC070 dataset used for the verified Qwen 2.5 3B benchmark. The goal is a direct, fair comparison using identical:
- Transcript preprocessing (`TranscriptProcessor.clean_transcript`)
- Identical 10-rule structured extraction prompt
- Identical Pydantic validation (`MeetingValidator`, `MeetingOutput`)
- Identical scoring: Lexical Jaccard + Semantic (`all-MiniLM-L6-v2`, threshold ≥ 0.5)
- Identical ground truth
- Identical hallucination checks

---

## 2. Dataset

70 meetings SC001–SC070 were all queued for evaluation. The checkpoint infrastructure recorded all 70 meeting attempts.

| Range | Queued | Evaluated | Quota-Failed |
|:---|:---:|:---:|:---:|
| SC001–SC007 | 7 | 6 | 1 (SC001 – 503 on first call) |
| SC008–SC070 | 63 | 0 | 63 (daily quota exhausted) |
| **Total** | **70** | **6** | **64** |

---

## 3. Model & Configuration

| Parameter | Value |
|:---|:---|
| **Model** | `gemini-3.5-flash` |
| **Provider** | Google Gemini Developer API (`google-genai` SDK v2.22.0) |
| **Temperature** | 0.0 (deterministic) |
| **API Key Source** | `GEMINI_API_KEY` env variable / `backend/.env` |
| **SDK** | `google-genai==2.22.0` (already installed in project venv) |
| **Daily Quota** | **20 requests/day/model (Free Tier)** |
| **Rate Limit Hit** | After meeting SC007 (request 7) — quota at 20 req/day |

---

## 4. Critical Blocker: Free-Tier Daily Quota

> [!CAUTION]
> **The Gemini API key being used is a Free Tier key with a hard limit of 20 requests per day per model (`GenerateRequestsPerDayPerProjectPerModel-FreeTier`).**
>
> SC001 failed on the first attempt due to model overload (`503 UNAVAILABLE`), which consumed request 1. SC002–SC007 (6 meetings) succeeded. SC008 onward were blocked by quota exhaustion (`429 RESOURCE_EXHAUSTED`).
>
> **64 out of 70 meetings could not be evaluated.**
>
> The full SC001–SC070 benchmark CANNOT be completed on a Free Tier key. **A paid Gemini API key is required to run the complete 70-meeting evaluation.**

---

## 5. Partial Results — 6 Evaluated Meetings (SC002–SC007)

> [!WARNING]
> The following metrics are computed over **6 meetings only** (SC002, SC003, SC004, SC005, SC006, SC007). They are **NOT representative** of performance across all 70 meetings and must **NOT** be used to make a production decision.

| Metric | Value | Notes |
|:---|:---:|:---:|
| **Meetings Successfully Evaluated** | **6 / 70** | Quota blocked remaining 64 |
| **JSON Parse Failures** | **0 / 6 (0.0%)** | Perfect schema compliance |
| **Pydantic Validation Success** | **6 / 6 (100.0%)** | No schema violations |
| **Summary Availability** | **6 / 6 (100.0%)** | All summaries present |
| **Total Successful Inference Time** | **212.1s** | 6 meetings |
| **Average Latency / Meeting** | **35.34s** | ~4.6× slower than Qwen (7.65s) |
| **Hallucinated Owners** | **0** | 0.00% hallucination rate |
| **Hallucinated Deadlines** | **0** | 0.00% hallucination rate |
| **Action Items Semantic Macro F1** | **0.9206** *(partial)* | Based on 6 meetings only |
| **Decisions Semantic Macro F1** | **1.0000** *(partial)* | Based on 6 meetings only |
| **Unresolved Issues Semantic Macro F1** | **0.9111** *(partial)* | Based on 6 meetings only |

---

## 6. Per-Meeting Detail (6 Evaluated Meetings)

| Meeting | Latency (s) | AI Sem F1 | Dec Sem F1 | Iss Sem F1 | Halluc | Pydantic |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **SC002** | ~35s | **1.0000** | **1.0000** | **1.0000** | 0 | ✅ |
| **SC003** | ~35s | **0.8571** | **1.0000** | **0.8000** | 0 | ✅ |
| **SC004** | ~35s | **1.0000** | **1.0000** | **1.0000** | 0 | ✅ |
| **SC005** | ~35s | **1.0000** | **1.0000** | **1.0000** | 0 | ✅ |
| **SC006** | ~35s | **1.0000** | **1.0000** | **1.0000** | 0 | ✅ |
| **SC007** | ~35s | **0.6667** | **1.0000** | **0.6667** | 0 | ✅ |

---

## 7. Comparison with Qwen 2.5 3B (SC001–SC070, 70 meetings)

> [!IMPORTANT]
> This comparison is **not valid as a full benchmark comparison** because Gemini was only tested on 6 meetings. The figures are included for orientation only. A complete 70-meeting Gemini evaluation is required before any production decision.

| Metric | Qwen 2.5 3B (70/70) | Gemini 3.5 Flash (6/70) | Notes |
|:---|:---:|:---:|:---|
| **Meetings Evaluated** | **70 / 70** | **6 / 70** | ⚠️ Not comparable |
| **JSON Validity** | 100.0% | 100.0% | Both perfect on completed meetings |
| **Pydantic Validity** | 100.0% | 100.0% | Both perfect on completed meetings |
| **Summary Availability** | 100.0% | 100.0% | Both 100% on completed meetings |
| **Action Items Sem Macro F1** | **0.7591** | **0.9206** *(6 mtgs)* | Gemini higher, sample too small |
| **Decisions Sem Macro F1** | **0.8215** | **1.0000** *(6 mtgs)* | Gemini higher, sample too small |
| **Issues Sem Macro F1** | **0.6019** | **0.9111** *(6 mtgs)* | Gemini higher, sample too small |
| **Hallucination Rate** | **0.00%** | **0.00%** | Both zero hallucinations |
| **Avg Latency / Meeting** | **7.65s** | **35.34s** | Qwen ~4.6× faster |
| **Cost** | Free (local) | Free tier (quota limited) | Paid key needed for production |

---

## 8. Smoke Test Result

The smoke test (SC001) was separately confirmed via the `--smoke` flag before the full run:

```
Meeting ID          : SC001
Model               : gemini-3.5-flash
Latency             : 37.03s
JSON Parse OK       : True
Pydantic Valid      : True
Summary Present     : True
Action Items F1     : Lex=1.0000, Sem=1.0000
Decisions F1        : Lex=1.0000, Sem=1.0000
Unresolved Issues F1: Lex=0.5000, Sem=1.0000
Hallucinations      : 0
```

The full-run attempt of SC001 itself failed with a transient `503 UNAVAILABLE` error during the main benchmark, so SC001 is counted as failed in the checkpoint (though the smoke test confirms Gemini generates correct structured output for it).

---

## 9. Failure Patterns in 6 Evaluated Meetings

Within the 6 meetings that completed:
- **Zero JSON parse failures** — Gemini produced correctly formatted JSON in all 6 cases.
- **Zero Pydantic validation errors** — All outputs matched the `MeetingOutput` schema.
- **Zero hallucinations** — No invented owners or deadlines in any of the 6 meetings.
- **Minor precision drop in SC007 Action Items** (F1=0.6667): Gemini extracted 3 items, ground truth has 3, one was not semantically matched — this could reflect a genuine extraction miss but is insufficient evidence in isolation.

---

## 10. What Is Required to Complete the Benchmark

### Option A: Upgrade to Gemini Paid API
- A paid Google AI / Google Cloud project with billing enabled allows thousands of requests per day.
- Re-run `eval_gemini_SC001_SC070.py` with the upgraded key — the checkpoint ensures SC002–SC007 will be loaded from cache and only SC001 + SC008–SC070 (64 meetings) will be re-queried.

### Option B: Spread Across Multiple Days (Free Tier)
- Free tier = 20 requests/day. Running 64 remaining meetings requires 4 more days.
- Add inter-request rate limiting (`time.sleep(90)` between calls) to stay within quota.
- Not practical for a project benchmark.

---

## 11. Production Safety Verification

The following production files were **NOT modified**:

| File | Status |
|:---|:---:|
| `backend/ai/prompts.py` (production Qwen prompt) | ✅ Unmodified |
| `backend/ai/orchestrator.py` | ✅ Unmodified |
| `backend/ai/validator.py` | ✅ Unmodified |
| `backend/app/` (FastAPI routes) | ✅ Unmodified |
| `backend/database/` (SQLite) | ✅ Unmodified |
| `frontend/` (React) | ✅ Unmodified |
| `qwen_eval_SC001_SC070_raw.json` | ✅ Unmodified |
| `QWEN_SC001_SC070_BENCHMARK_REPORT.md` | ✅ Unmodified |

New files created (isolated, benchmark-only):
- [`eval_gemini_SC001_SC070.py`](file:///r:/S5%20mini%20datasets/eval_gemini_SC001_SC070.py)
- [`gemini_eval_SC001_SC070_raw.json`](file:///r:/S5%20mini%20datasets/gemini_eval_SC001_SC070_raw.json)
- [`gemini_eval_SC001_SC070_metrics.json`](file:///r:/S5%20mini%20datasets/gemini_eval_SC001_SC070_metrics.json)
- [`gemini_eval_SC001_SC070_checkpoint.json`](file:///r:/S5%20mini%20datasets/gemini_eval_SC001_SC070_checkpoint.json)

---

## 12. Recommendation

**CANNOT RECOMMEND GEMINI YET — Insufficient Data.**

Based on the partial results across 6 meetings, Gemini `3.5-flash` shows very promising output quality (0.9206 Action F1, 1.0000 Decision F1, 0.9111 Issue F1 on the 6 completed meetings, and zero hallucinations). However:

1. **6 out of 70 meetings is not a representative benchmark.** The SC001–SC010 range covers simpler, well-structured transcripts. Harder meetings (SC011–SC070) are where Qwen's performance dropped and where meaningful comparison would occur.
2. **Gemini is 4.6× slower** (35.34s vs 7.65s avg) on the free tier, which has rate-limiting implications for production use.
3. **The free-tier quota is a hard blocker.** A paid API key is required before any production decision.

### Recommended Next Step

> Upgrade the Gemini API key to a paid plan and re-run `eval_gemini_SC001_SC070.py`. The checkpoint will resume from SC008 automatically. Only 64 additional API calls are needed to complete the full benchmark.

**Until the full 70-meeting benchmark is available, Qwen 2.5 3B (local, free, verified 70/70) remains the production AI.**
