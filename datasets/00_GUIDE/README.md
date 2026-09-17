# Automatic Meeting Minutes & Action Item Generator — Dataset Pack

This folder is a cleaned, organized copy of the datasets contained in the uploaded `Datasets(1).zip`.

## Dataset roles

### 01_PRIMARY
- `student_club`: Primary domain-specific dataset for the project.
  - 70 student-club meetings
  - transcript + summary + key topics
  - action items: task, owner, deadline, evidence, confidence
  - decisions + evidence
  - unresolved issues + evidence
  - train_dev / validation / test split

### 02_BENCHMARKS
- `qmsum`: General meeting understanding / query-based summarization benchmark.
- `meetingbank`: Long-meeting summarization benchmark with transcript + reference summary.

### 03_SUPPLEMENTARY
- `mised`: Information-seeking dialogs grounded in meeting transcript segments. Use only for supplementary meeting QA / retrieval experiments.

### 04_REFERENCE
- `ami`: AMI public manual/annotation corpus supplied in the uploaded archive. Keep as a reference/annotation resource; it is not the same as a ready-made action-item dataset.
- `icsi`: ICSIplus corpus/annotations supplied in the uploaded archive. Keep as a reference/annotation resource.
- `elitr_bench`: ELITR-Bench partial benchmark; QA data is present, while the underlying external transcripts are not included.

## Recommended project order

1. Student Club → main experiments and evaluation.
2. QMSum → external meeting benchmark.
3. MeetingBank → external long-meeting summarization benchmark.
4. MISeD → optional information-seeking / retrieval experiment.
5. AMI / ICSI / ELITR → reference or future experiments.

## Important

Do not train one model by blindly merging all datasets. They have different tasks, schemas, and purposes.
