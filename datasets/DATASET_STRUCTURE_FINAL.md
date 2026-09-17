# Dataset Structure Final

Date: 2026-09-08

## Final root

```
datasets/
├── 00_GUIDE/
├── 01_PRIMARY/
│   └── student_club/
│       ├── transcripts/
│       ├── ground_truth/
│       ├── metadata/
│       └── documentation/
├── 02_BENCHMARKS/
│   ├── meetingbank/
│   └── qmsum/
├── 03_SUPPLEMENTARY/
│   └── mised/
├── 04_REFERENCE/
│   ├── ami/
│   ├── elitr_bench/
│   └── icsi/
├── 99_ARCHIVE_NOTES/
│   └── raw_Datasets/
├── DATASET_AUDIT_BEFORE_REORGANIZATION.md
├── DATASET_REORGANIZATION_PLAN.md
├── DATASET_INVENTORY_FINAL.csv
├── DATASET_STRUCTURE_FINAL.md
├── DATASET_USAGE_MAPPING.md
└── ...
```

## Summary

- Total folders: 233
- Total files: 16784
- Clean dataset root created: datasets/
- Archive preserved unchanged: yes
- ICSI preserved separately under 04_REFERENCE/icsi: yes
- No preprocessing or conversion work started: yes

## Active dataset locations

- Student Club: 01_PRIMARY/student_club
- QMSum: 02_BENCHMARKS/qmsum
- MeetingBank: 02_BENCHMARKS/meetingbank
- MISeD: 03_SUPPLEMENTARY/mised
- AMI: 04_REFERENCE/ami
- ELITR Bench: 04_REFERENCE/elitr_bench
- ICSI: 04_REFERENCE/icsi
- Archive: 99_ARCHIVE_NOTES

## Train / validation / test files retained

- Student Club
  - transcripts/SC001.txt ... SC070.txt
  - ground_truth/SC001.json ... SC070.json
  - metadata.csv
  - documentation/statistics.json

- QMSum
  - processed/qmsum_train.jsonl
  - processed/qmsum_validation.jsonl
  - processed/qmsum_test.jsonl

- MeetingBank
  - train.json
  - validation.json
  - test.json

- MISeD
  - processed/mised_train.jsonl
  - processed/mised_validation.jsonl
  - processed/mised_test.jsonl

## Duplicate relationships found

- Historical raw copies remain in 99_ARCHIVE_NOTES/raw_Datasets.
- These are intentionally not active working data and were left unchanged.
- No active duplicate dataset copies were created during the reorganization.

## Archive status

- 99_ARCHIVE_NOTES was intentionally preserved without modification.
- The archive contains historical and raw dataset snapshots, including AMI, QMSum, MISeD, and aggregated raw folders.
