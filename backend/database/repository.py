"""Repository layer for persisting and querying meeting outputs."""

from pathlib import Path
import re
import sqlite3
from typing import Any

from backend.database.connection import get_connection, DEFAULT_DB_PATH
from backend.database.schema import init_db
from backend.models.meeting import MeetingOutput, ActionItem, Decision, UnresolvedIssue

# Optional import — only needed when persisting agentic-pipeline output.
# Imported lazily in save_meeting_analysis to avoid circular deps if the
# agentic stack is not installed.
try:
    from app.schemas.meeting_schema import MeetingAnalysis as AgenticMeetingAnalysis
except ImportError:
    AgenticMeetingAnalysis = None  # type: ignore[assignment,misc]


def _parse_iso_date(date_str: str | None) -> str | None:
    if not date_str:
        return None
    m_iso = re.search(r'\b(\d{4})-(\d{1,2})-(\d{1,2})\b', date_str)
    if m_iso:
        return f"{int(m_iso.group(1)):04d}-{int(m_iso.group(2)):02d}-{int(m_iso.group(3)):02d}"
    _MONTHS = {
        "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
        "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "sept": 9,
        "oct": 10, "nov": 11, "dec": 12,
    }
    m_text = re.search(r'\b([A-Za-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})\b', date_str)
    if m_text and m_text.group(1).lower() in _MONTHS:
        return f"{int(m_text.group(3)):04d}-{_MONTHS[m_text.group(1).lower()]:02d}-{int(m_text.group(2)):02d}"
    m_day = re.search(r'\b(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]+),?\s+(\d{4})\b', date_str)
    if m_day and m_day.group(2).lower() in _MONTHS:
        return f"{int(m_day.group(3)):04d}-{_MONTHS[m_day.group(2).lower()]:02d}-{int(m_day.group(1)):02d}"
    return None


def _parse_time_hms(time_str: str | None) -> str | None:
    if not time_str:
        return None
    m_12 = re.search(r'\b(\d{1,2})(?::(\d{2}))?\s*(AM|PM|am|pm)\b', time_str, re.IGNORECASE)
    if m_12:
        hour = int(m_12.group(1))
        minute = int(m_12.group(2)) if m_12.group(2) else 0
        ampm = m_12.group(3).upper()
        if ampm == "PM" and hour < 12:
            hour += 12
        elif ampm == "AM" and hour == 12:
            hour = 0
        return f"{hour:02d}:{minute:02d}:00"
    m_24 = re.search(r'\b(\d{1,2}):(\d{2})(?::(\d{2}))?\b', time_str)
    if m_24:
        hour = int(m_24.group(1))
        minute = int(m_24.group(2))
        second = int(m_24.group(3)) if m_24.group(3) else 0
        return f"{hour:02d}:{minute:02d}:{second:02d}"
    return None


def _extract_header_timestamp(obj: Any, transcript: str = "") -> str | None:
    """Compute header timestamp from meeting_date and start_time/meeting_time if present."""
    m_date = getattr(obj, "meeting_date", None)
    s_time = getattr(obj, "start_time", None) or getattr(obj, "meeting_time", None)

    # If not on obj, check transcript header area
    if not m_date and transcript:
        m_d_match = re.search(r'(?i)\*{0,2}(?:Date(?:\s*/\s*Time)?)\*{0,2}\s*[:\-]?\*{0,2}\s*([^\n\r]+)', transcript[:500])
        if m_d_match:
            m_date = m_d_match.group(1).strip()
    if not s_time and transcript:
        m_t_match = re.search(r'(?i)\*{0,2}(?:Time|Schedule|Start\s*Time)\*{0,2}\s*[:\-]?\*{0,2}\s*([^\n\r]+)', transcript[:500])
        if m_t_match:
            s_time = m_t_match.group(1).strip()

    iso_d = _parse_iso_date(m_date)
    hms = _parse_time_hms(s_time)

    if iso_d and hms:
        return f"{iso_d} {hms}"
    if iso_d:
        return f"{iso_d} 00:00:00"
    return None


class MeetingRepository:
    """Repository handling all database operations for meetings and child records."""

    def __init__(self, db_path: str | Path | None = None):
        self.db_path = Path(db_path) if db_path is not None else DEFAULT_DB_PATH
        # Ensure schema exists
        init_db(db_path=self.db_path)

    def _get_connection(self) -> sqlite3.Connection:
        return get_connection(self.db_path)

    def save_meeting(self, transcript: str, meeting_output: MeetingOutput) -> int:
        """Save a complete MeetingOutput and transcript in a single atomic transaction.

        If any insertion fails, the entire transaction is rolled back.
        Returns:
            int: The primary key ID of the inserted meeting.
        """
        conn = self._get_connection()
        header_ts = _extract_header_timestamp(meeting_output, transcript)
        try:
            with conn:
                cursor = conn.cursor()

                # 1. Insert parent meeting record
                if getattr(meeting_output, 'created_at', None):
                    cursor.execute(
                        """
                        INSERT INTO meetings 
                            (transcript, summary, title, meeting_date, meeting_time, start_time, end_time, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                        """,
                        (
                            transcript,
                            meeting_output.summary,
                            getattr(meeting_output, 'title', None),
                            getattr(meeting_output, 'meeting_date', None),
                            getattr(meeting_output, 'meeting_time', None),
                            getattr(meeting_output, 'start_time', None),
                            getattr(meeting_output, 'end_time', None),
                            meeting_output.created_at,
                        ),
                    )
                else:
                    cursor.execute(
                        """
                        INSERT INTO meetings 
                            (transcript, summary, title, meeting_date, meeting_time, start_time, end_time)
                        VALUES (?, ?, ?, ?, ?, ?, ?);
                        """,
                        (
                            transcript,
                            meeting_output.summary,
                            getattr(meeting_output, 'title', None),
                            getattr(meeting_output, 'meeting_date', None),
                            getattr(meeting_output, 'meeting_time', None),
                            getattr(meeting_output, 'start_time', None),
                            getattr(meeting_output, 'end_time', None),
                        ),
                    )
                meeting_id = cursor.lastrowid
                if meeting_id is None:
                    raise RuntimeError("Failed to obtain lastrowid for inserted meeting.")

                # 2. Insert action items (evidence is optional — None if not set)
                if meeting_output.action_items:
                    cursor.executemany(
                        """
                        INSERT INTO action_items
                            (meeting_id, task, owner, deadline, status, confidence, evidence)
                        VALUES (?, ?, ?, ?, ?, ?, ?);
                        """,
                        [
                            (
                                meeting_id,
                                item.task,
                                item.owner if item.owner is not None else None,
                                item.deadline if item.deadline is not None else None,
                                item.status or "pending",
                                float(item.confidence) if item.confidence is not None else 1.0,
                                getattr(item, "evidence", None),
                            )
                            for item in meeting_output.action_items
                        ],
                    )

                # 3. Insert decisions
                if meeting_output.decisions:
                    cursor.executemany(
                        """
                        INSERT INTO decisions (meeting_id, decision, confidence)
                        VALUES (?, ?, ?);
                        """,
                        [
                            (
                                meeting_id,
                                dec.decision,
                                float(dec.confidence) if dec.confidence is not None else 1.0,
                            )
                            for dec in meeting_output.decisions
                        ],
                    )

                # 4. Insert unresolved issues
                if meeting_output.unresolved_issues:
                    cursor.executemany(
                        """
                        INSERT INTO unresolved_issues (meeting_id, issue, confidence)
                        VALUES (?, ?, ?);
                        """,
                        [
                            (
                                meeting_id,
                                issue.issue,
                                float(issue.confidence) if issue.confidence is not None else 1.0,
                            )
                            for issue in meeting_output.unresolved_issues
                        ],
                    )

                return meeting_id
        finally:
            conn.close()

    def get_meeting(self, meeting_id: int) -> dict[str, Any] | None:
        """Retrieve a complete meeting record by ID, including all child records."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, transcript, summary, title, meeting_date, meeting_time, start_time, end_time, created_at 
                FROM meetings WHERE id = ?;
                """,
                (meeting_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return None

            meeting = dict(row)
            meeting["action_items"] = self.get_action_items(meeting_id, conn=conn)
            meeting["decisions"] = self.get_decisions(meeting_id, conn=conn)
            meeting["unresolved_issues"] = self.get_unresolved_issues(meeting_id, conn=conn)
            return meeting
        finally:
            conn.close()

    def list_meetings(self, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        """List meetings ordered by newest first with counts of child items."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT 
                    m.id,
                    m.summary,
                    m.title,
                    m.meeting_date,
                    m.meeting_time,
                    m.start_time,
                    m.end_time,
                    m.created_at,
                    COUNT(DISTINCT a.id) AS action_items_count,
                    COUNT(DISTINCT d.id) AS decisions_count,
                    COUNT(DISTINCT u.id) AS unresolved_issues_count
                FROM meetings m
                LEFT JOIN action_items a ON m.id = a.meeting_id
                LEFT JOIN decisions d ON m.id = d.meeting_id
                LEFT JOIN unresolved_issues u ON m.id = u.meeting_id
                GROUP BY m.id
                ORDER BY m.id DESC
                LIMIT ? OFFSET ?;
                """,
                (limit, offset),
            )
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_action_items(
        self, meeting_id: int, conn: sqlite3.Connection | None = None
    ) -> list[dict[str, Any]]:
        """Retrieve all action items for a given meeting."""
        should_close = False
        if conn is None:
            conn = self._get_connection()
            should_close = True
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, meeting_id, task, owner, deadline, status, confidence, evidence
                FROM action_items
                WHERE meeting_id = ?
                ORDER BY id ASC;
                """,
                (meeting_id,),
            )
            return [dict(row) for row in cursor.fetchall()]
        finally:
            if should_close:
                conn.close()

    def get_decisions(
        self, meeting_id: int, conn: sqlite3.Connection | None = None
    ) -> list[dict[str, Any]]:
        """Retrieve all decisions for a given meeting."""
        should_close = False
        if conn is None:
            conn = self._get_connection()
            should_close = True
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, meeting_id, decision, confidence
                FROM decisions
                WHERE meeting_id = ?
                ORDER BY id ASC;
                """,
                (meeting_id,),
            )
            return [dict(row) for row in cursor.fetchall()]
        finally:
            if should_close:
                conn.close()

    def get_unresolved_issues(
        self, meeting_id: int, conn: sqlite3.Connection | None = None
    ) -> list[dict[str, Any]]:
        """Retrieve all unresolved issues for a given meeting."""
        should_close = False
        if conn is None:
            conn = self._get_connection()
            should_close = True
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, meeting_id, issue, confidence
                FROM unresolved_issues
                WHERE meeting_id = ?
                ORDER BY id ASC;
                """,
                (meeting_id,),
            )
            return [dict(row) for row in cursor.fetchall()]
        finally:
            if should_close:
                conn.close()

    def update_action_item_status(self, action_item_id: int, status: str) -> bool:
        """Update the status of an existing action item."""
        conn = self._get_connection()
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE action_items SET status = ? WHERE id = ?;",
                    (status, action_item_id),
                )
                return cursor.rowcount > 0
        finally:
            conn.close()

    def delete_meeting(self, meeting_id: int) -> bool:
        """Delete a meeting and cascade delete all associated child records."""
        conn = self._get_connection()
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM meetings WHERE id = ?;", (meeting_id,))
                return cursor.rowcount > 0
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Agentic pipeline bridge
    # ------------------------------------------------------------------

    def save_meeting_analysis(self, transcript: str, analysis: Any) -> int:
        """Persist a MeetingAnalysis (agentic pipeline output) using the existing schema.

        Bridges the agentic-pipeline schema to the persistence layer:
          - ``analysis.decisions`` (list[str]) → decisions table
          - ``analysis.detailed_decisions`` (list[DecisionItem] | None) → decisions table
            (preferred over flat strings when present; stores evidence & confidence)
          - ``analysis.unresolved_issues`` (list[str]) → unresolved_issues table
          - ``analysis.action_items`` (list[app.schemas.meeting_schema.ActionItem])
            → action_items table (evidence & confidence stored)

        Args:
            transcript: The raw transcript string.
            analysis:   A MeetingAnalysis instance from the agentic pipeline.

        Returns:
            The integer primary key of the newly inserted meeting row.
        """
        conn = self._get_connection()
        header_ts = _extract_header_timestamp(analysis, transcript)
        try:
            with conn:
                cursor = conn.cursor()

                # 1. Insert parent meeting record
                if getattr(analysis, 'created_at', None):
                    cursor.execute(
                        """
                        INSERT INTO meetings 
                            (transcript, summary, title, meeting_date, meeting_time, start_time, end_time, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                        """,
                        (
                            transcript,
                            analysis.summary,
                            getattr(analysis, 'title', None),
                            getattr(analysis, 'meeting_date', None),
                            getattr(analysis, 'meeting_time', None),
                            getattr(analysis, 'start_time', None),
                            getattr(analysis, 'end_time', None),
                            analysis.created_at,
                        ),
                    )
                else:
                    cursor.execute(
                        """
                        INSERT INTO meetings 
                            (transcript, summary, title, meeting_date, meeting_time, start_time, end_time)
                        VALUES (?, ?, ?, ?, ?, ?, ?);
                        """,
                        (
                            transcript,
                            analysis.summary,
                            getattr(analysis, 'title', None),
                            getattr(analysis, 'meeting_date', None),
                            getattr(analysis, 'meeting_time', None),
                            getattr(analysis, 'start_time', None),
                            getattr(analysis, 'end_time', None),
                        ),
                    )
                meeting_id = cursor.lastrowid
                if meeting_id is None:
                    raise RuntimeError("Failed to obtain lastrowid for inserted meeting.")

                # 2. Insert action items (agentic ActionItem has evidence field)
                if analysis.action_items:
                    cursor.executemany(
                        """
                        INSERT INTO action_items
                            (meeting_id, task, owner, deadline, status, confidence, evidence)
                        VALUES (?, ?, ?, ?, ?, ?, ?);
                        """,
                        [
                            (
                                meeting_id,
                                item.task,
                                item.owner if item.owner not in (None, "Not specified") else None,
                                item.deadline if item.deadline not in (None, "Not specified") else None,
                                item.status or "pending",
                                float(item.confidence) if item.confidence is not None else 1.0,
                                getattr(item, "evidence", None),
                            )
                            for item in analysis.action_items
                        ],
                    )

                # 3. Insert decisions.
                #    Use detailed_decisions when available (richer: evidence + confidence);
                #    fall back to flat decision strings.
                detailed = getattr(analysis, "detailed_decisions", None)
                if detailed:
                    decision_rows = [
                        (
                            meeting_id,
                            dec.decision,
                            float(dec.confidence) if dec.confidence is not None else 1.0,
                        )
                        for dec in detailed
                        if dec.decision and dec.decision.strip()
                    ]
                elif analysis.decisions:
                    decision_rows = [
                        (meeting_id, dec_str, 1.0)
                        for dec_str in analysis.decisions
                        if dec_str and dec_str.strip()
                    ]
                else:
                    decision_rows = []

                if decision_rows:
                    cursor.executemany(
                        "INSERT INTO decisions (meeting_id, decision, confidence) VALUES (?, ?, ?);",
                        decision_rows,
                    )

                # 4. Insert unresolved issues (flat strings from agentic pipeline)
                if analysis.unresolved_issues:
                    cursor.executemany(
                        "INSERT INTO unresolved_issues (meeting_id, issue, confidence) VALUES (?, ?, ?);",
                        [
                            (meeting_id, issue_str, 1.0)
                            for issue_str in analysis.unresolved_issues
                            if issue_str and issue_str.strip()
                        ],
                    )

                return meeting_id
        finally:
            conn.close()
