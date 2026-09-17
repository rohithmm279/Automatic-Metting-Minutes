# Dataset Audit Before Reorganization

Date: 2026-09-08
Scope: `r:\S5 mini datasets\Meeting_Project_Datasets_Organized\Meeting_Project_Datasets`

Status: AUDIT ONLY — no files were moved, renamed, deleted, merged, or modified during this phase.

## 1. Current dataset root

```
Meeting_Project_Datasets/
├── 00_GUIDE/
│   ├── DATASET_CAPABILITIES_original.md
│   ├── DATASET_INVENTORY_original.csv
│   ├── DATASET_SOURCES_original.md
│   ├── DATASET_USAGE_PLAN.md
│   ├── FINAL_STRUCTURE.txt
│   ├── README.md
│   └── ...
├── 01_PRIMARY/
│   └── student_club/
│       ├── README.md
│       ├── metadata.csv
│       ├── statistics.json
│       ├── transcripts/
│       │   ├── SC001.txt
│       │   ├── SC002.txt
│       │   ├── ...
│       │   └── SC070.txt
│       └── ground_truth/
│           ├── SC001.json
│           ├── SC002.json
│           ├── ...
│           └── SC070.json
├── 02_BENCHMARKS/
│   ├── meetingbank/
│   │   ├── README.md
│   │   ├── data_process.ipynb
│   │   ├── train.json
│   │   ├── validation.json
│   │   ├── test.json
│   │   └── project_metadata/
│   └── qmsum/
│       ├── README.md
│       ├── statistics.json
│       ├── metadata/
│       ├── processed/
│       │   ├── qmsum_train.jsonl
│       │   ├── qmsum_validation.jsonl
│       │   └── qmsum_test.jsonl
│       ├── raw/
│       │   ├── data/
│       │   ├── extracted_span/
│       │   └── README.md
│       └── ...
├── 03_SUPPLEMENTARY/
│   └── mised/
│       ├── LICENSE_INFO.txt
│       ├── README.md
│       ├── statistics.json
│       ├── metadata/
│       ├── processed/
│       │   ├── mised_train.jsonl
│       │   ├── mised_validation.jsonl
│       │   └── mised_test.jsonl
│       ├── raw/
│       │   ├── mised/
│       │   ├── woz/
│       │   └── README.md
│       └── ...
├── 04_REFERENCE/
│   ├── ami/
│   │   ├── 00README_MANUAL.txt
│   │   ├── AMI-metadata.xml
│   │   ├── LICENCE.txt
│   │   ├── MANIFEST_MANUAL.txt
│   │   ├── resource.xml
│   │   ├── abstractive/
│   │   ├── argumentation/
│   │   ├── configuration/
│   │   ├── corpusdoc/
│   │   ├── corpusResources/
│   │   ├── decision/
│   │   ├── dialogueActs/
│   │   ├── disfluency/
│   │   ├── extractive/
│   │   ├── focus/
│   │   ├── handGesture/
│   │   ├── headGesture/
│   │   ├── movement/
│   │   ├── namedEntities/
│   │   ├── ontologies/
│   │   ├── participantRoles/
│   │   ├── participantSummaries/
│   │   ├── segments/
│   │   ├── topics/
│   │   ├── words/
│   │   └── youUsages/
│   ├── elitr_bench/
│   │   ├── LICENSE_INFO.txt
│   │   ├── README.md
│   │   ├── statistics.json
│   │   ├── metadata/
│   │   ├── processed/
│   │   └── raw/
│   └── icsi/
│       └── ICSIplus/
└── 99_ARCHIVE_NOTES/
    └── raw_Datasets/
        ├── ALL_PROJECT_DATASETS/
        ├── ALL_QMSum/
        ├── Meeting_Project_Datasets/
        ├── MISeD-main/
        ├── ami_public_manual_1.6.2/
        ├── data/
        ├── data_process.ipynb
        ├── gitattributes
        ├── ICSI_plus_NXT.zip
        ├── README.md
        ├── test.json
        ├── train.json
        ├── validation.json
        └── ...
```

## 2. Top-level dataset inventory

### 00_GUIDE
Purpose: Documentation and metadata pack. Contains original source inventory and usage documentation.

### 01_PRIMARY
- Student Club dataset
- Main active project dataset
- Contains transcripts and programmatically verified ground truth records.

### 02_BENCHMARKS
- MeetingBank
- QMSum

### 03_SUPPLEMENTARY
- MISeD

### 04_REFERENCE
- AMI
- ELITR-Bench
- ICSI

### 99_ARCHIVE_NOTES
Archive and historical raw-copy area. Protected and intentionally excluded from reorganization.

## 3. Nested duplicate wrapper folders and possible duplicates

### Likely duplicate wrapper folders
1. `99_ARCHIVE_NOTES/raw_Datasets/Meeting_Project_Datasets`  
   This appears to be a nested copy of the active dataset root structure, including a second `02_BENCHMARKS/qmsum` and a second `03_SUPPLEMENTARY` structure.

2. `99_ARCHIVE_NOTES/raw_Datasets/MISeD-main`  
   This appears to be a raw source bundle for the same dataset already present in `03_SUPPLEMENTARY/mised`.

3. `99_ARCHIVE_NOTES/raw_Datasets/ALL_PROJECT_DATASETS`  
   This appears to be a historical aggregate or raw copy of earlier dataset combinations.

4. `99_ARCHIVE_NOTES/raw_Datasets/ALL_QMSum`  
   This appears to be a copy of QMSum-related material retained for archive/reference.

5. `99_ARCHIVE_NOTES/raw_Datasets/ami_public_manual_1.6.2`  
   This is a raw AMI archive bundle that mirrors the reference corpus and is retained under archive.

### Duplicate relationship summary
- Active dataset folders are present under `01_PRIMARY`, `02_BENCHMARKS`, `03_SUPPLEMENTARY`, and `04_REFERENCE`.
- Archive contains historical duplicates of the same datasets in `99_ARCHIVE_NOTES/raw_Datasets`.
- The archive copies are not active working data and are intentionally to remain unchanged.

## 4. Existing train / validation / test splits

### Student Club
- Transcript files: `transcripts/SC001.txt` ... `SC070.txt`
- Ground-truth files: `ground_truth/SC001.json` ... `SC070.json`
- Split metadata: `metadata.csv`, `statistics.json`
- Split counts: train_dev = 49, validation = 10, test = 11

### QMSum
- Processed splits:
  - `processed/qmsum_train.jsonl`
  - `processed/qmsum_validation.jsonl`
  - `processed/qmsum_test.jsonl`
- Raw source structure also contains domain-wise train/validation/test organization inside `raw/data/...`.

### MISeD
- Processed splits:
  - `processed/mised_train.jsonl`
  - `processed/mised_validation.jsonl`
  - `processed/mised_test.jsonl`
- Raw source folders include `woz` and original raw dataset bundle under archive.

### MeetingBank
- Split files:
  - `train.json`
  - `validation.json`
  - `test.json`

### Archive raw copies
- `99_ARCHIVE_NOTES/raw_Datasets/.../train.json`, `validation.json`, and `test.json` also exist as historical or raw copies, but they are not part of the active working structure and are intentionally excluded from moves.

## 5. Audit conclusion

The dataset collection already has a valid active working structure, but it also contains nested archive duplicates and historical wrapper folders. The duplicate copies are not required for the working dataset root, but they are being preserved exactly as-is because the safety rules prohibit deleting or modifying them during this audit phase.

## 6. Safety status

- No dataset files were deleted.
- No raw files were modified.
- No dataset files were moved.
- No train/validation/test files were altered.
- No content in `99_ARCHIVE_NOTES` was changed.
- This audit is complete and ready for the reorganization plan review.
