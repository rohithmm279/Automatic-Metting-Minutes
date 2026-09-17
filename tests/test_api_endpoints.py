"""Unit tests for FastAPI endpoints using TestClient with isolated database and mocked AI."""

from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient
from backend.main import app
from backend.database.repository import MeetingRepository
from backend.models.meeting import ActionItem, Decision, UnresolvedIssue, MeetingOutput


class TestAPIEndpoints(unittest.TestCase):
    """Test all FastAPI routes and error cases using TestClient."""

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.db_path = Path(cls.temp_dir.name) / "test_api.db"
        cls.repo = MeetingRepository(db_path=cls.db_path)

        # Mock orchestrator
        cls.mock_orchestrator = MagicMock()
        cls.sample_output = MeetingOutput(
            summary="Discussion of student club activities and budget.",
            action_items=[
                ActionItem(task="Submit expense report", owner="Alex", deadline="Monday", status="pending", confidence=1.0),
                ActionItem(task="Coordinate logistics", owner="Jordan", deadline="Wednesday", status="pending", confidence=0.9),
            ],
            decisions=[
                Decision(decision="Approved $300 for club orientation", confidence=1.0),
            ],
            unresolved_issues=[
                UnresolvedIssue(issue="Room reservation still pending confirmation", confidence=0.8),
            ],
        )
        cls.mock_orchestrator.analyze.return_value = cls.sample_output

        # Inject into app state
        app.state.repository = cls.repo
        app.state.orchestrator = cls.mock_orchestrator
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        cls.temp_dir.cleanup()

    def test_01_health_checks(self):
        """Test GET / and GET /health."""
        resp1 = self.client.get("/")
        self.assertEqual(resp1.status_code, 200)
        self.assertEqual(resp1.json()["status"], "ok")

        resp2 = self.client.get("/health")
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(resp2.json()["status"], "ok")

    def test_02_create_meeting_success(self):
        """Test POST /meetings with valid transcript creates meeting and returns 201."""
        transcript = (
            "Alex: We need to submit expense report by Monday.\n"
            "Jordan: I will coordinate logistics by Wednesday.\n"
            "Alex: We agreed to approve $300 for orientation.\n"
            "Jordan: Room reservation still pending."
        )
        resp = self.client.post("/meetings", json={"transcript": transcript})
        self.assertEqual(resp.status_code, 201)
        data = resp.json()

        self.assertIn("meeting_id", data)
        self.assertIsInstance(data["meeting_id"], int)
        self.assertEqual(data["summary"], self.sample_output.summary)
        self.assertEqual(len(data["action_items"]), 2)
        self.assertEqual(data["action_items"][0]["task"], "Submit expense report")
        self.assertEqual(len(data["decisions"]), 1)
        self.assertEqual(len(data["unresolved_issues"]), 1)
        self.assertIn("created_at", data)

    def test_03_list_meetings(self):
        """Test GET /meetings returns stored meetings."""
        resp = self.client.get("/meetings")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIsInstance(data, list)
        self.assertGreaterEqual(len(data), 1)

        first = data[0]
        self.assertIn("id", first)
        self.assertIn("summary", first)
        self.assertIn("action_items_count", first)
        self.assertIn("decisions_count", first)
        self.assertIn("unresolved_issues_count", first)

    def test_04_get_meeting_detail(self):
        """Test GET /meetings/{id} returns complete meeting details."""
        # Create a meeting first
        created_resp = self.client.post("/meetings", json={"transcript": "Sample transcript text"})
        meeting_id = created_resp.json()["meeting_id"]

        resp = self.client.get(f"/meetings/{meeting_id}")
        self.assertEqual(resp.status_code, 200)
        detail = resp.json()
        self.assertEqual(detail["id"], meeting_id)
        self.assertEqual(detail["summary"], self.sample_output.summary)
        self.assertEqual(len(detail["action_items"]), 2)
        self.assertEqual(len(detail["decisions"]), 1)
        self.assertEqual(len(detail["unresolved_issues"]), 1)

    def test_05_update_action_item_status(self):
        """Test PATCH /meetings/{id}/action-items/{item_id}/status."""
        created_resp = self.client.post("/meetings", json={"transcript": "Sample transcript text"})
        meeting_id = created_resp.json()["meeting_id"]

        detail = self.client.get(f"/meetings/{meeting_id}").json()
        item_id = detail["action_items"][0]["id"]

        # Update to completed
        patch_resp = self.client.patch(
            f"/meetings/{meeting_id}/action-items/{item_id}/status",
            json={"status": "completed"},
        )
        self.assertEqual(patch_resp.status_code, 200)
        patch_data = patch_resp.json()
        self.assertEqual(patch_data["action_item_id"], item_id)
        self.assertEqual(patch_data["status"], "completed")
        self.assertTrue(patch_data["updated"])

        # Verify through GET
        updated_detail = self.client.get(f"/meetings/{meeting_id}").json()
        target = next(it for it in updated_detail["action_items"] if it["id"] == item_id)
        self.assertEqual(target["status"], "completed")

    def test_06_delete_meeting_and_cascade(self):
        """Test DELETE /meetings/{id}: deletes meeting and confirms cascade deletion."""
        # 1. Create meeting
        created_resp = self.client.post("/meetings", json={"transcript": "Meeting to be deleted"})
        self.assertEqual(created_resp.status_code, 201)
        meeting_id = created_resp.json()["meeting_id"]

        # 2. Confirm it exists
        get_resp = self.client.get(f"/meetings/{meeting_id}")
        self.assertEqual(get_resp.status_code, 200)
        self.assertEqual(len(get_resp.json()["action_items"]), 2)

        # 3. Delete it
        del_resp = self.client.delete(f"/meetings/{meeting_id}")
        self.assertEqual(del_resp.status_code, 204)
        self.assertEqual(del_resp.text, "")

        # 4. Confirm it can no longer be retrieved (404)
        get_after_resp = self.client.get(f"/meetings/{meeting_id}")
        self.assertEqual(get_after_resp.status_code, 404)
        self.assertIn(f"Meeting {meeting_id} not found", get_after_resp.json()["detail"])

        # 5. Confirm child records are purged via repository and direct query
        child_items = self.repo.get_action_items(meeting_id)
        child_decisions = self.repo.get_decisions(meeting_id)
        child_issues = self.repo.get_unresolved_issues(meeting_id)
        self.assertEqual(len(child_items), 0)
        self.assertEqual(len(child_decisions), 0)
        self.assertEqual(len(child_issues), 0)

    def test_07_delete_nonexistent_meeting(self):
        """Test DELETE /meetings/99999 returns 404."""
        resp = self.client.delete("/meetings/99999")
        self.assertEqual(resp.status_code, 404)
        self.assertIn("Meeting 99999 not found", resp.json()["detail"])

    def test_08_get_nonexistent_meeting(self):
        """Test GET /meetings/99999 returns 404."""
        resp = self.client.get("/meetings/99999")
        self.assertEqual(resp.status_code, 404)
        self.assertIn("Meeting 99999 not found", resp.json()["detail"])

    def test_09_validation_errors(self):
        """Test validation 422 errors for bad inputs."""
        # Empty transcript
        resp_empty = self.client.post("/meetings", json={"transcript": ""})
        self.assertEqual(resp_empty.status_code, 422)

        # Whitespace-only transcript
        resp_ws = self.client.post("/meetings", json={"transcript": "   \n\t  "})
        self.assertEqual(resp_ws.status_code, 422)

        # Missing transcript key
        resp_missing = self.client.post("/meetings", json={})
        self.assertEqual(resp_missing.status_code, 422)

    def test_10_patch_validation_and_errors(self):
        """Test PATCH errors: invalid status, non-existent item, non-existent meeting."""
        # Create a meeting
        created_resp = self.client.post("/meetings", json={"transcript": "Patch error test"})
        meeting_id = created_resp.json()["meeting_id"]
        item_id = created_resp.json()["action_items"][0]["id"]

        # Invalid status -> 422
        resp_bad_status = self.client.patch(
            f"/meetings/{meeting_id}/action-items/{item_id}/status",
            json={"status": "invalid_status_xyz"},
        )
        self.assertEqual(resp_bad_status.status_code, 422)

        # Item not in meeting -> 404
        resp_bad_item = self.client.patch(
            f"/meetings/{meeting_id}/action-items/999999/status",
            json={"status": "completed"},
        )
        self.assertEqual(resp_bad_item.status_code, 404)

        # Meeting not found -> 404
        resp_bad_meeting = self.client.patch(
            "/meetings/99999/action-items/1/status",
            json={"status": "completed"},
        )
        self.assertEqual(resp_bad_meeting.status_code, 404)

    def test_11_action_item_evidence_exposed_in_create_meeting(self):
        """Test POST /meetings returns action item evidence when present and None when absent."""
        custom_output = MeetingOutput(
            summary="Meeting with action items containing evidence.",
            action_items=[
                ActionItem(
                    task="Prepare slides",
                    owner="Sam",
                    deadline="Thursday",
                    status="pending",
                    confidence=0.95,
                    evidence="Sam will prepare the slide deck by Thursday.",
                ),
                ActionItem(
                    task="Book room",
                    owner="Taylor",
                    deadline=None,
                    status="pending",
                    confidence=0.85,
                    evidence=None,
                ),
            ],
            decisions=[],
            unresolved_issues=[],
        )
        self.mock_orchestrator.analyze.return_value = custom_output
        resp = self.client.post("/meetings", json={"transcript": "Sam: I will prepare slides by Thursday."})
        self.assertEqual(resp.status_code, 201)
        data = resp.json()

        items = data["action_items"]
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["task"], "Prepare slides")
        self.assertEqual(items[0]["evidence"], "Sam will prepare the slide deck by Thursday.")
        self.assertEqual(items[1]["task"], "Book room")
        self.assertIsNone(items[1]["evidence"])

        # Reset mock
        self.mock_orchestrator.analyze.return_value = self.sample_output

    def test_12_persisted_evidence_retrieved_via_get_detail(self):
        """Test GET /meetings/{id} exposes persisted evidence from the database."""
        custom_output = MeetingOutput(
            summary="Meeting testing retrieval of persisted evidence.",
            action_items=[
                ActionItem(
                    task="Submit draft",
                    owner="Morgan",
                    deadline="Friday",
                    status="pending",
                    confidence=1.0,
                    evidence="Morgan: I'll submit the final draft by Friday.",
                ),
            ],
            decisions=[],
            unresolved_issues=[],
        )
        self.mock_orchestrator.analyze.return_value = custom_output
        create_resp = self.client.post("/meetings", json={"transcript": "Morgan: I'll submit the final draft by Friday."})
        meeting_id = create_resp.json()["meeting_id"]

        get_resp = self.client.get(f"/meetings/{meeting_id}")
        self.assertEqual(get_resp.status_code, 200)
        detail = get_resp.json()
        self.assertEqual(len(detail["action_items"]), 1)
        self.assertEqual(detail["action_items"][0]["evidence"], "Morgan: I'll submit the final draft by Friday.")

        # Reset mock
        self.mock_orchestrator.analyze.return_value = self.sample_output

    def test_13_action_item_without_evidence_has_null_evidence(self):
        """Test backward compatibility: action items without evidence return null/None for evidence."""
        # Using default self.sample_output which has no evidence
        create_resp = self.client.post("/meetings", json={"transcript": "Default sample meeting transcript."})
        self.assertEqual(create_resp.status_code, 201)
        items = create_resp.json()["action_items"]
        for item in items:
            self.assertIn("evidence", item)
            self.assertIsNone(item["evidence"])

    def test_14_action_item_status_lifecycle_and_field_immutability(self):
        """Test full action-item lifecycle (pending -> in_progress -> completed) and verify field immutability."""
        custom_output = MeetingOutput(
            summary="Lifecycle verification meeting.",
            action_items=[
                ActionItem(
                    task="Conduct security audit",
                    owner="Alex",
                    deadline="End of Q3",
                    status="pending",
                    confidence=0.95,
                    evidence="Alex: I will conduct the security audit by End of Q3.",
                ),
            ],
            decisions=[],
            unresolved_issues=[],
        )
        self.mock_orchestrator.analyze.return_value = custom_output

        # 1. Create meeting
        create_resp = self.client.post("/meetings", json={"transcript": "Alex: I will conduct the security audit by End of Q3."})
        self.assertEqual(create_resp.status_code, 201)
        meeting_id = create_resp.json()["meeting_id"]
        item_id = create_resp.json()["action_items"][0]["id"]

        # Initial check
        init_detail = self.client.get(f"/meetings/{meeting_id}").json()
        init_item = init_detail["action_items"][0]
        self.assertEqual(init_item["status"], "pending")
        self.assertEqual(init_item["task"], "Conduct security audit")
        self.assertEqual(init_item["owner"], "Alex")
        self.assertEqual(init_item["deadline"], "End of Q3")
        self.assertEqual(init_item["confidence"], 0.95)
        self.assertEqual(init_item["evidence"], "Alex: I will conduct the security audit by End of Q3.")
        self.assertEqual(init_item["meeting_id"], meeting_id)

        # 2. Transition pending -> in_progress
        patch_resp1 = self.client.patch(
            f"/meetings/{meeting_id}/action-items/{item_id}/status",
            json={"status": "in_progress"},
        )
        self.assertEqual(patch_resp1.status_code, 200)
        self.assertEqual(patch_resp1.json()["action_item_id"], item_id)
        self.assertEqual(patch_resp1.json()["status"], "in_progress")
        self.assertTrue(patch_resp1.json()["updated"])

        # Verify via GET detail endpoint
        step1_detail = self.client.get(f"/meetings/{meeting_id}").json()
        step1_item = step1_detail["action_items"][0]
        self.assertEqual(step1_item["status"], "in_progress")
        self.assertEqual(step1_item["task"], "Conduct security audit")
        self.assertEqual(step1_item["owner"], "Alex")
        self.assertEqual(step1_item["deadline"], "End of Q3")
        self.assertEqual(step1_item["confidence"], 0.95)
        self.assertEqual(step1_item["evidence"], "Alex: I will conduct the security audit by End of Q3.")
        self.assertEqual(step1_item["meeting_id"], meeting_id)

        # 3. Transition in_progress -> completed
        patch_resp2 = self.client.patch(
            f"/meetings/{meeting_id}/action-items/{item_id}/status",
            json={"status": "completed"},
        )
        self.assertEqual(patch_resp2.status_code, 200)
        self.assertEqual(patch_resp2.json()["action_item_id"], item_id)
        self.assertEqual(patch_resp2.json()["status"], "completed")
        self.assertTrue(patch_resp2.json()["updated"])

        # Verify via GET detail endpoint
        step2_detail = self.client.get(f"/meetings/{meeting_id}").json()
        step2_item = step2_detail["action_items"][0]
        self.assertEqual(step2_item["status"], "completed")
        self.assertEqual(step2_item["task"], "Conduct security audit")
        self.assertEqual(step2_item["owner"], "Alex")
        self.assertEqual(step2_item["deadline"], "End of Q3")
        self.assertEqual(step2_item["confidence"], 0.95)
        self.assertEqual(step2_item["evidence"], "Alex: I will conduct the security audit by End of Q3.")
        self.assertEqual(step2_item["meeting_id"], meeting_id)

        # 4. Verify directly in SQLite repository
        db_items = self.repo.get_action_items(meeting_id)
        self.assertEqual(len(db_items), 1)
        self.assertEqual(db_items[0]["status"], "completed")
        self.assertEqual(db_items[0]["task"], "Conduct security audit")
        self.assertEqual(db_items[0]["owner"], "Alex")
        self.assertEqual(db_items[0]["deadline"], "End of Q3")
        self.assertEqual(db_items[0]["confidence"], 0.95)
        self.assertEqual(db_items[0]["evidence"], "Alex: I will conduct the security audit by End of Q3.")
        self.assertEqual(db_items[0]["meeting_id"], meeting_id)

        # Reset mock
        self.mock_orchestrator.analyze.return_value = self.sample_output


if __name__ == "__main__":
    unittest.main()

