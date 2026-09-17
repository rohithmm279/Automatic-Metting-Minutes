# Prompt V2 Controlled Experiment Report

> **Model**: `qwen2.5:3b` (via local Ollama, temperature 0.0)  
> **Experiment Scope**: 14 Affected Meetings (`SC012`, `SC016`, `SC018`, `SC025`, `SC030`, `SC033`, `SC037`, `SC043`, `SC049`, `SC054`, `SC056`, `SC059`, `SC060`, `SC064`)  
> **Script**: [`eval_qwen_prompt_v2_affected.py`](file:///r:/S5%20mini%20datasets/eval_qwen_prompt_v2_affected.py)  
> **Artifacts**: [`qwen_eval_prompt_v2_affected_raw.json`](file:///r:/S5%20mini%20datasets/qwen_eval_prompt_v2_affected_raw.json), [`qwen_eval_prompt_v2_affected_metrics.json`](file:///r:/S5%20mini%20datasets/qwen_eval_prompt_v2_affected_metrics.json)  

---

## 1. Baseline
Production metrics across all 70 meetings (**SC001–SC070**) established by the baseline benchmark:
* **JSON Validity**: 100.0% (70/70)
* **Pydantic Validity**: 100.0% (70/70)
* **Hallucination Rate**: 0.00% (0 owners, 0 deadlines)
* **Action Items Semantic Macro F1**: **0.7591** (Micro: 0.7714) $\ge 0.75$
* **Decisions Semantic Macro F1**: **0.8215** (Micro: 0.8462) $\ge 0.75$
* **Unresolved Issues Semantic Macro F1**: **0.6019** (Micro: 0.6087) $< 0.75$ ⚠️

Across the 14 meetings specifically affected by prompt attractor issues, the baseline V1 metrics were:
* **Issue Semantic Macro F1 (14 meetings)**: **0.1476**
* **Decision Semantic Macro F1 (14 meetings)**: **0.6048**
* **Action Semantic Macro F1 (14 meetings)**: **0.7261**

---

## 2. Experimental Change
In [`prompts_v2.py`](file:///r:/S5%20mini%20datasets/prompts_v2.py), a minimal intervention was implemented to replace concrete illustrative strings with abstract placeholder examples:

1. **Unresolved Issues (Rule 4 & 5)**:
   * Replaced: `["Guest's travel plans", "Budget approval"]`
   * With: `["<Topic or item awaiting resolution>"]`
2. **Decisions (Rule 3 & 5)**:
   * Replaced: `["Finalize the event date"]`
   * With: `["<Confirmed agreement or decision>"]`

All other rules, formatting instructions, JSON schemas, Pydantic validations, preprocessing routines, and Ollama inference settings were kept strictly identical.

---

## 3. Affected Meetings
Detailed per-meeting comparison across the 14 evaluated meetings:

| Meeting ID | V1 Issue F1 | V2 Issue F1 | $\Delta$ Issue | V1 Dec F1 | V2 Dec F1 | $\Delta$ Dec | V1 AI F1 | V2 AI F1 | $\Delta$ AI |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **SC012** | 0.0000 | 0.6667 | **+0.6667** | 1.0000 | 1.0000 | +0.0000 | 0.5714 | 0.8571 | +0.2857 |
| **SC016** | 0.0000 | 0.0000 | +0.0000 | 0.6667 | 0.0000 | **-0.6667** | 0.8000 | 1.0000 | +0.2000 |
| **SC018** | 0.0000 | 1.0000 | **+1.0000** | 0.0000 | 0.0000 | +0.0000 | 1.0000 | 1.0000 | +0.0000 |
| **SC025** | 1.0000 | 0.5000 | **-0.5000** | 0.0000 | 0.0000 | +0.0000 | 1.0000 | 1.0000 | +0.0000 |
| **SC030** | 0.0000 | 0.0000 | +0.0000 | 0.0000 | 0.5000 | **+0.5000** | 1.0000 | 1.0000 | +0.0000 |
| **SC033** | 0.0000 | 0.8000 | **+0.8000** | 1.0000 | 0.5714 | **-0.4286** | 1.0000 | 1.0000 | +0.0000 |
| **SC037** | 0.0000 | 0.6667 | **+0.6667** | 1.0000 | 1.0000 | +0.0000 | 0.5000 | 0.5000 | +0.0000 |
| **SC043** | 0.0000 | 0.0000 | +0.0000 | 1.0000 | 0.0000 | **-1.0000** | 0.6667 | 0.7273 | +0.0606 |
| **SC049** | 0.6667 | 0.5000 | **-0.1667** | 1.0000 | 0.0000 | **-1.0000** | 0.0000 | 0.0000 | +0.0000 |
| **SC054** | 0.0000 | 0.0000 | +0.0000 | 0.0000 | 0.0000 | +0.0000 | 0.8889 | 0.8889 | +0.0000 |
| **SC056** | 0.0000 | 0.0000 | +0.0000 | 1.0000 | 1.0000 | +0.0000 | 1.0000 | 1.0000 | +0.0000 |
| **SC059** | 0.4000 | 0.5000 | **+0.1000** | 0.0000 | 1.0000 | **+1.0000** | 0.6667 | 0.8571 | +0.1904 |
| **SC060** | 0.0000 | 1.0000 | **+1.0000** | 0.8000 | 0.8000 | +0.0000 | 0.5714 | 0.5714 | +0.0000 |
| **SC064** | 0.0000 | 0.2857 | **+0.2857** | 1.0000 | 1.0000 | +0.0000 | 0.5000 | 1.0000 | +0.5000 |

---

## 4. V1 vs V2 Comparison

| Metric | V1 (Baseline) | V2 (Experiment) | Delta ($\Delta$) |
|:---|---:|---:|---:|
| **Issue Semantic Macro F1** | **0.1476** | **0.4228** | **+0.2752** |
| **Action Semantic Macro F1** | **0.7261** | **0.8144** | **+0.0883** |
| **Decision Semantic Macro F1** | **0.6048** | **0.4908** | **-0.1140** |
| **Hallucination Rate** | **0.00%** | **0.00%** | **0.00%** |
| **JSON Validity** | **100.0% (14/14)** | **100.0% (14/14)** | **0.00%** |
| **Pydantic Validity** | **100.0% (14/14)** | **100.0% (14/14)** | **0.00%** |

---

## 5. Failure Analysis

### What was fixed:
1. **Unresolved Issue Grounding Recovered**:
   * In meetings like **SC012, SC018, SC033, SC037, SC060**, V1 output the static attractor strings `["Guest's travel plans", "Budget approval"]`. 
   * In V2, the model stopped outputting this false attractor and correctly extracted the true issues:
     * **SC012**: extracted `"Final headcount confirmation"` (F1: 0.0 $\rightarrow$ 0.67).
     * **SC018**: extracted `"Printing order approval"` (F1: 0.0 $\rightarrow$ 1.00).
     * **SC033**: extracted `"Final headcount confirmation"` and `"Equipment availability confirmation"` (F1: 0.0 $\rightarrow$ 0.80).
     * **SC060**: extracted `"Equipment availability"` (F1: 0.0 $\rightarrow$ 1.00).

### What failed / New failure mode introduced:
1. **Template Regurgitation in Decisions**:
   * In **SC016**, **SC043**, and **SC049**, instead of synthesizing actual meeting decisions, Qwen 2.5:3b literally output:
     ```json
     "decisions": [
       "<Confirmed agreement or decision>"
     ]
     ```
   * In **SC043**, the model also literally output:
     ```json
     "unresolved_issues": [
       "<Topic or item awaiting resolution>"
     ]
     ```
   * Because 3B parameter models have limited meta-prompting comprehension, replacing natural language examples with angled-bracket placeholder tokens (`<...>`) caused the model to treat the placeholder as literal verbatim text to output.
2. **Decision Performance Regression**:
   * As a direct consequence of template regurgitation, Decision Semantic F1 plummeted by **-0.1140** across the affected set (falling from 0.6048 to 0.4908). Specifically:
     * **SC016**: Decision F1 dropped from 0.6667 to 0.0000.
     * **SC043**: Decision F1 dropped from 1.0000 to 0.0000.
     * **SC049**: Decision F1 dropped from 1.0000 to 0.0000.
     * **SC033**: Decision F1 dropped from 1.0000 to 0.5714.

---

## 6. Final Recommendation

**KEEP V1**

### Measured Evidence & Rationale
1. **Decision Degradation Violates Decision Rule**:
   * Under the predetermined decision rule: *"If V2 improves issues but damages Action/Decision performance significantly: KEEP PRODUCTION PROMPT UNCHANGED."*
   * Decision Macro F1 suffered an unacceptable regression of **-0.1140** (with 3 meetings experiencing catastrophic drops to 0.0).
2. **Template Regurgitation Risk**:
   * Outputting literal placeholder tokens (`<Confirmed agreement or decision>`) represents a regression in extraction quality and user experience that cannot be promoted to production.
3. **Action Items & Decisions in Production V1 are Robust**:
   * Baseline V1 achieves **0.7591** Semantic F1 on Action Items and **0.8215** on Decisions across all 70 meetings, both solidly exceeding the 0.75 threshold with 0.00% hallucinations and 100% JSON validity.
   * Modifying the prompt to use angled bracket placeholders introduces prompt regression without sufficient stability.
4. **Future Iteration Path**:
   * If Unresolved Issues are to be tuned in a future phase, the placeholder syntax must avoid angled brackets (`<...>`) and instead provide realistic, non-repeating natural domain-generic sentences (or dynamic few-shot extraction), and undergo a full regression benchmark before any deployment.
