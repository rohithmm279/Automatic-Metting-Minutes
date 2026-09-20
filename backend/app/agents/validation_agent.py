"""Validation Agent: Cross-validates generated outputs against the source transcript."""

import logging
import re
from typing import Optional

from app.schemas.meeting_schema import (
    ActionItem,
    DecisionItem,
    OverallValidation,
    ValidationInfo,
)

logger = logging.getLogger(__name__)


class ValidationAgent:
    """Agent that performs semantic and lexical grounding checks on all generated outputs."""

    # Disallowed phrases in decisions that signal an unconfirmed proposal or mere discussion
    _SPECULATION_PHRASES = [
        "maybe",
        "might",
        "could consider",
        "perhaps",
        "suggested",
        "thinking about",
        "we could",
        "what if",
        "open for debate",
    ]

    # Disallowed meta-task phrases (administrative logging/recording overhead)
    _META_TASK_PATTERNS = [
        re.compile(r"^(?:log|assign|record|note\s+down|track)\s+(?:the\s+)?(?:action\s+items?|decisions?|meeting\s+minutes?|tasks?|items?)\b", re.I),
        re.compile(r"\b(?:log\s+and\s+assign|assign\s+the\s+task\s+to\s+log|track\s+(?:these\s+)?items\s+in\s+jira)\b", re.I),
    ]

    # Pattern for standalone time-of-day timestamps without future context (e.g. 11:02 AM)
    _INCIDENT_TIME_PATTERN = re.compile(r"^\d{1,2}:\d{2}\s*(?:am|pm|utc|est|pst|gmt)?$", re.I)

    def validate_all(
        self,
        transcript: str,
        summary: str,
        action_items: list[ActionItem],
        decisions: list[str],
        detailed_decisions: Optional[list[DecisionItem]] = None,
        unresolved_issues: Optional[list[str]] = None,
    ) -> tuple[str, list[ActionItem], list[str], Optional[list[DecisionItem]], OverallValidation]:
        """Validate summary, action items, and decisions against transcript evidence.
        
        Returns:
            Tuple of (validated_summary, validated_action_items, validated_decisions, validated_detailed_decisions, overall_validation)
        """
        transcript_clean = transcript.strip()
        transcript_lower = transcript_clean.lower()
        issues_found: list[str] = []

        # 1. Summary validation
        summary_grounded = self.validate_summary(summary, transcript_lower)
        if not summary_grounded:
            issues_found.append("Summary contains unsupported or hallucinated claims not found in transcript.")

        # 2. Action items validation
        validated_actions: list[ActionItem] = []
        action_items_valid = True
        for idx, item in enumerate(action_items):
            val_info = self.validate_action_item(item, transcript_lower)
            if not val_info.is_valid:
                action_items_valid = False
                issues_found.append(f"Action item #{idx+1} '{item.task}': {val_info.notes}")
            
            # Attach validation info
            item.validation = val_info
            validated_actions.append(item)

        # 3. Decision validation
        validated_decisions: list[str] = []
        validated_detailed_decisions: list[DecisionItem] = []
        decisions_valid = True

        if detailed_decisions:
            for idx, dec_item in enumerate(detailed_decisions):
                val_info = self.validate_decision_item(dec_item, transcript_lower)
                if not val_info.is_valid:
                    decisions_valid = False
                    issues_found.append(f"Decision #{idx+1} '{dec_item.decision}': {val_info.notes}")
                dec_item.validation = val_info
                validated_detailed_decisions.append(dec_item)
                validated_decisions.append(dec_item.decision)
        else:
            for idx, dec_str in enumerate(decisions):
                val_info = self.validate_decision_string(dec_str, transcript_lower)
                if not val_info.is_valid:
                    decisions_valid = False
                    issues_found.append(f"Decision #{idx+1} '{dec_str}': {val_info.notes}")
                validated_decisions.append(dec_str)

        # 4. Unresolved issues validation
        if unresolved_issues:
            for idx, u_iss in enumerate(unresolved_issues):
                if not self.validate_unresolved_issue(u_iss, transcript_lower):
                    issues_found.append(f"Unresolved issue #{idx+1} '{u_iss}': Not grounded in transcript.")

        all_grounded = summary_grounded and action_items_valid and decisions_valid

        overall = OverallValidation(
            summary_grounded=summary_grounded,
            action_items_valid=action_items_valid,
            decisions_valid=decisions_valid,
            all_grounded=all_grounded,
            issues=issues_found,
        )

        return summary, validated_actions, validated_decisions, validated_detailed_decisions, overall

    def validate_summary(self, summary: str, transcript_lower: str) -> bool:
        """Check if summary is non-empty and grounded in transcript words."""
        if not summary or not summary.strip():
            return False
        
        # Token overlap check: ensure key content words appear in transcript
        words = [w.lower() for w in re.findall(r"\b[A-Za-z]{4,}\b", summary)]
        if not words:
            return True
        
        found_count = sum(1 for w in words if w in transcript_lower)
        overlap_ratio = found_count / len(words)
        return overlap_ratio >= 0.40

    def validate_action_item(self, item: ActionItem, transcript_lower: str) -> ValidationInfo:
        """Validate an ActionItem for task grounding, owner presence, deadline presence."""
        if not item.task or not item.task.strip():
            return ValidationInfo(
                is_valid=False,
                grounded=False,
                confidence=0.0,
                notes="Task description is empty.",
            )

        task_clean = item.task.strip()
        
        # Check for disallowed meta-tasks (e.g. "log the action items", "assign task to log")
        for pattern in self._META_TASK_PATTERNS:
            if pattern.search(task_clean):
                return ValidationInfo(
                    is_valid=False,
                    grounded=False,
                    confidence=0.0,
                    notes="Rejected meta-task: meeting administrative logging/recording instruction.",
                )

        task_words = [w.lower() for w in re.findall(r"\b[A-Za-z]{3,}\b", task_clean)]
        grounded = True
        notes_list = []

        # Check task words grounding in transcript
        if task_words:
            matched_words = sum(1 for w in task_words if w in transcript_lower)
            if matched_words / len(task_words) < 0.30:
                grounded = False
                notes_list.append("Task keywords not found in transcript.")

        # Check owner
        if item.owner and item.owner.strip() and item.owner.lower() not in ("not specified", "null", "none", "unassigned"):
            owner_clean = item.owner.strip().lower()
            if owner_clean not in transcript_lower:
                grounded = False
                notes_list.append(f"Owner '{item.owner}' is not present in transcript dialogue.")
        else:
            # Missing owner is valid when marked 'Not specified' or None
            item.owner = "Not specified"

        # Check deadline
        if item.deadline and item.deadline.strip() and item.deadline.lower() not in ("not specified", "null", "none", "no deadline"):
            deadline_clean = item.deadline.strip().lower()
            # If deadline is a bare timestamp without future date/preposition, reject as incident timestamp
            if self._INCIDENT_TIME_PATTERN.match(deadline_clean) and not any(kw in deadline_clean for kw in ("by", "before", "due", "until", "tomorrow", "today", "next", "eod")):
                item.deadline = "Not specified"
                notes_list.append("Raw timestamp normalized to 'Not specified' as it does not specify a future deadline.")
            else:
                # Extract key words from deadline to verify against transcript
                dl_words = [w for w in re.findall(r"\b[A-Za-z0-9]{3,}\b", deadline_clean)]
                if dl_words and not any(w in transcript_lower for w in dl_words):
                    grounded = False
                    notes_list.append(f"Deadline '{item.deadline}' is not mentioned in transcript.")
        else:
            item.deadline = "Not specified"

        # Check evidence quote if provided
        if item.evidence:
            ev_clean = item.evidence.strip().lower()
            if ev_clean not in transcript_lower:
                # Evidence quote slightly rewritten or not verbatim
                ev_words = [w for w in re.findall(r"\b[A-Za-z]{3,}\b", ev_clean)]
                if ev_words and sum(1 for w in ev_words if w in transcript_lower) / len(ev_words) < 0.5:
                    notes_list.append("Evidence quote does not match transcript content.")

        confidence = 1.0 if grounded else 0.4
        notes = "; ".join(notes_list) if notes_list else "Fully supported by transcript."

        return ValidationInfo(
            is_valid=grounded,
            grounded=grounded,
            confidence=confidence,
            notes=notes,
        )

    def validate_unresolved_issue(self, issue: str, transcript_lower: str) -> bool:
        """Check if an unresolved issue is grounded in transcript words and not a dummy placeholder."""
        if not issue or not issue.strip():
            return False
        
        # Check for dummy/placeholder phrases like "No issues identified"
        if re.search(
            r"(?i)^(?:no\s+(?:active\s+|open\s+|explicit\s+|identified\s+|unresolved\s+)?(?:issues|risks|blockers|concerns)(?:\s+(?:identified|found|noted|reported|raised))?|none|n/a)\.?$",
            issue.strip(),
        ):
            return False

        words = [w.lower() for w in re.findall(r"\b[A-Za-z]{4,}\b", issue)]
        if not words:
            return True
        matched = sum(1 for w in words if w in transcript_lower)
        if len(words) <= 2:
            return matched >= 1 and (matched / len(words)) >= 0.5
        return (matched / len(words)) >= 0.50 and matched >= 2

    def filter_unresolved_issues(self, issues: list[str], transcript_lower: str) -> list[str]:
        """Prune ungrounded, dummy, or hallucinated issues that do not appear in transcript."""
        return [iss for iss in issues if self.validate_unresolved_issue(iss, transcript_lower)]

    def validate_decision_item(self, item: DecisionItem, transcript_lower: str) -> ValidationInfo:
        """Validate DecisionItem against speculative phrasing and transcript grounding."""
        return self._validate_decision_text(item.decision, transcript_lower, item.evidence)

    def validate_decision_string(self, decision_text: str, transcript_lower: str) -> ValidationInfo:
        """Validate flat decision string."""
        return self._validate_decision_text(decision_text, transcript_lower)

    def _validate_decision_text(
        self,
        decision_text: str,
        transcript_lower: str,
        evidence: Optional[str] = None,
    ) -> ValidationInfo:
        if not decision_text or not decision_text.strip():
            return ValidationInfo(
                is_valid=False,
                grounded=False,
                confidence=0.0,
                notes="Decision text is empty.",
            )

        dec_clean = decision_text.strip().lower()

        # Check for speculative / unconfirmed language
        for phrase in self._SPECULATION_PHRASES:
            if phrase in dec_clean:
                return ValidationInfo(
                    is_valid=False,
                    grounded=False,
                    confidence=0.3,
                    notes=f"Decision contains speculative phrasing ('{phrase}') instead of confirmed resolution.",
                )

        # Token grounding
        words = [w for w in re.findall(r"\b[A-Za-z]{3,}\b", dec_clean)]
        if words:
            matched = sum(1 for w in words if w in transcript_lower)
            if matched / len(words) < 0.30:
                return ValidationInfo(
                    is_valid=False,
                    grounded=False,
                    confidence=0.4,
                    notes="Decision keywords not found in transcript.",
                )

        return ValidationInfo(
            is_valid=True,
            grounded=True,
            confidence=1.0,
            notes="Confirmed and grounded in transcript.",
        )
