"""Deterministic validator for meeting intelligence outputs."""

from backend.models.meeting import MeetingOutput, ActionItem, Decision, UnresolvedIssue

ALLOWED_STATUSES = {"pending", "in_progress", "completed", "cancelled"}


class MeetingValidationError(ValueError):
    """Raised when extracted meeting data fails validation."""
    pass


class MeetingValidator:
    """Validates MeetingOutput structures and checks grounding against transcript."""

    def __init__(self, allowed_statuses: set[str] | None = None):
        self.allowed_statuses = allowed_statuses or ALLOWED_STATUSES

    def validate(self, output: MeetingOutput, transcript: str) -> MeetingOutput:
        """Run all deterministic validations against the MeetingOutput and transcript."""
        if not isinstance(output, MeetingOutput):
            raise MeetingValidationError("Output must be an instance of MeetingOutput.")

        if not transcript or not transcript.strip():
            raise MeetingValidationError("Transcript must not be empty.")

        transcript_lower = transcript.lower()

        # 1. Summary validation
        if not output.summary or not output.summary.strip():
            raise MeetingValidationError("Meeting summary must be a non-empty string.")

        # 2. Action items validation
        for idx, item in enumerate(output.action_items):
            if not isinstance(item, ActionItem):
                raise MeetingValidationError(f"Action item at index {idx} is not an ActionItem instance.")

            if not item.task or not item.task.strip():
                raise MeetingValidationError(f"Action item at index {idx} has an empty task.")

            if item.status not in self.allowed_statuses:
                raise MeetingValidationError(
                    f"Action item at index {idx} has invalid status '{item.status}'. "
                    f"Must be one of {self.allowed_statuses}."
                )

            if not (0.0 <= item.confidence <= 1.0):
                raise MeetingValidationError(
                    f"Action item at index {idx} has invalid confidence {item.confidence}. Must be in [0.0, 1.0]."
                )

            # Check owner against transcript
            if item.owner is not None:
                cleaned_owner = item.owner.strip()
                if not cleaned_owner:
                    item.owner = None
                elif cleaned_owner.lower() not in transcript_lower:
                    raise MeetingValidationError(
                        f"Action item at index {idx} references owner '{item.owner}' which is not in the transcript."
                    )

            # Check deadline against transcript
            if item.deadline is not None:
                cleaned_deadline = item.deadline.strip()
                if not cleaned_deadline:
                    item.deadline = None
                elif cleaned_deadline.lower() not in transcript_lower:
                    raise MeetingValidationError(
                        f"Action item at index {idx} references deadline '{item.deadline}' which is not in the transcript."
                    )

        # 3. Decisions validation
        for idx, dec in enumerate(output.decisions):
            if not isinstance(dec, Decision):
                raise MeetingValidationError(f"Decision at index {idx} is not a Decision instance.")

            if not dec.decision or not dec.decision.strip():
                raise MeetingValidationError(f"Decision at index {idx} has an empty decision text.")

            if not (0.0 <= dec.confidence <= 1.0):
                raise MeetingValidationError(
                    f"Decision at index {idx} has invalid confidence {dec.confidence}. Must be in [0.0, 1.0]."
                )

        # 4. Unresolved issues validation
        for idx, issue in enumerate(output.unresolved_issues):
            if not isinstance(issue, UnresolvedIssue):
                raise MeetingValidationError(f"Unresolved issue at index {idx} is not an UnresolvedIssue instance.")

            if not issue.issue or not issue.issue.strip():
                raise MeetingValidationError(f"Unresolved issue at index {idx} has an empty issue text.")

            if not (0.0 <= issue.confidence <= 1.0):
                raise MeetingValidationError(
                    f"Unresolved issue at index {idx} has invalid confidence {issue.confidence}. Must be in [0.0, 1.0]."
                )

        return output
