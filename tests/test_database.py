"""Unit tests for the SQLite database repository layer using an isolated database."""

from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.database.repository import MeetingRepository
from backend.database.connection import get_connection
from backend.models.meeting import ActionItem, Decision, UnresolvedIssue, MeetingOutput


class TestDatabaseRepository(unittest.TestCase):
    """Test isolated database operations: insert, retrieve, list, update status, delete, cascade."""

    def setUp(self):
        # Create a unique temporary file path for the SQLite database
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_isolated.db"
        self.repo = MeetingRepository(db_path=self.db_path)

        # Sample output for reuse
        self.sample_output = MeetingOutput(
            summary="Annual general meeting summary for student club.",
            action_items=[
                ActionItem(task="Book hall", owner="Alice", deadline="Friday", status="pending", confidence=1.0),
                ActionItem(task="Buy refreshments", owner=None, deadline=None, status="pending", confidence=0.9),
            ],
            decisions=[
                Decision(decision="Approved budget of $200", confidence=1.0),
            ],
            unresolved_issues=[
                UnresolvedIssue(issue="Guest speaker availability", confidence=0.8),
            ],
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_01_insert_meeting(self):
        """Test 1: Insert meeting stores parent and child records and returns valid ID."""
        meeting_id = self.repo.save_meeting(
            transcript="Alice: We need to book the hall by Friday.",
            meeting_output=self.sample_output,
        )
        self.assertIsInstance(meeting_id, int)
        self.assertGreater(meeting_id, 0)

    def test_02_retrieve_meeting(self):
        """Test 2: Retrieve meeting fetches full parent and child records accurately."""
        transcript = "Alice: We need to book the hall by Friday."
        meeting_id = self.repo.save_meeting(transcript=transcript, meeting_output=self.sample_output)

        retrieved = self.repo.get_meeting(meeting_id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved["id"], meeting_id)
        self.assertEqual(retrieved["transcript"], transcript)
        self.assertEqual(retrieved["summary"], self.sample_output.summary)

        # Child records
        self.assertEqual(len(retrieved["action_items"]), 2)
        self.assertEqual(retrieved["action_items"][0]["task"], "Book hall")
        self.assertEqual(retrieved["action_items"][0]["owner"], "Alice")
        self.assertEqual(retrieved["action_items"][0]["deadline"], "Friday")
        self.assertIsNone(retrieved["action_items"][1]["owner"])
        self.assertIsNone(retrieved["action_items"][1]["deadline"])

        self.assertEqual(len(retrieved["decisions"]), 1)
        self.assertEqual(retrieved["decisions"][0]["decision"], "Approved budget of $200")

        self.assertEqual(len(retrieved["unresolved_issues"]), 1)
        self.assertEqual(retrieved["unresolved_issues"][0]["issue"], "Guest speaker availability")

        # Non-existent meeting returns None
        self.assertIsNone(self.repo.get_meeting(99999))

    def test_03_list_meetings(self):
        """Test 3: List meetings returns ordered records with correct item counts."""
        id1 = self.repo.save_meeting("Transcript 1", self.sample_output)

        minimal_output = MeetingOutput(
            summary="Minimal meeting without tasks.",
            action_items=[],
            decisions=[],
            unresolved_issues=[],
        )
        id2 = self.repo.save_meeting("Transcript 2", minimal_output)

        meetings = self.repo.list_meetings(limit=10, offset=0)
        self.assertEqual(len(meetings), 2)
        # Newest first
        self.assertEqual(meetings[0]["id"], id2)
        self.assertEqual(meetings[0]["action_items_count"], 0)

        self.assertEqual(meetings[1]["id"], id1)
        self.assertEqual(meetings[1]["action_items_count"], 2)
        self.assertEqual(meetings[1]["decisions_count"], 1)
        self.assertEqual(meetings[1]["unresolved_issues_count"], 1)

    def test_04_update_action_item_status(self):
        """Test 4: Update action item status successfully transitions and persists status."""
        meeting_id = self.repo.save_meeting("Sample transcript", self.sample_output)
        items = self.repo.get_action_items(meeting_id)
        self.assertGreater(len(items), 0)

        item_id = items[0]["id"]
        self.assertEqual(items[0]["status"], "pending")

        # Update to in_progress
        updated = self.repo.update_action_item_status(item_id, "in_progress")
        self.assertTrue(updated)

        refetched = self.repo.get_action_items(meeting_id)
        target = next(i for i in refetched if i["id"] == item_id)
        self.assertEqual(target["status"], "in_progress")

        # Update to completed
        self.repo.update_action_item_status(item_id, "completed")
        refetched2 = self.repo.get_action_items(meeting_id)
        target2 = next(i for i in refetched2 if i["id"] == item_id)
        self.assertEqual(target2["status"], "completed")

        # Updating non-existent item returns False
        self.assertFalse(self.repo.update_action_item_status(99999, "completed"))

    def test_05_delete_meeting(self):
        """Test 5: Delete meeting removes the meeting record and returns True."""
        meeting_id = self.repo.save_meeting("Delete test", self.sample_output)
        self.assertIsNotNone(self.repo.get_meeting(meeting_id))

        deleted = self.repo.delete_meeting(meeting_id)
        self.assertTrue(deleted)

        # Confirm no longer retrievable
        self.assertIsNone(self.repo.get_meeting(meeting_id))

        # Deleting again returns False
        self.assertFalse(self.repo.delete_meeting(meeting_id))

    def test_06_cascade_deletion(self):
        """Test 6: Deleting parent meeting cascades and removes all child records."""
        meeting_id = self.repo.save_meeting("Cascade test", self.sample_output)

        # Verify child items exist initially
        self.assertEqual(len(self.repo.get_action_items(meeting_id)), 2)
        self.assertEqual(len(self.repo.get_decisions(meeting_id)), 1)
        self.assertEqual(len(self.repo.get_unresolved_issues(meeting_id)), 1)

        # Delete parent
        self.repo.delete_meeting(meeting_id)

        # Verify child records purged via repository methods
        self.assertEqual(len(self.repo.get_action_items(meeting_id)), 0)
        self.assertEqual(len(self.repo.get_decisions(meeting_id)), 0)
        self.assertEqual(len(self.repo.get_unresolved_issues(meeting_id)), 0)

        # Directly query tables to ensure no orphaned rows exist with meeting_id
        conn = get_connection(self.db_path)
        try:
            cursor = conn.cursor()
            for table in ("action_items", "decisions", "unresolved_issues"):
                cursor.execute(f"SELECT COUNT(*) FROM {table} WHERE meeting_id = ?;", (meeting_id,))
                count = cursor.fetchone()[0]
                self.assertEqual(count, 0, f"Table {table} still has orphaned records for deleted meeting {meeting_id}")
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
