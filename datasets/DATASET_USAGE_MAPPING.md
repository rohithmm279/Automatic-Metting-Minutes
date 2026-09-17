# Dataset Usage Mapping

## PRIMARY

- Student Club Dataset
  - Location: 01_PRIMARY/student_club
  - Purpose: Main research and evaluation dataset for structured meeting outputs
  - Includes: transcript files, ground-truth annotations, metadata, and documentation

## BENCHMARKS

- AMI
  - Location: 04_REFERENCE/ami
  - Classification: Benchmark / reference corpus
  - Role: Meeting understanding and annotation research

- QMSum
  - Location: 02_BENCHMARKS/qmsum
  - Classification: Benchmark
  - Role: Query-based meeting summarization and long-context understanding

- MeetingBank
  - Location: 02_BENCHMARKS/meetingbank
  - Classification: Benchmark
  - Role: Long-form meeting summarization and minute generation

- ELITR Bench
  - Location: 04_REFERENCE/elitr_bench
  - Classification: Benchmark / reference corpus
  - Role: Long-context QA and meeting-related benchmark tasks

## SUPPLEMENTARY

- MISED
  - Location: 03_SUPPLEMENTARY/mised
  - Purpose: Supplementary information-seeking and grounded QA dataset

## REFERENCE

- Raw meeting annotations and reference datasets
  - Location: 04_REFERENCE
  - Includes: AMI, ELITR Bench, and ICSI
  - Notes: These are retained as reference and annotation resources, separate from the main primary and benchmark working datasets

- ICSI
  - Location: 04_REFERENCE/icsi
  - Purpose: Separate reference corpus kept distinct from the benchmark bucket

## ARCHIVE

- Everything inside 99_ARCHIVE_NOTES
  - Purpose: historical snapshots, raw dataset mirrors, and duplicate archive material
  - Status: intentionally left unchanged

## Final usage policy

- Use Student Club as the primary dataset for training and evaluation.
- Use benchmark datasets to validate generalization and compare against external meeting corpora.
- Use MISeD only as a supplementary QA / retrieval resource.
- Keep reference and archive materials separate from the active working dataset flow.
- Do not preprocess, convert, or train on data during this audit and reorganization phase.
