# Qwen 2.5 3B Benchmark Report: SC001–SC010 Evaluation

> **Model Tested**: `qwen2.5:3b` (via local Ollama, 3.1B parameters, 4-bit quantized `Q4_K_M`, temperature 0.0)  
> **Evaluation Dataset**: `datasets/01_PRIMARY/student_club` (`SC001` through `SC010`)  
> **Script**: [`eval_qwen_SC001_SC010.py`](file:///r:/S5%20mini%20datasets/eval_qwen_SC001_SC010.py) importing `build_prompt()` from [`test_qwen_inference.py`](file:///r:/S5%20mini%20datasets/test_qwen_inference.py)  
> **Raw Results Artifact**: [`qwen_eval_SC001_SC010_raw.json`](file:///r:/S5%20mini%20datasets/qwen_eval_SC001_SC010_raw.json)  

---

## 1. Executive Summary

The batch benchmark across all 10 student club primary meetings (**SC001 through SC010**) was executed to completion using the identical 10-rule structured prompt established for SC001.

| Metric | Result |
|---|---|
| **Meetings Processed** | **10 / 10 (100%)** |
| **JSON Parse Failures** | **0 / 10 (0.0%)** |
| **Summary Availability** | **10 / 10 (100%)** |
| **Total Inference Time** | **91.3s** |
| **Average Latency / Meeting** | **9.1s** (Range: 7.5s – 14.8s) |
| **Hallucinated Owners** | **0** |
| **Hallucinated Deadlines** | **0** |
| **Action Items Semantic Macro F1** | **0.8205** (Micro F1: **0.8052**) |
| **Decisions Semantic Macro F1** | **0.8633** (Micro F1: **0.8571**) |
| **Unresolved Issues Semantic Macro F1** | **0.7533** (Micro F1: **0.7647**) |

---

## 2. Per-Meeting Results Breakdown

| Meeting | Latency (s) | AI (Pred/GT) | AI Lex F1 | AI Sem F1 | Dec (Pred/GT) | Dec Lex F1 | Dec Sem F1 | Iss (Pred/GT) | Iss Lex F1 | Iss Sem F1 |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **SC001** | 14.75s | 3 / 3 | 1.0000 | 1.0000 | 1 / 1 | 1.0000 | 1.0000 | 2 / 2 | 0.5000 | 1.0000 |
| **SC002** | 8.58s | 5 / 4 | 0.6667 | 0.6667 | 2 / 1 | 0.6667 | 0.6667 | 2 / 1 | 0.0000 | 0.6667 |
| **SC003** | 9.16s | 4 / 4 | 0.7500 | 0.7500 | 1 / 1 | 1.0000 | 1.0000 | 2 / 2 | 0.0000 | 1.0000 |
| **SC004** | 8.03s | 4 / 4 | 0.7500 | 0.7500 | 2 / 2 | 1.0000 | 1.0000 | 1 / 1 | 0.0000 | 1.0000 |
| **SC005** | 8.14s | 4 / 3 | 0.5714 | 0.5714 | 2 / 2 | 1.0000 | 1.0000 | 1 / 1 | 0.0000 | 0.0000 |
| **SC006** | 7.45s | 3 / 3 | 1.0000 | 1.0000 | 2 / 2 | 1.0000 | 1.0000 | 1 / 1 | 1.0000 | 1.0000 |
| **SC007** | 7.59s | 3 / 3 | 0.6667 | 1.0000 | 2 / 2 | 1.0000 | 1.0000 | 2 / 1 | 0.6667 | 0.6667 |
| **SC008** | 8.93s | 5 / 4 | 0.6667 | 0.6667 | 2 / 2 | 0.5000 | 0.5000 | 3 / 2 | 0.0000 | 0.8000 |
| **SC009** | 10.39s | 6 / 4 | 0.8000 | 0.8000 | 3 / 2 | 0.8000 | 0.8000 | 3 / 2 | 0.0000 | 0.4000 |
| **SC010** | 8.31s | 4 / 4 | 1.0000 | 1.0000 | 1 / 2 | 0.6667 | 0.6667 | 2 / 2 | 0.0000 | 1.0000 |

---

## 3. Aggregate Performance Metrics

### Action Items
* **Lexical (Jaccard $\ge 0.5$)**:
  * Macro: Precision = **0.7533**, Recall = **0.8333**, F1 = **0.7872**
  * Micro: Precision = **0.7317**, Recall = **0.8333**, F1 = **0.7792** (30 matches / 36 GT)
* **Semantic (`all-MiniLM-L6-v2` $\ge 0.5$)**:
  * Macro: Precision = **0.7867**, Recall = **0.8667**, F1 = **0.8205**
  * Micro: Precision = **0.7561**, Recall = **0.8611**, F1 = **0.8052** (31 matches / 36 GT)

### Decisions
* **Lexical (Jaccard $\ge 0.5$)**:
  * Macro: Precision = **0.8667**, Recall = **0.9000**, F1 = **0.8633**
  * Micro: Precision = **0.8333**, Recall = **0.8824**, F1 = **0.8571** (15 matches / 17 GT)
* **Semantic (`all-MiniLM-L6-v2` $\ge 0.5$)**:
  * Macro: Precision = **0.8667**, Recall = **0.9000**, F1 = **0.8633**
  * Micro: Precision = **0.8333**, Recall = **0.8824**, F1 = **0.8571** (15 matches / 17 GT)

### Unresolved Issues
* **Lexical (Jaccard $\ge 0.5$)**:
  * Macro: Precision = **0.2000**, Recall = **0.2500**, F1 = **0.2167**
  * Micro: Precision = **0.1579**, Recall = **0.2000**, F1 = **0.1765** (3 matches / 15 GT)
* **Semantic (`all-MiniLM-L6-v2` $\ge 0.5$)**:
  * Macro: Precision = **0.7000**, Recall = **0.8500**, F1 = **0.7533**
  * Micro: Precision = **0.6842**, Recall = **0.8667**, F1 = **0.7647** (13 matches / 15 GT)

---

## 4. Key Analytical Findings

### 1. The Lexical vs. Semantic Gap in Unresolved Issues
The sharp divergence between **Lexical F1 (0.2167)** and **Semantic F1 (0.7533)** highlights an artifact of annotation phrasing rather than model error:
* Ground-truth labels frequently use boilerplate full sentences: e.g., `"The auditorium booking remains unresolved."` (5 words).
* Qwen extracts concise noun phrases instructed by the prompt: e.g., `"Auditorium booking"` (2 words).
* Because the token-Jaccard score is $\frac{2}{5} = 0.40$, it falls below the rigid $0.50$ lexical matching cutoff.
* Semantic evaluation correctly recognizes that `"Auditorium booking"` and `"The auditorium booking remains unresolved."` are semantically equivalent, recovering an F1 of **0.7533** (macro) / **0.7647** (micro).

### 2. Zero Hallucinations Across 10 Meetings
* Out of all predicted action items across 10 meetings, **0 owners were hallucinated** and **0 deadlines were hallucinated**.
* Every assigned owner and deadline string existed verbatim in the respective transcript, showing strict adherence to Rules 2, 7, and 8.

### 3. Reliability of JSON Formatting
* Across 10 multi-speaker transcripts, Qwen 2.5 3B achieved a **100% JSON parse rate** with **0 syntax errors**, respecting the requested schema with all 4 categories (`summary`, `action_items`, `decisions`, `unresolved_issues`).

### 4. Fast Local Inference
* Total time for 10 meetings was **91.3 seconds**, averaging **9.1 seconds per meeting**.
* This demonstrates that a compact 3B model running locally via Ollama can perform extraction and summarization at interactive speeds without cloud API dependencies or costs.

---

## 5. Conclusion on Qwen 2.5 3B
Qwen 2.5 3B is highly effective as a local, private extraction engine for structured meeting analysis:
1. **Strong Decision Extraction**: 0.8633 semantic F1 with 90% recall.
2. **Robust Action Item Extraction**: 0.8205 semantic F1 with 86.7% recall and zero owner/deadline hallucinations.
3. **Solid Issue Identification**: 0.7533 semantic F1 (13/15 ground truth issues captured).
4. **Dependable JSON Output**: Zero markdown leaks or parse failures at temperature 0.0.
