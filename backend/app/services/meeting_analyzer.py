"""Deterministic, conservative fallback meeting transcript analysis."""

from collections.abc import Iterable
import re

from app.schemas.meeting_schema import ActionItem, MeetingAnalysis


class MeetingAnalyzer:
    """Extract meeting outcomes when Gemini is unavailable.

    The fallback requires explicit linguistic evidence; it does not infer an
    assignment, date, or decision that is not stated in the transcript.
    """

    _ACTION_PATTERNS = (
        r"\b(?:need|needs|needed|has) to\s+",
        r"\b(?:i|we|they|[A-Z][a-z]+)\s+(?:will|'ll|shall|plan to|are going to)\s+",
        r"\b(?:can|could|would)\s+you\s+",
        r"\b(?:assigned|assign)\s+(?:to\s+)?",
        r"\bresponsible for\s+",
        r"\btasked with\s+",
    )
    _DECISION_PATTERNS = (
        r"\b(?:agreed|decided|approved|confirmed|finalized|settled on|chose|chosen|selected)\b",
        r"\b(?:will|shall) proceed with\b",
        r"\blet'?s go with\b",
        r"\b(?:final choice|decision) is\b",
        r"\b(?:committee|everyone|team) accepted\b",
        r"\bthat'?s settled\b",
    )
    _UNRESOLVED_PATTERNS = (
        r"\bstill pending\b",
        r"\b(?:not|has not|have not|is not|isn't)\s+(?:yet\s+)?(?:decided|approved|confirmed|finalized|settled)\b",
        r"\b(?:still\s+)?undecided\b",
        r"\bunresolved\b",
        r"\bwaiting for (?:approval|confirmation|a response|a reply|an answer)\b",
        r"\bneeds? (?:further )?discussion\b",
        r"\bneeds? confirmation\b",
        r"\bopen question\b",
        r"\bunclear\b",
    )
    _DEADLINE_PATTERN = re.compile(
        r"\b(?:(?:by|before|on|due)\s+(?:the\s+)?(?:end of )?(?:next\s+)?"
        r"(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)|"
        r"(?:by|before|on|due)\s+\d{1,2}(?:st|nd|rd|th)?(?:\s+of\s+\w+)?|"
        r"(?:tomorrow|today|this\s+(?:week|month)|next\s+(?:week|month)|"
        r"sometime\s+next\s+week|before\s+the\s+weekend))\b",
        re.IGNORECASE,
    )
    _SPEAKER_PATTERN = re.compile(r"^([A-Za-z][A-Za-z .'-]{0,49}):\s*(.*)$")
    _NON_PERSON_LEADS = {"the", "we", "i", "our", "team", "committee", "everyone", "someone"}

    def analyze(self, transcript: str) -> MeetingAnalysis:
        """Analyze a cleaned transcript and return the existing response shape."""
        if not isinstance(transcript, str) or not transcript.strip():
            raise ValueError("A non-empty transcript is required for analysis.")

        sentences = self._split_sentences(transcript)
        unresolved_issues = self._unique_sentences(
            self._normalize_issue(sentence)
            for sentence in sentences
            if self._is_unresolved_issue(sentence)
        )
        decisions = self._unique_sentences(
            self._normalize_decision(sentence)
            for sentence in sentences
            if self._is_decision(sentence) and not self._is_unresolved_issue(sentence)
        )
        action_items = self._extract_actions(sentences)
        return MeetingAnalysis(
            summary=self._build_summary(sentences, decisions, action_items, unresolved_issues),
            action_items=action_items,
            decisions=decisions,
            unresolved_issues=unresolved_issues,
        )

    @staticmethod
    def _split_sentences(transcript: str) -> list[str]:
        return [sentence.strip(" -–—") for sentence in re.split(r"(?<=[.!?])\s+|\n+", transcript) if sentence.strip(" -–—")]

    @staticmethod
    def _matches_any(text: str, patterns: tuple[str, ...]) -> bool:
        return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)

    @classmethod
    def _content(cls, sentence: str) -> str:
        match = cls._SPEAKER_PATTERN.match(sentence)
        return match.group(2).strip() if match else sentence.strip()

    @classmethod
    def _speaker(cls, sentence: str) -> str | None:
        match = cls._SPEAKER_PATTERN.match(sentence)
        return match.group(1).strip() if match else None

    def _is_action_item(self, sentence: str) -> bool:
        return self._matches_any(self._content(sentence), self._ACTION_PATTERNS) and not self._is_unresolved_issue(sentence)

    def _is_decision(self, sentence: str) -> bool:
        return self._matches_any(self._content(sentence), self._DECISION_PATTERNS) and not self._is_unresolved_issue(sentence)

    def _is_unresolved_issue(self, sentence: str) -> bool:
        return self._matches_any(self._content(sentence), self._UNRESOLVED_PATTERNS)

    def _extract_actions(self, sentences: list[str]) -> list[ActionItem]:
        """Build deduplicated actions and attach only explicit nearby corrections."""
        actions: list[ActionItem] = []
        for sentence in sentences:
            if not self._is_action_item(sentence):
                deadline, speaker = self._extract_deadline(sentence), self._speaker(sentence)
                if deadline and actions and speaker and actions[-1].owner == speaker:
                    actions[-1].deadline = deadline
                continue
            task = self._normalize_task(sentence)
            if not task:
                continue
            candidate = ActionItem(task=task, owner=self._extract_owner(sentence), deadline=self._extract_deadline(sentence), status="pending", confidence=0.7)
            existing = next((item for item in actions if self._same_task(item.task, task)), None)
            if existing is None:
                actions.append(candidate)
            else:
                existing.owner = existing.owner or candidate.owner
                existing.deadline = existing.deadline or candidate.deadline
        return actions

    @classmethod
    def _extract_owner(cls, sentence: str) -> str | None:
        content, speaker = cls._content(sentence), cls._speaker(sentence)
        addressed = re.match(r"(?:alright,?\s+)?([A-Z][a-z]+),\s*(?:can|could|would)\s+you\b", content, re.I)
        if addressed:
            return addressed.group(1)
        assigned = re.search(r"\b(?:assigned|assign)\s+to\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b", content)
        if assigned:
            return assigned.group(1)
        named = re.match(r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+(?:will|has to|needs? to)\b", content)
        if named and named.group(1).lower() not in cls._NON_PERSON_LEADS:
            return named.group(1)
        if speaker and re.search(r"\b(?:i(?:'ll| will)|i plan to|i am going to)\b", content, re.I):
            return speaker
        return None

    @classmethod
    def _extract_deadline(cls, sentence: str) -> str | None:
        match = cls._DEADLINE_PATTERN.search(cls._content(sentence))
        return match.group(0) if match else None

    def _normalize_task(self, sentence: str) -> str:
        text = self._content(sentence)
        text = re.sub(r"^(?:(?:alright|okay|so|yeah|well)[,\s]+)+", "", text, flags=re.I)
        text = re.sub(r"^[A-Z][a-z]+,\s*(?:can|could|would)\s+you\s+", "", text, flags=re.I)
        text = re.sub(r"^(?:be\s+able\s+to\s+)", "", text, flags=re.I)
        nested_request = re.search(r"\b(?:we\s+)?need\s+to\s+(.+)$", text, re.I)
        if nested_request:
            text = nested_request.group(1)
        text = re.sub(r"^(?:someone\s+)?(?:needs?|need|has) to\s+", "", text, flags=re.I)
        text = re.sub(r"^(?:i(?:'ll| will)|we(?:'ll| will)|they(?:'ll| will))\s+", "", text, flags=re.I)
        text = re.sub(r"^[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\s+(?:will|has to|needs? to)\s+", "", text)
        text = re.sub(r"^(?:assigned to|responsible for|tasked with)\s+", "", text, flags=re.I)
        deadline = self._extract_deadline(sentence)
        if deadline:
            text = re.sub(r"\s*(?:,|—|–|-)?\s*" + re.escape(deadline) + r"\b.*$", "", text, flags=re.I)
        text = text.strip(" .?!")
        return text[:1].upper() + text[1:] if text else ""

    def _normalize_decision(self, sentence: str) -> str:
        text = self._content(sentence).strip(" .?!")
        match = re.search(r"(?:finali[sz]e|settle on|decide on)\s+(.*?)(?:\s*(?:then|—|-|that's settled|that is settled).*)?$", text, re.I)
        if match and match.group(1).strip():
            return f"Finalized {match.group(1).strip().rstrip('.')} .".replace(" .", ".")
        return text[:1].upper() + text[1:] if text else text

    def _normalize_issue(self, sentence: str) -> str:
        text = self._content(sentence).strip(" .?!")
        subject = re.split(r"\s+(?:is|are|has|have)\s+", text, maxsplit=1, flags=re.I)[0].strip()
        return f"{subject} remains unresolved." if subject else text

    @staticmethod
    def _same_task(left: str, right: str) -> bool:
        left_words, right_words = set(re.findall(r"\w+", left.lower())), set(re.findall(r"\w+", right.lower()))
        return bool(left_words and right_words and len(left_words & right_words) / len(left_words | right_words) >= 0.6)

    @staticmethod
    def _unique_sentences(sentences: Iterable[str]) -> list[str]:
        unique: list[str] = []
        for sentence in sentences:
            if sentence and sentence not in unique:
                unique.append(sentence)
        return unique

    def _build_summary(self, sentences: list[str], decisions: list[str], action_items: list[ActionItem], unresolved_issues: list[str]) -> str:
        """Create an extractive overview that includes major outcome categories."""
        discussion = next((self._content(sentence) for sentence in sentences if not self._is_action_item(sentence) and not self._is_decision(sentence) and not self._is_unresolved_issue(sentence)), self._content(sentences[0]) if sentences else "")
        selected = [discussion] if discussion else []
        selected.extend(decisions[:1])
        selected.extend(issue for issue in unresolved_issues[:1] if issue not in selected)
        selected.extend(item.task for item in action_items[:1] if item.task not in selected)
        return " ".join(selected[:3])
