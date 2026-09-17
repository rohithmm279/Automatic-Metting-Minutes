"""Safe, read-only discovery and normalization of supported dataset files."""

import csv
import json
from itertools import islice
from pathlib import Path
from typing import Any

from app.schemas.evaluation_schema import DatasetInfo, DatasetRecord


class DatasetLoader:
    """Discover files and normalize transcript records from common data formats."""

    _SUPPORTED_EXTENSIONS = {".csv", ".json", ".jsonl", ".txt", ".transcript"}
    _TRANSCRIPT_FIELDS = ("transcript", "content", "text", "dialogue", "conversation")
    _SUMMARY_FIELDS = ("reference_summary", "summary", "gold_summary")
    _ACTION_FIELDS = ("reference_action_items", "action_items", "actions")
    _DECISION_FIELDS = ("reference_decisions", "decisions")
    _ISSUE_FIELDS = ("reference_issues", "unresolved_issues", "issues", "open_issues")
    _MAX_FILE_SIZE_BYTES = 10_000_000
    _MAX_TRANSCRIPT_CHARACTERS = 100_000

    def __init__(self, datasets_root: Path | None = None) -> None:
        """Set the datasets root, defaulting to the repository's datasets folder."""
        self.datasets_root = datasets_root or Path(__file__).resolve().parents[3] / "datasets"

    def discover(self) -> list[DatasetInfo]:
        """Return selectable files and parent collections without reading their content."""
        if not self.datasets_root.is_dir():
            return []
        files = [
            path
            for path in sorted(self.datasets_root.rglob("*"))
            if path.is_file() and path.suffix.lower() in self._SUPPORTED_EXTENSIONS
        ]
        file_entries = [
            DatasetInfo(
                name=path.relative_to(self.datasets_root).as_posix(),
                entry_type="file",
                file_format=path.suffix.lower().lstrip("."),
                size_bytes=path.stat().st_size,
            )
            for path in files
        ]
        collections = sorted({path.parent for path in files})
        directory_entries = [
            DatasetInfo(
                name=directory.relative_to(self.datasets_root).as_posix(),
                entry_type="directory",
                file_format="collection",
                size_bytes=0,
                supported_file_count=sum(path.parent == directory for path in files),
            )
            for directory in collections
        ]
        return directory_entries + file_entries

    def load(self, dataset_name: str, limit: int) -> tuple[list[DatasetRecord], int]:
        """Load up to ``limit`` valid records from one file or recursive directory.

        Returns records and the count of source entries skipped for missing or
        invalid transcript content. Dataset parsing errors result in no records.
        """
        path = self._resolve_dataset_path(dataset_name)
        if path is None or not path.exists():
            raise ValueError("Dataset path does not exist.")
        source_paths = self._source_paths(path)
        if not source_paths:
            raise ValueError("No supported transcript files were found in the dataset path.")

        records: list[DatasetRecord] = []
        skipped = 0
        for source_path in source_paths:
            if len(records) >= limit:
                break
            if source_path.stat().st_size > self._MAX_FILE_SIZE_BYTES:
                skipped += 1
                continue
            try:
                source_records = self._read_source_records(source_path, limit - len(records))
            except (OSError, UnicodeDecodeError, csv.Error, json.JSONDecodeError, ValueError):
                skipped += 1
                continue
            for index, source_record in enumerate(source_records):
                normalized = self._normalize_record(source_record, source_path, index)
                if normalized is None:
                    skipped += 1
                    continue
                records.append(normalized)
                if len(records) >= limit:
                    break

        if not records:
            raise ValueError("No valid transcript records were found in the dataset path.")
        if path.is_dir() and len(records) < limit:
            raise ValueError(
                f"Requested limit ({limit}) exceeds available valid records ({len(records)})."
            )
        return records, skipped

    def _source_paths(self, path: Path) -> list[Path]:
        """Return one file or all supported files beneath a selected directory."""
        if path.is_file():
            return [path] if path.suffix.lower() in self._SUPPORTED_EXTENSIONS else []
        return [
            candidate
            for candidate in sorted(path.rglob("*"))
            if candidate.is_file() and candidate.suffix.lower() in self._SUPPORTED_EXTENSIONS
        ]

    def _resolve_dataset_path(self, dataset_name: str) -> Path | None:
        """Resolve a relative dataset name while preventing path traversal."""
        try:
            candidate = (self.datasets_root / dataset_name).resolve()
            candidate.relative_to(self.datasets_root.resolve())
            return candidate
        except (OSError, ValueError):
            return None

    def _read_source_records(self, path: Path, limit: int) -> list[Any]:
        """Read at most ``limit`` source records without writing to disk."""
        suffix = path.suffix.lower()
        if suffix in {".txt", ".transcript"}:
            return [{"id": path.stem, "transcript": path.read_text(encoding="utf-8")}]
        if suffix == ".csv":
            with path.open("r", encoding="utf-8-sig", newline="") as source_file:
                return list(islice(csv.DictReader(source_file), limit))
        if suffix == ".jsonl":
            with path.open("r", encoding="utf-8") as source_file:
                records = []
                for line in islice(source_file, limit):
                    if line.strip():
                        records.append(json.loads(line))
                return records

        parsed = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(parsed, list):
            return parsed[:limit]
        if isinstance(parsed, dict):
            for key in ("records", "data", "meetings", "items"):
                if isinstance(parsed.get(key), list):
                    return parsed[key][:limit]
            return [parsed]
        return []

    def _normalize_record(
        self, source_record: Any, path: Path, index: int
    ) -> DatasetRecord | None:
        """Map a source record to the shared structure when transcript text exists."""
        if not isinstance(source_record, dict):
            return None
        transcript = self._first_text(source_record, self._TRANSCRIPT_FIELDS)
        annotations = self._companion_annotations(path, source_record.get("id") or path.stem)
        combined = {**annotations, **source_record}
        transcript = transcript or self._first_text(combined, self._TRANSCRIPT_FIELDS)
        if not transcript or len(transcript) > self._MAX_TRANSCRIPT_CHARACTERS:
            return None

        record_id = str(combined.get("id") or combined.get("meeting_id") or f"{path.stem}-{index}")
        return DatasetRecord(
            id=record_id,
            transcript=transcript,
            reference_summary=self._first_text(combined, self._SUMMARY_FIELDS),
            reference_action_items=self._first_list(combined, self._ACTION_FIELDS, "task"),
            reference_decisions=self._first_list(combined, self._DECISION_FIELDS, "decision"),
            reference_issues=self._first_list(combined, self._ISSUE_FIELDS, "issue"),
            source_dataset=path.relative_to(self.datasets_root).as_posix(),
        )

    @staticmethod
    def _first_text(record: dict[str, Any], fields: tuple[str, ...]) -> str | None:
        """Return the first non-empty string found under known field aliases."""
        for field in fields:
            value = record.get(field)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    @staticmethod
    def _first_list(
        record: dict[str, Any], fields: tuple[str, ...], nested_field: str
    ) -> list[str] | None:
        """Return string labels from a known list field, preserving unavailable as None."""
        for field in fields:
            value = record.get(field)
            if not isinstance(value, list):
                continue
            labels = []
            for item in value:
                if isinstance(item, str) and item.strip():
                    labels.append(item.strip())
                elif isinstance(item, dict) and isinstance(item.get(nested_field), str):
                    labels.append(item[nested_field].strip())
            return labels
        return None

    @staticmethod
    def _companion_annotations(path: Path, record_id: object) -> dict[str, Any]:
        """Read same-ID ground-truth JSON beside a ``transcripts`` directory if present."""
        if path.parent.name != "transcripts":
            return {}
        annotation_path = path.parent.parent / "ground_truth" / f"{record_id}.json"
        try:
            parsed = json.loads(annotation_path.read_text(encoding="utf-8"))
            return parsed if isinstance(parsed, dict) else {}
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return {}
