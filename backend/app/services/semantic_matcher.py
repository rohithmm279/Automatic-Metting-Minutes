"""Explainable semantic normalization and matching for meeting evaluation."""

import re
from typing import Literal


CategoryType = Literal["action_items", "decisions", "unresolved_issues", "generic"]


class SemanticMatcher:
    """Conservative, explainable semantic normalization layer for evaluation.

    Normalizes category meta-phrasing (e.g., 'remains unresolved' vs 'not confirmed'),
    modal/auxiliary verbs (e.g., 'will prepare' vs 'responsible for preparing'),
    grammatical stopwords, possessives, and common inflections while strictly
    preventing unrelated items from matching.
    """

    _STOPWORDS = {
        "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
        "to", "of", "in", "for", "on", "at", "by", "with", "about", "that",
        "this", "it", "its", "as", "and", "or", "from", "into", "onto",
        "our", "my", "your", "their", "his", "her", "us", "we", "i", "they",
        "shall", "will", "would", "could", "can", "should", "may", "might",
    }

    _UNRESOLVED_PHRASES = (
        r"\bremains?\s+unresolved\b",
        r"\bis\s+unresolved\b",
        r"\bare\s+unresolved\b",
        r"\bstill\s+unresolved\b",
        r"\bunresolved\b",
        r"\bstill\s+pending\b",
        r"\bis\s+pending\b",
        r"\bare\s+pending\b",
        r"\bremains?\s+pending\b",
        r"\bpending\s+approval\b",
        r"\bpending\b",
        r"\b(?:still\s+)?not\s+(?:yet\s+)?confirmed\b",
        r"\b(?:is|are|was|were)\s+not\s+(?:yet\s+)?confirmed\b",
        r"\bnot\s+confirmed\b",
        r"\b(?:still\s+)?not\s+(?:yet\s+)?finalized\b",
        r"\b(?:is|are|was|were)\s+not\s+(?:yet\s+)?finalized\b",
        r"\bnot\s+finalized\b",
        r"\b(?:still\s+)?undecided\b",
        r"\b(?:is|are)\s+undecided\b",
        r"\bawaiting\s+approval\b",
        r"\bwaiting\s+for\s+approval\b",
        r"\bneeds?\s+approval\b",
        r"\bneeds?\s+(?:further\s+)?discussion\b",
        r"\bneed\s+(?:further\s+)?discussion\b",
        r"\bopen\s+(?:question|issue)\b",
        r"\bstill\s+unclear\b",
        r"\bunclear\b",
    )

    _DECISION_PHRASES = (
        r"\bagreed\s+(?:to|on|that|upon)\b",
        r"\bagreed\b",
        r"\bdecided\s+(?:to|on|that|upon)\b",
        r"\bdecided\b",
        r"\bapproved\s+(?:to|that)?\b",
        r"\bconfirmed\s+(?:to|that)?\b",
        r"\bfinalized\s+(?:to|that)?\b",
        r"\bselected\s+(?:to|that)?\b",
        r"\bchose\s+(?:to|that)?\b",
        r"\bchosen\s+(?:to|that)?\b",
        r"\bwill\s+proceed\s+with\b",
        r"\bshall\s+proceed\s+with\b",
        r"\bproceed\s+with\b",
        r"\blet'?s\s+go\s+with\b",
        r"\bfinal\s+choice\s+is\b",
        r"\bfinal\s+decision\s+is\b",
        r"\bcommittee\s+accepted\b",
        r"\bteam\s+accepted\b",
        r"\beveryone\s+agreed\b",
        r"\bthat'?s\s+settled\b",
    )

    _ACTION_PHRASES = (
        r"\b(?:is|are|was|were)\s+responsible\s+for\b",
        r"\bresponsible\s+for\b",
        r"\b(?:is|are|was|were)\s+assigned\s+to\b",
        r"\bassigned\s+to\b",
        r"\b(?:is|are|was|were)\s+tasked\s+with\b",
        r"\btasked\s+with\b",
        r"\b(?:need|needs|needed|has|have|had)\s+to\b",
        r"\b(?:will|shall|plan\s+to|plans\s+to|planning\s+to|going\s+to)\b",
        r"\b(?:can|could|would)\s+you\b",
    )

    @classmethod
    def normalize_sentence(cls, text: str, category: CategoryType = "generic") -> str:
        """Strip punctuation, category markers, and normalize spaces."""
        text = text.strip()
        # Remove possessives (e.g., guest's -> guest)
        text = re.sub(r"['’]s\b", "", text)
        text = re.sub(r"['’]", "", text)

        # Normalize category marker phrases
        if category == "unresolved_issues":
            for pattern in cls._UNRESOLVED_PHRASES:
                text = re.sub(pattern, " ", text, flags=re.IGNORECASE)
        elif category == "decisions":
            for pattern in cls._DECISION_PHRASES:
                text = re.sub(pattern, " ", text, flags=re.IGNORECASE)
        elif category == "action_items":
            for pattern in cls._ACTION_PHRASES:
                text = re.sub(pattern, " ", text, flags=re.IGNORECASE)

        # Replace non-alphanumeric with spaces
        text = re.sub(r"[^\w\s]", " ", text)
        return " ".join(text.split())

    @classmethod
    def stem_token(cls, word: str) -> str:
        """Lightweight, deterministic stemming for common English suffixes."""
        word = word.lower()
        if len(word) <= 3:
            return word

        # Normalize common gerunds / participles
        if word.endswith("ing"):
            base = word[:-3]
            if len(base) >= 3:
                # e.g., preparing -> prepar -> prepare
                if base.endswith("ar") or base.endswith("iz") or base.endswith("at") or base.endswith("ul"):
                    return base + "e"
                # double consonant e.g. planning -> plan
                if len(base) >= 3 and base[-1] == base[-2] and base[-1] in "bcdgmnprt":
                    return base[:-1]
                return base

        # Normalize past tense / participles
        if word.endswith("ed"):
            base = word[:-2]
            if len(base) >= 3:
                if base.endswith("e"):
                    return base
                if base.endswith("i"):  # e.g. clarified -> clarify
                    return base[:-1] + "y"
                if len(base) >= 3 and base[-1] == base[-2] and base[-1] in "bcdgmnprt":
                    return base[:-1]
                return base + "e" if base[-1] in "cglsvz" else base

        # Normalize plurals
        if word.endswith("ies") and len(word) > 4:
            return word[:-3] + "y"
        if word.endswith("es") and len(word) > 4:
            return word[:-2]
        if word.endswith("s") and not word.endswith("ss") and len(word) > 3:
            return word[:-1]

        return word

    @classmethod
    def extract_semantic_tokens(cls, text: str, category: CategoryType = "generic") -> set[str]:
        """Extract stemmed, stopword-filtered core tokens for a text under a category."""
        normalized = cls.normalize_sentence(text, category)
        words = re.findall(r"\w+", normalized.lower())
        tokens = set()
        for word in words:
            if word not in cls._STOPWORDS and len(word) > 1:
                tokens.add(cls.stem_token(word))
        return tokens

    @classmethod
    def semantic_similarity(cls, left: str, right: str, category: CategoryType = "generic") -> float:
        """Calculate explainable semantic similarity between two texts.

        Uses Jaccard overlap on category-normalized, stemmed core entity/action tokens.
        If both sets are non-empty and one is a subset of the other with strong overlap,
        takes the maximum of Jaccard and containment Dice score.
        """
        left_tokens = cls.extract_semantic_tokens(left, category)
        right_tokens = cls.extract_semantic_tokens(right, category)

        if not left_tokens or not right_tokens:
            return 0.0

        intersection = len(left_tokens & right_tokens)
        if intersection == 0:
            return 0.0

        union = len(left_tokens | right_tokens)
        jaccard = intersection / union

        # Also consider containment if one is an exact semantic subset of the other
        min_len = min(len(left_tokens), len(right_tokens))
        containment = intersection / min_len if min_len > 0 else 0.0

        # Require meaningful shared content: at least 2 tokens or full containment of 1 token
        if min_len == 1 and intersection < 1:
            return 0.0

        # Conservative score: weight Jaccard primarily, allowing containment to boost only when
        # core concepts are shared (e.g. task with added deadline/details)
        if containment >= 0.75 and jaccard >= 0.4:
            return max(jaccard, (jaccard + containment) / 2)

        return jaccard

    @classmethod
    def is_semantic_match(
        cls,
        prediction: str,
        reference: str,
        category: CategoryType = "generic",
        threshold: float = 0.5,
    ) -> bool:
        """Return True if the semantic similarity satisfies the threshold."""
        return cls.semantic_similarity(prediction, reference, category) >= threshold

    @classmethod
    def count_semantic_matches(
        cls,
        predicted: list[str],
        reference: list[str],
        category: CategoryType = "generic",
        threshold: float = 0.5,
    ) -> int:
        """Count one-to-one greedy matches using semantic similarity."""
        unmatched_references = list(reference)
        matches = 0
        for prediction in predicted:
            best_match = None
            best_score = 0.0
            for ref_item in unmatched_references:
                score = cls.semantic_similarity(prediction, ref_item, category)
                if score >= threshold and score > best_score:
                    best_score = score
                    best_match = ref_item

            if best_match is not None:
                unmatched_references.remove(best_match)
                matches += 1

        return matches
