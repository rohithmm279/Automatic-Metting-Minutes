"""Utilities for preparing meeting transcripts for downstream processing."""

import re


class TranscriptProcessor:
    """Clean transcript formatting without changing its content or meaning."""

    @staticmethod
    def clean_transcript(transcript: str) -> str:
        """Return a consistently formatted transcript suitable for AI processing.

        The method trims surrounding whitespace, collapses repeated horizontal
        whitespace within each line, and removes blank lines. It deliberately
        does not summarize, rewrite, or otherwise alter meeting content.

        Args:
            transcript: The raw meeting transcript.

        Returns:
            The cleaned transcript, or an empty string when the input is not a
            string.
        """
        if not isinstance(transcript, str):
            return ""

        cleaned_lines: list[str] = []
        for line in transcript.strip().splitlines():
            cleaned_line = re.sub(r"[^\S\r\n]+", " ", line).strip()
            if cleaned_line:
                cleaned_lines.append(cleaned_line)

        return "\n".join(cleaned_lines)
