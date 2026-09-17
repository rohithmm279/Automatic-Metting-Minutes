"""Orchestrator for end-to-end meeting analysis pipeline."""

import json
from typing import Any
from backend.ai.ollama_client import OllamaClient
from backend.ai.prompts import build_meeting_analysis_prompt
from backend.ai.validator import MeetingValidator
from backend.app.services.transcript_processor import TranscriptProcessor
from backend.models.meeting import ActionItem, Decision, UnresolvedIssue, MeetingOutput


class MeetingParseError(ValueError):
    """Raised when the LLM response cannot be parsed as structured meeting data."""
    pass


def _flatten_string_or_list(item: Any) -> str:
    """Recursively flatten nested lists/dicts to a single string."""
    if isinstance(item, str):
        return item.strip()
    if isinstance(item, list):
        return " ".join(_flatten_string_or_list(x) for x in item).strip()
    if isinstance(item, dict):
        return str(item.get("decision", item.get("issue", item.get("task", str(item))))).strip()
    return str(item).strip()


class MeetingOrchestrator:
    """Orchestrates transcript preprocessing, Ollama inference, parsing, and validation."""

    def __init__(
        self,
        client: OllamaClient | None = None,
        validator: MeetingValidator | None = None,
        temperature: float = 0.0,
        repository: Any | None = None,
    ):
        self.client = client or OllamaClient()
        self.validator = validator or MeetingValidator()
        self.temperature = temperature
        self.repository = repository

    def _parse_json(self, raw_output: str) -> dict[str, Any]:
        """Strip optional markdown formatting and parse raw JSON."""
        cleaned = raw_output.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1]
            if cleaned.endswith("```"):
                cleaned = cleaned.rsplit("```", 1)[0]
            cleaned = cleaned.strip()

        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError as err:
            raise MeetingParseError(
                f"Model response is not valid JSON: {err}. Preview: {raw_output[:200]}"
            ) from err

        if not isinstance(parsed, dict):
            raise MeetingParseError(
                f"Model output root must be a JSON object, got {type(parsed).__name__}."
            )

        return parsed

    def _build_models(self, data: dict[str, Any]) -> MeetingOutput:
        """Convert parsed dictionary to Pydantic MeetingOutput."""
        summary = str(data.get("summary", "")).strip()

        # Action items
        action_items: list[ActionItem] = []
        raw_actions = data.get("action_items", [])
        if not isinstance(raw_actions, list):
            raise MeetingParseError("Field 'action_items' must be a list.")

        for item in raw_actions:
            if not isinstance(item, dict):
                continue
            task = str(item.get("task", "")).strip()
            owner = item.get("owner")
            if owner is not None:
                owner = str(owner).strip() or None
            deadline = item.get("deadline")
            if deadline is not None:
                deadline = str(deadline).strip() or None
            status = str(item.get("status", "pending")).strip() or "pending"

            action_items.append(
                ActionItem(
                    task=task,
                    owner=owner,
                    deadline=deadline,
                    status=status,
                    confidence=1.0,
                )
            )

        # Decisions
        decisions: list[Decision] = []
        raw_decisions = data.get("decisions", [])
        if not isinstance(raw_decisions, list):
            raise MeetingParseError("Field 'decisions' must be a list.")

        for dec in raw_decisions:
            dec_text = _flatten_string_or_list(dec)
            if dec_text:
                decisions.append(Decision(decision=dec_text, confidence=1.0))

        # Unresolved issues
        unresolved_issues: list[UnresolvedIssue] = []
        raw_issues = data.get("unresolved_issues", [])
        if not isinstance(raw_issues, list):
            raise MeetingParseError("Field 'unresolved_issues' must be a list.")

        for issue in raw_issues:
            issue_text = _flatten_string_or_list(issue)
            if issue_text:
                unresolved_issues.append(UnresolvedIssue(issue=issue_text, confidence=1.0))

        return MeetingOutput(
            summary=summary,
            action_items=action_items,
            decisions=decisions,
            unresolved_issues=unresolved_issues,
        )

    def analyze(self, transcript: str) -> MeetingOutput:
        """Run full meeting analysis workflow: preprocess -> prompt -> Ollama -> parse -> validate -> output."""
        if not transcript or not transcript.strip():
            raise ValueError("Transcript must not be empty or whitespace only.")

        # 1. Preprocess transcript using existing TranscriptProcessor
        cleaned_transcript = TranscriptProcessor.clean_transcript(transcript)
        if not cleaned_transcript or not cleaned_transcript.strip():
            raise ValueError("Transcript must not be empty or whitespace only after preprocessing.")

        # 2. Build prompt using the benchmark rules
        prompt = build_meeting_analysis_prompt(cleaned_transcript)

        # 3. Call local Ollama model
        raw_output = self.client.generate(prompt=prompt, temperature=self.temperature)

        # 4. Parse JSON
        parsed_data = self._parse_json(raw_output)

        # 5. Convert to Pydantic models
        meeting_output = self._build_models(parsed_data)

        # 6. Deterministic validation
        validated_output = self.validator.validate(meeting_output, cleaned_transcript)

        return validated_output

    def analyze_and_save(
        self, transcript: str, repository: Any | None = None
    ) -> tuple[MeetingOutput, int]:
        """Analyze transcript and persist validated output to the repository.

        Returns:
            tuple[MeetingOutput, int]: The validated MeetingOutput and generated meeting ID.
        """
        repo = repository or self.repository
        if repo is None:
            raise ValueError("No repository provided to persist the meeting.")

        validated_output = self.analyze(transcript)
        meeting_id = repo.save_meeting(transcript=transcript, meeting_output=validated_output)
        return validated_output, meeting_id

