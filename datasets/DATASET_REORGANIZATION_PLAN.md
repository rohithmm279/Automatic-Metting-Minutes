# Dataset Reorganization Plan

Status: PLAN ONLY — not executed yet.

## Goal
Create a single clean dataset root using the target structure while preserving all raw data, split files, and archive content exactly as currently stored.

## Proposed target root

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
│   ├── AMI/
│   ├── QMSum/
│   ├── MeetingBank/
│   └── ELITR/
├── 03_SUPPLEMENTARY/
│   └── MISED/
├── 04_REFERENCE/
│   └── raw_annotations/
├── 99_ARCHIVE_NOTES/
│   └── all existing archive content unchanged
└── ...
```

## Planned actions

| Current path | Proposed path | Reason for change | Action |
|---|---|---|---|
| `Meeting_Project_Datasets_Organized/Meeting_Project_Datasets/00_GUIDE` | `datasets/00_GUIDE` | Standardize the root to a single clean `datasets` directory and keep guide material together. | Move folder contents to new root |
| `Meeting_Project_Datasets_Organized/Meeting_Project_Datasets/01_PRIMARY/student_club` | `datasets/01_PRIMARY/student_club` | This is the primary working dataset and should sit under the new single root. | Move folder |
| `Meeting_Project_Datasets_Organized/Meeting_Project_Datasets/01_PRIMARY/student_club/transcripts` | `datasets/01_PRIMARY/student_club/transcripts` | Preserve transcript files and keep the standard project structure. | Move folder |
| `Meeting_Project_Datasets_Organized/Meeting_Project_Datasets/01_PRIMARY/student_club/ground_truth` | `datasets/01_PRIMARY/student_club/ground_truth` | Keep annotation and evidence records with the student-club dataset. | Move folder |
| `Meeting_Project_Datasets_Organized/Meeting_Project_Datasets/01_PRIMARY/student_club/metadata.csv` | `datasets/01_PRIMARY/student_club/metadata/metadata.csv` | Match the target structure where metadata is held under a dedicated metadata directory. | Move and rename as needed |
| `Meeting_Project_Datasets_Organized/Meeting_Project_Datasets/01_PRIMARY/student_club/statistics.json` | `datasets/01_PRIMARY/student_club/documentation/statistics.json` | Separate dataset metadata from transcript and annotation data. | Move and rename as needed |
| `Meeting_Project_Datasets_Organized/Meeting_Project_Datasets/01_PRIMARY/student_club/README.md` | `datasets/01_PRIMARY/student_club/documentation/README.md` | Place dataset-level documentation in a dedicated documentation folder. | Move and rename as needed |
| `Meeting_Project_Datasets_Organized/Meeting_Project_Datasets/02_BENCHMARKS/qmsum` | `datasets/02_BENCHMARKS/QMSum` | Standardize benchmark naming to uppercase canonical dataset names. | Rename and move |
| `Meeting_Project_Datasets_Organized/Meeting_Project_Datasets/02_BENCHMARKS/meetingbank` | `datasets/02_BENCHMARKS/MeetingBank` | Standardize benchmark naming consistent with target structure. | Rename and move |
| `Meeting_Project_Datasets_Organized/Meeting_Project_Datasets/03_SUPPLEMENTARY/mised` | `datasets/03_SUPPLEMENTARY/MISED` | Standardize naming and keep supplementary datasets under one folder. | Rename and move |
| `Meeting_Project_Datasets_Organized/Meeting_Project_Datasets/04_REFERENCE/ami` | `datasets/02_BENCHMARKS/AMI` | AMI belongs to benchmark-level reference material in the target layout. | Move to benchmark bucket |
| `Meeting_Project_Datasets_Organized/Meeting_Project_Datasets/04_REFERENCE/elitr_bench` | `datasets/02_BENCHMARKS/ELITR` | ELITR-Bench is a benchmark-style reference dataset and should be grouped accordingly. | Move and rename |
| `Meeting_Project_Datasets_Organized/Meeting_Project_Datasets/04_REFERENCE/icsi` | `datasets/04_REFERENCE/raw_annotations` or `datasets/02_BENCHMARKS/ICSI` depending on final classification | ICSI is a reference meeting corpus; as a safer default, leave under reference raw annotations unless specific downstream usage requires benchmark grouping. | Leave unchanged for review |
| `Meeting_Project_Datasets_Organized/Meeting_Project_Datasets/99_ARCHIVE_NOTES` | `datasets/99_ARCHIVE_NOTES` | Preserve historical raw copies and nested archive state exactly as-is. | Leave unchanged |
| `Meeting_Project_Datasets_Organized/Meeting_Project_Datasets/99_ARCHIVE_NOTES/raw_Datasets` | `datasets/99_ARCHIVE_NOTES/raw_Datasets` | Historical raw duplicates are protected and must remain untouched. | Leave unchanged |

## Notes

1. No file move is scheduled yet.
2. No dataset content is being deleted.
3. All split files are explicitly protected and will be preserved exactly.
4. Only after approval will the actual physical moves begin.
5. Archive content remains frozen and will not be modified in any way.

## Proposed execution order after approval

1. Create a single clean `datasets/` root at the top level.
2. Move only the active working dataset folders, never the archive.
3. Preserve the current train/validation/test split files exactly.
4. Keep all raw data files intact and avoid duplicates.
5. Rebuild the final inventory after the folder moves are complete.

## Approval gate

This plan is intentionally non-destructive and is waiting for explicit approval before Phase 3 execution begins.
