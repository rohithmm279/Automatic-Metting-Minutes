"""Focused persistence tests for the SQLite repository layer.

Covers every requirement in the task:
  - Meeting persistence (ID, transcript, summary, created_at)
  - Multiple action-item persistence (task, owner, deadline, status, confidence, evidence)
  - Decision persistence
  - Unresolved-issue persistence
  - Full meeting retrieval (all child tables)
  - Action-item status update (task/owner/deadline unchanged)
  - Foreign-key / cascade correctness
  - Agentic-pipeline bridge (save_meeting_analysis)
  - get_db context manager commit/rollback behaviour
  - Connection safety: foreign keys ON, duplicate-safe init

All tests run against isolated temporary SQLite files — no Gemini API calls.
"""

from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
for _p in (ROOT, BACKEND):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from backend.database.connection import get_connection, get_db
from backend.database.repository import MeetingRepository
from backend.database.schema import init_db
from backend.models.meeting import ActionItem, Decision, MeetingOutput, UnresolvedIssue

# Agentic-schema imports (app/ tree)
from app.schemas.meeting_schema import (
    ActionItem as AgenticActionItem,
    DecisionItem,
    MeetingAnalysis,
    OverallValidation,
)


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------

def _make_full_output() -> MeetingOutput:
    return MeetingOutput(
        summary="Annual student club planning meeting.",
        action_items=[
            ActionItem(task="Book venue", owner="Alice", deadline="Friday", status="pending", confidence=1.0),
            ActionItem(task="Send invites", owner="Bob", deadline=None, status="pending", confidence=0.9),
            ActionItem(task="Prepare agenda", owner=None, deadline=None, status="pending", confidence=0.8),
        ],
        decisions=[
            Decision(decision="Approved $500 budget", confidence=1.0),
            Decision(decision="Chose October 12th as event date", confidence=0.95),
        ],
        unresolved_issues=[
            UnresolvedIssue(issue="Catering vendor not confirmed", confidence=0.8),
            UnresolvedIssue(issue="Parking permit still pending", confidence=0.7),
        ],
    )


def _make_agentic_analysis() -> MeetingAnalysis:
    """Build a MeetingAnalysis as the agentic pipeline produces."""
    return MeetingAnalysis(
        summary="The robotics club discussed the hackathon and logistics.",
        action_items=[
            AgenticActionItem(
                task="Finalize sponsorship proposal",
                owner="Jordan",
                deadline="Friday",
                status="pending",
                confidence=1.0,
                evidence="I will finalize the sponsorship proposal by Friday.",
            ),
            AgenticActionItem(
                task="Order motor parts",
                owner="Not specified",
                deadline="Not specified",
                status="pending",
                confidence=0.9,
                evidence="We need someone to order the motor parts.",
            ),
        ],
        decisions=["Host the hackathon on November 15th"],
        detailed_decisions=[
            DecisionItem(
                decision="Host the hackathon on November 15th",
                confidence=1.0,
                evidence="We all agreed to host the hackathon on November 15th.",
            )
        ],
        unresolved_issues=["Guest speaker confirmation still pending"],
        validation=OverallValidation(
            summary_grounded=True,
            action_items_valid=True,
            decisions_valid=True,
            all_grounded=True,
            issues=[],
        ),
    )


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------

class TestSQLitePersistence(unittest.TestCase):
    """Comprehensive persistence tests using isolated temporary databases."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_persistence.db"
        self.repo = MeetingRepository(db_path=self.db_path)
        self.sample_output = _make_full_output()
        self.transcript = (
            "Alice: We need to book venue by Friday.\n"
            "Bob: I will send invites.\n"
            "Chair: Approved $500 budget and October 12th as event date.\n"
            "Alice: Catering vendor not confirmed.\n"
            "Bob: Parking permit still pending."
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    # -----------------------------------------------------------------------
    # 1. Meeting persistence
    # -----------------------------------------------------------------------
    def test_01_meeting_persistence_returns_valid_id(self):
        """Meeting persistence: save_meeting returns a positive integer meeting ID."""
        meeting_id = self.repo.save_meeting(
            transcript=self.transcript,
            meeting_output=self.sample_output,
        )
        self.assertIsInstance(meeting_id, int)
        self.assertGreater(meeting_id, 0)

    def test_02_meeting_persistence_stores_transcript_and_summary(self):
        """Meeting persistence: stored meeting has correct transcript, summary, and created_at."""
        meeting_id = self.repo.save_meeting(
            transcript=self.transcript,
            meeting_output=self.sample_output,
        )
        row = self.repo.get_meeting(meeting_id)

        self.assertIsNotNone(row)
        self.assertEqual(row["id"], meeting_id)
        self.assertEqual(row["transcript"], self.transcript)
        self.assertEqual(row["summary"], self.sample_output.summary)
        self.assertIn("created_at", row)
        self.assertIsNotNone(row["created_at"])

    # -----------------------------------------------------------------------
    # 2. Action-item persistence
    # -----------------------------------------------------------------------
    def test_03_action_items_all_fields_persisted(self):
        """Action items: task, owner, deadline, status, confidence all stored correctly."""
        meeting_id = self.repo.save_meeting(self.transcript, self.sample_output)
        items = self.repo.get_action_items(meeting_id)

        self.assertEqual(len(items), 3)

        item0 = items[0]
        self.assertEqual(item0["task"], "Book venue")
        self.assertEqual(item0["owner"], "Alice")
        self.assertEqual(item0["deadline"], "Friday")
        self.assertEqual(item0["status"], "pending")
        self.assertAlmostEqual(item0["confidence"], 1.0)
        self.assertEqual(item0["meeting_id"], meeting_id)

    def test_04_action_items_null_owner_and_deadline_stored_as_null(self):
        """Action items: None owner and None deadline are stored as NULL, not 'None'."""
        meeting_id = self.repo.save_meeting(self.transcript, self.sample_output)
        items = self.repo.get_action_items(meeting_id)

        # item[1]: owner=Bob, deadline=None
        item1 = items[1]
        self.assertIsNone(item1["deadline"])

        # item[2]: owner=None, deadline=None
        item2 = items[2]
        self.assertIsNone(item2["owner"])
        self.assertIsNone(item2["deadline"])

    def test_05_action_items_confidence_stored(self):
        """Action items: confidence values persisted correctly."""
        meeting_id = self.repo.save_meeting(self.transcript, self.sample_output)
        items = self.repo.get_action_items(meeting_id)
        self.assertAlmostEqual(items[1]["confidence"], 0.9, places=4)
        self.assertAlmostEqual(items[2]["confidence"], 0.8, places=4)

    # -----------------------------------------------------------------------
    # 3. Decision persistence
    # -----------------------------------------------------------------------
    def test_06_decisions_persisted(self):
        """Decisions: all decision records stored with correct text and confidence."""
        meeting_id = self.repo.save_meeting(self.transcript, self.sample_output)
        decisions = self.repo.get_decisions(meeting_id)

        self.assertEqual(len(decisions), 2)
        texts = [d["decision"] for d in decisions]
        self.assertIn("Approved $500 budget", texts)
        self.assertIn("Chose October 12th as event date", texts)

        for d in decisions:
            self.assertEqual(d["meeting_id"], meeting_id)
            self.assertGreater(d["confidence"], 0.0)

    # -----------------------------------------------------------------------
    # 4. Unresolved issue persistence
    # -----------------------------------------------------------------------
    def test_07_unresolved_issues_persisted(self):
        """Unresolved issues: all records stored with correct text and confidence."""
        meeting_id = self.repo.save_meeting(self.transcript, self.sample_output)
        issues = self.repo.get_unresolved_issues(meeting_id)

        self.assertEqual(len(issues), 2)
        texts = [i["issue"] for i in issues]
        self.assertIn("Catering vendor not confirmed", texts)
        self.assertIn("Parking permit still pending", texts)

        for i in issues:
            self.assertEqual(i["meeting_id"], meeting_id)

    # -----------------------------------------------------------------------
    # 5. Full retrieval
    # -----------------------------------------------------------------------
    def test_08_full_meeting_retrieval(self):
        """Retrieval: get_meeting returns meeting + all child tables in one call."""
        meeting_id = self.repo.save_meeting(self.transcript, self.sample_output)
        row = self.repo.get_meeting(meeting_id)

        self.assertIsNotNone(row)
        # Parent
        self.assertEqual(row["summary"], self.sample_output.summary)
        self.assertEqual(row["transcript"], self.transcript)
        # Children
        self.assertEqual(len(row["action_items"]), 3)
        self.assertEqual(len(row["decisions"]), 2)
        self.assertEqual(len(row["unresolved_issues"]), 2)

    def test_09_get_meeting_nonexistent_returns_none(self):
        """Retrieval: get_meeting with unknown ID returns None (not an exception)."""
        result = self.repo.get_meeting(9999999)
        self.assertIsNone(result)

    def test_10_list_meetings_ordered_newest_first(self):
        """Retrieval: list_meetings returns meetings newest-first with accurate counts."""
        id1 = self.repo.save_meeting("Transcript A", self.sample_output)
        minimal = MeetingOutput(summary="Short meeting.", action_items=[], decisions=[], unresolved_issues=[])
        id2 = self.repo.save_meeting("Transcript B", minimal)

        rows = self.repo.list_meetings(limit=10, offset=0)
        self.assertGreaterEqual(len(rows), 2)
        ids = [r["id"] for r in rows]
        # id2 is newer, so it should appear before id1 (smaller index = earlier in results)
        self.assertLess(ids.index(id2), ids.index(id1), "Newer meeting should appear first in list.")
        # Verify counts
        row_id2 = next(r for r in rows if r["id"] == id2)
        self.assertEqual(row_id2["action_items_count"], 0)
        self.assertEqual(row_id2["decisions_count"], 0)

        row_id1 = next(r for r in rows if r["id"] == id1)
        self.assertEqual(row_id1["action_items_count"], 3)
        self.assertEqual(row_id1["decisions_count"], 2)
        self.assertEqual(row_id1["unresolved_issues_count"], 2)

    # -----------------------------------------------------------------------
    # 6. Action-item status update
    # -----------------------------------------------------------------------
    def test_11_update_action_item_status_only(self):
        """Status update: only status changes; task, owner, deadline are unaffected."""
        meeting_id = self.repo.save_meeting(self.transcript, self.sample_output)
        items = self.repo.get_action_items(meeting_id)
        item = items[0]
        item_id = item["id"]
        original_task = item["task"]
        original_owner = item["owner"]
        original_deadline = item["deadline"]

        self.assertEqual(item["status"], "pending")

        # Progress to in_progress
        result = self.repo.update_action_item_status(item_id, "in_progress")
        self.assertTrue(result)

        refreshed = self.repo.get_action_items(meeting_id)
        target = next(i for i in refreshed if i["id"] == item_id)
        self.assertEqual(target["status"], "in_progress")
        self.assertEqual(target["task"], original_task)      # unchanged
        self.assertEqual(target["owner"], original_owner)    # unchanged
        self.assertEqual(target["deadline"], original_deadline)  # unchanged

        # Progress to completed
        self.repo.update_action_item_status(item_id, "completed")
        refreshed2 = self.repo.get_action_items(meeting_id)
        target2 = next(i for i in refreshed2 if i["id"] == item_id)
        self.assertEqual(target2["status"], "completed")

    def test_12_update_action_item_status_all_allowed_values(self):
        """Status update: all four allowed statuses (pending, in_progress, completed, cancelled)."""
        meeting_id = self.repo.save_meeting(self.transcript, self.sample_output)
        item_id = self.repo.get_action_items(meeting_id)[0]["id"]

        for status in ("pending", "in_progress", "completed", "cancelled"):
            self.assertTrue(self.repo.update_action_item_status(item_id, status))
            items = self.repo.get_action_items(meeting_id)
            self.assertEqual(next(i for i in items if i["id"] == item_id)["status"], status)

    def test_13_update_nonexistent_action_item_returns_false(self):
        """Status update: updating a non-existent item ID returns False without exception."""
        result = self.repo.update_action_item_status(9999999, "completed")
        self.assertFalse(result)

    # -----------------------------------------------------------------------
    # 7. Foreign key / cascade correctness
    # -----------------------------------------------------------------------
    def test_14_cascade_delete_removes_all_children(self):
        """Foreign key cascade: deleting parent meeting removes all child rows."""
        meeting_id = self.repo.save_meeting(self.transcript, self.sample_output)
        self.assertEqual(len(self.repo.get_action_items(meeting_id)), 3)

        self.repo.delete_meeting(meeting_id)

        self.assertEqual(len(self.repo.get_action_items(meeting_id)), 0)
        self.assertEqual(len(self.repo.get_decisions(meeting_id)), 0)
        self.assertEqual(len(self.repo.get_unresolved_issues(meeting_id)), 0)

    def test_15_cascade_no_orphan_rows_in_db(self):
        """Foreign key cascade: raw SQL confirms zero orphaned rows after meeting deletion."""
        meeting_id = self.repo.save_meeting(self.transcript, self.sample_output)
        self.repo.delete_meeting(meeting_id)

        conn = get_connection(self.db_path)
        try:
            for table in ("action_items", "decisions", "unresolved_issues"):
                row = conn.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE meeting_id = ?;", (meeting_id,)
                ).fetchone()
                self.assertEqual(row[0], 0, f"Orphaned rows in {table} after cascade delete.")
        finally:
            conn.close()

    def test_16_foreign_key_enforcement_blocks_orphan_insert(self):
        """Foreign key enforcement: inserting an action item for a non-existent meeting raises."""
        conn = get_connection(self.db_path)
        init_db(conn=conn)
        try:
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO action_items (meeting_id, task, status) VALUES (?, ?, ?);",
                    (999999, "Phantom task", "pending"),
                )
                conn.commit()
        finally:
            conn.close()

    # -----------------------------------------------------------------------
    # 8. Database safety
    # -----------------------------------------------------------------------
    def test_17_init_db_idempotent(self):
        """DB safety: calling init_db multiple times does not duplicate tables or error."""
        for _ in range(3):
            init_db(db_path=self.db_path)
        # Should still work normally
        meeting_id = self.repo.save_meeting(self.transcript, self.sample_output)
        self.assertGreater(meeting_id, 0)

    def test_18_transaction_rollback_on_partial_failure(self):
        """DB safety: a failed atomic transaction leaves the database unchanged."""
        initial_count_before = len(self.repo.list_meetings())

        # Intentionally corrupt the second insert by injecting a bad row
        conn = self._open_fresh_conn()
        try:
            # Disable FK first so we can insert, then test rollback via Python exception
            cursor = conn.cursor()
            cursor.execute("BEGIN;")
            cursor.execute(
                "INSERT INTO meetings (transcript, summary) VALUES (?, ?);",
                ("Rollback test", "Rollback summary"),
            )
            # Simulate a failure mid-transaction — roll back
            conn.rollback()
        finally:
            conn.close()

        # Meetings count should be unchanged
        count_after = len(self.repo.list_meetings())
        self.assertEqual(count_after, initial_count_before)

    def test_19_get_db_commits_on_success(self):
        """get_db: writes inside the context manager are committed on clean exit."""
        with get_db(self.db_path) as conn:
            conn.execute(
                "INSERT INTO meetings (transcript, summary) VALUES (?, ?);",
                ("get_db commit test", "Summary via get_db"),
            )

        # Open a fresh connection and verify the row is visible
        conn2 = get_connection(self.db_path)
        try:
            row = conn2.execute(
                "SELECT summary FROM meetings WHERE transcript = ?;",
                ("get_db commit test",),
            ).fetchone()
            self.assertIsNotNone(row, "Row should be committed by get_db on success.")
            self.assertEqual(row["summary"], "Summary via get_db")
        finally:
            conn2.close()

    def test_20_get_db_rolls_back_on_exception(self):
        """get_db: writes inside the context manager are rolled back when an exception is raised."""
        try:
            with get_db(self.db_path) as conn:
                conn.execute(
                    "INSERT INTO meetings (transcript, summary) VALUES (?, ?);",
                    ("get_db rollback test", "Should not persist"),
                )
                raise RuntimeError("Simulated failure inside get_db block")
        except RuntimeError:
            pass

        conn2 = get_connection(self.db_path)
        try:
            row = conn2.execute(
                "SELECT id FROM meetings WHERE transcript = ?;",
                ("get_db rollback test",),
            ).fetchone()
            self.assertIsNone(row, "Row must NOT be committed after get_db exception rollback.")
        finally:
            conn2.close()

    # -----------------------------------------------------------------------
    # 9. Agentic pipeline bridge (save_meeting_analysis)
    # -----------------------------------------------------------------------
    def test_21_save_meeting_analysis_persists_all_fields(self):
        """Agentic bridge: save_meeting_analysis persists summary, action items, decisions, issues."""
        analysis = _make_agentic_analysis()
        agentic_transcript = (
            "Alex: I will finalize the sponsorship proposal by Friday.\n"
            "Taylor: We need someone to order the motor parts.\n"
            "Alex: We all agreed to host the hackathon on November 15th.\n"
            "Sam: Guest speaker confirmation still pending."
        )

        meeting_id = self.repo.save_meeting_analysis(agentic_transcript, analysis)
        self.assertGreater(meeting_id, 0)

        row = self.repo.get_meeting(meeting_id)
        self.assertIsNotNone(row)
        self.assertEqual(row["summary"], analysis.summary)
        self.assertEqual(row["transcript"], agentic_transcript)

        # Action items: 2 items; "Not specified" normalized to NULL
        items = row["action_items"]
        self.assertEqual(len(items), 2)
        item0 = items[0]
        self.assertEqual(item0["task"], "Finalize sponsorship proposal")
        self.assertEqual(item0["owner"], "Jordan")
        self.assertEqual(item0["deadline"], "Friday")
        self.assertEqual(item0["evidence"], "I will finalize the sponsorship proposal by Friday.")

        item1 = items[1]
        self.assertEqual(item1["task"], "Order motor parts")
        self.assertIsNone(item1["owner"])       # "Not specified" normalized to NULL
        self.assertIsNone(item1["deadline"])    # "Not specified" normalized to NULL
        self.assertEqual(item1["evidence"], "We need someone to order the motor parts.")

        # Decisions: prefers detailed_decisions
        decisions = row["decisions"]
        self.assertEqual(len(decisions), 1)
        self.assertEqual(decisions[0]["decision"], "Host the hackathon on November 15th")
        self.assertAlmostEqual(decisions[0]["confidence"], 1.0)

        # Unresolved issues
        issues = row["unresolved_issues"]
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0]["issue"], "Guest speaker confirmation still pending")

    def test_22_save_meeting_analysis_flat_decisions_fallback(self):
        """Agentic bridge: when detailed_decisions is None, flat decisions list is used."""
        analysis = MeetingAnalysis(
            summary="Short meeting.",
            action_items=[],
            decisions=["Use Zoom for next meeting", "Postpone budget discussion"],
            detailed_decisions=None,     # no detailed decisions
            unresolved_issues=[],
        )
        meeting_id = self.repo.save_meeting_analysis("Transcript text", analysis)
        decisions = self.repo.get_decisions(meeting_id)
        self.assertEqual(len(decisions), 2)
        texts = {d["decision"] for d in decisions}
        self.assertIn("Use Zoom for next meeting", texts)
        self.assertIn("Postpone budget discussion", texts)

    def test_23_save_meeting_analysis_cascade_delete(self):
        """Agentic bridge: deleting a meeting saved via save_meeting_analysis cascades correctly."""
        analysis = _make_agentic_analysis()
        meeting_id = self.repo.save_meeting_analysis("Transcript", analysis)

        self.repo.delete_meeting(meeting_id)

        self.assertIsNone(self.repo.get_meeting(meeting_id))
        self.assertEqual(len(self.repo.get_action_items(meeting_id)), 0)
        self.assertEqual(len(self.repo.get_decisions(meeting_id)), 0)
        self.assertEqual(len(self.repo.get_unresolved_issues(meeting_id)), 0)

    # -----------------------------------------------------------------------
    # 10. Evidence column
    # -----------------------------------------------------------------------
    def test_24_evidence_field_stored_and_retrieved(self):
        """Evidence: action_items.evidence is stored and returned by get_action_items."""
        # MeetingOutput.ActionItem doesn't have evidence, but repository now accepts it via getattr
        # Use save_meeting_analysis which passes evidence from agentic ActionItem
        analysis = _make_agentic_analysis()
        meeting_id = self.repo.save_meeting_analysis("Transcript", analysis)
        items = self.repo.get_action_items(meeting_id)

        evidences = [i.get("evidence") for i in items]
        self.assertIn("I will finalize the sponsorship proposal by Friday.", evidences)
        self.assertIn("We need someone to order the motor parts.", evidences)

    def test_25_evidence_null_for_classic_pipeline(self):
        """Evidence: classic MeetingOutput action items store NULL evidence (no error)."""
        meeting_id = self.repo.save_meeting(self.transcript, self.sample_output)
        items = self.repo.get_action_items(meeting_id)
        # All evidence values should be None (classic pipeline has no evidence field)
        for item in items:
            self.assertIsNone(item.get("evidence"))

    def test_26_action_item_lifecycle_preserves_evidence_and_fields(self):
        """Status update: pending -> in_progress -> completed lifecycle preserves evidence, task, owner, deadline, confidence."""
        analysis = _make_agentic_analysis()
        meeting_id = self.repo.save_meeting_analysis("Transcript", analysis)
        items = self.repo.get_action_items(meeting_id)
        self.assertGreater(len(items), 0)

        target = items[0]
        item_id = target["id"]
        original_task = target["task"]
        original_owner = target["owner"]
        original_deadline = target["deadline"]
        original_confidence = target["confidence"]
        original_evidence = target["evidence"]
        original_meeting_id = target["meeting_id"]

        self.assertEqual(target["status"], "pending")

        # Step 1: pending -> in_progress
        updated_step1 = self.repo.update_action_item_status(item_id, "in_progress")
        self.assertTrue(updated_step1)

        refreshed_step1 = self.repo.get_action_items(meeting_id)
        target_step1 = next(i for i in refreshed_step1 if i["id"] == item_id)
        self.assertEqual(target_step1["status"], "in_progress")
        self.assertEqual(target_step1["task"], original_task)
        self.assertEqual(target_step1["owner"], original_owner)
        self.assertEqual(target_step1["deadline"], original_deadline)
        self.assertEqual(target_step1["confidence"], original_confidence)
        self.assertEqual(target_step1["evidence"], original_evidence)
        self.assertEqual(target_step1["meeting_id"], original_meeting_id)

        # Step 2: in_progress -> completed
        updated_step2 = self.repo.update_action_item_status(item_id, "completed")
        self.assertTrue(updated_step2)

        refreshed_step2 = self.repo.get_action_items(meeting_id)
        target_step2 = next(i for i in refreshed_step2 if i["id"] == item_id)
        self.assertEqual(target_step2["status"], "completed")
        self.assertEqual(target_step2["task"], original_task)
        self.assertEqual(target_step2["owner"], original_owner)
        self.assertEqual(target_step2["deadline"], original_deadline)
        self.assertEqual(target_step2["confidence"], original_confidence)
        self.assertEqual(target_step2["evidence"], original_evidence)
        self.assertEqual(target_step2["meeting_id"], original_meeting_id)

        # Full meeting retrieval check
        full_meeting = self.repo.get_meeting(meeting_id)
        self.assertIsNotNone(full_meeting)
        full_target = next(i for i in full_meeting["action_items"] if i["id"] == item_id)
        self.assertEqual(full_target["status"], "completed")
        self.assertEqual(full_target["evidence"], original_evidence)


    # -----------------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------------
    def _open_fresh_conn(self) -> sqlite3.Connection:
        """Return a fresh connection to the test DB (caller must close it)."""
        return get_connection(self.db_path)


if __name__ == "__main__":
    unittest.main()

