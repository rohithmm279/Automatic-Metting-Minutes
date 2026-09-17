"""Integration tests for POST /analyze-meeting agentic endpoint wired to SQLite persistence.

Tests:
  TEST A: POST /analyze-meeting with valid transcript -> HTTP 200, analysis returned, one meeting persisted.
  TEST B: Verify persisted action items match returned analysis (task, owner, deadline, status, confidence).
  TEST C: Verify decisions and unresolved issues are persisted in SQLite.
  TEST D: Verify evidence is retained in SQLite when available.
  TEST E: Verify repeated requests create distinct meeting records cleanly without corrupting previous records.
  TEST F: Simulate database failure and verify the API handles it safely (HTTP 500, no corrupted/partial writes).
"""

from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
for _p in (ROOT, BACKEND):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from fastapi.testclient import TestClient
from app.main import app
from app.schemas.meeting_schema import (
    ActionItem as AgenticActionItem,
    DecisionItem,
    MeetingAnalysis,
    OverallValidation,
)
from backend.database.repository import MeetingRepository


class TestAgenticAPIPersistence(unittest.TestCase):
    """Integration tests verifying POST /analyze-meeting auto-persists to SQLite."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_agentic_api.db"
        self.repo = MeetingRepository(db_path=self.db_path)

        # Inject repository into app state
        app.state.repository = self.repo
        self.client = TestClient(app)

        self.mock_analysis = MeetingAnalysis(
            summary="Robotics Club met to organize the Hackathon.",
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

        self.valid_transcript = (
            "Alex: Welcome to the Robotics Club planning meeting.\n"
            "Jordan: I will finalize the sponsorship proposal by Friday.\n"
            "Taylor: We need someone to order the motor parts.\n"
            "Alex: We all agreed to host the hackathon on November 15th.\n"
            "Sam: Guest speaker confirmation still pending."
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    @patch("app.main.analyze_transcript")
    def test_A_analyze_meeting_persists_one_meeting(self, mock_analyze):
        """TEST A: POST /analyze-meeting with valid transcript -> HTTP 200, analysis returned, one meeting persisted."""
        mock_analyze.return_value = self.mock_analysis

        response = self.client.post(
            "/analyze-meeting",
            json={"transcript": self.valid_transcript},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["summary"], self.mock_analysis.summary)

        # Verify exactly one meeting persisted in SQLite
        meetings = self.repo.list_meetings()
        self.assertEqual(len(meetings), 1)
        self.assertEqual(meetings[0]["summary"], self.mock_analysis.summary)

        persisted = self.repo.get_meeting(meetings[0]["id"])
        self.assertIsNotNone(persisted)
        self.assertEqual(persisted["transcript"], self.valid_transcript)
        self.assertEqual(persisted["summary"], self.mock_analysis.summary)

    @patch("app.main.analyze_transcript")
    def test_B_persisted_action_items_match_returned_analysis(self, mock_analyze):
        """TEST B: Verify persisted action items match the returned analysis."""
        mock_analyze.return_value = self.mock_analysis

        response = self.client.post(
            "/analyze-meeting",
            json={"transcript": self.valid_transcript},
        )
        self.assertEqual(response.status_code, 200)

        meetings = self.repo.list_meetings()
        meeting_id = meetings[0]["id"]
        persisted_items = self.repo.get_action_items(meeting_id)

        self.assertEqual(len(persisted_items), 2)
        # First item
        self.assertEqual(persisted_items[0]["task"], "Finalize sponsorship proposal")
        self.assertEqual(persisted_items[0]["owner"], "Jordan")
        self.assertEqual(persisted_items[0]["deadline"], "Friday")
        self.assertEqual(persisted_items[0]["status"], "pending")
        self.assertAlmostEqual(persisted_items[0]["confidence"], 1.0)

        # Second item ('Not specified' normalized to None/NULL)
        self.assertEqual(persisted_items[1]["task"], "Order motor parts")
        self.assertIsNone(persisted_items[1]["owner"])
        self.assertIsNone(persisted_items[1]["deadline"])
        self.assertEqual(persisted_items[1]["status"], "pending")
        self.assertAlmostEqual(persisted_items[1]["confidence"], 0.9)

    @patch("app.main.analyze_transcript")
    def test_C_decisions_and_unresolved_issues_persisted(self, mock_analyze):
        """TEST C: Verify decisions and unresolved issues are persisted."""
        mock_analyze.return_value = self.mock_analysis

        response = self.client.post(
            "/analyze-meeting",
            json={"transcript": self.valid_transcript},
        )
        self.assertEqual(response.status_code, 200)

        meetings = self.repo.list_meetings()
        meeting_id = meetings[0]["id"]

        decisions = self.repo.get_decisions(meeting_id)
        self.assertEqual(len(decisions), 1)
        self.assertEqual(decisions[0]["decision"], "Host the hackathon on November 15th")
        self.assertAlmostEqual(decisions[0]["confidence"], 1.0)

        issues = self.repo.get_unresolved_issues(meeting_id)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0]["issue"], "Guest speaker confirmation still pending")

    @patch("app.main.analyze_transcript")
    def test_D_evidence_retained_when_available(self, mock_analyze):
        """TEST D: Verify evidence is retained when available."""
        mock_analyze.return_value = self.mock_analysis

        response = self.client.post(
            "/analyze-meeting",
            json={"transcript": self.valid_transcript},
        )
        self.assertEqual(response.status_code, 200)

        meetings = self.repo.list_meetings()
        meeting_id = meetings[0]["id"]
        items = self.repo.get_action_items(meeting_id)

        self.assertEqual(
            items[0]["evidence"],
            "I will finalize the sponsorship proposal by Friday.",
        )
        self.assertEqual(
            items[1]["evidence"],
            "We need someone to order the motor parts.",
        )

    @patch("app.main.analyze_transcript")
    def test_E_repeated_requests_create_distinct_meetings(self, mock_analyze):
        """TEST E: Verify repeated requests do not accidentally duplicate data or corrupt existing records."""
        mock_analyze.return_value = self.mock_analysis

        # First request
        resp1 = self.client.post("/analyze-meeting", json={"transcript": self.valid_transcript})
        self.assertEqual(resp1.status_code, 200)

        # Second request
        resp2 = self.client.post("/analyze-meeting", json={"transcript": self.valid_transcript})
        self.assertEqual(resp2.status_code, 200)

        meetings = self.repo.list_meetings()
        self.assertEqual(len(meetings), 2)
        self.assertNotEqual(meetings[0]["id"], meetings[1]["id"])

        # Both meetings should have exactly their own 2 action items, 1 decision, 1 issue
        for m in meetings:
            items = self.repo.get_action_items(m["id"])
            decs = self.repo.get_decisions(m["id"])
            issues = self.repo.get_unresolved_issues(m["id"])
            self.assertEqual(len(items), 2)
            self.assertEqual(len(decs), 1)
            self.assertEqual(len(issues), 1)

    @patch("app.main.analyze_transcript")
    def test_F_simulate_database_failure(self, mock_analyze):
        """TEST F: Simulate database failure and verify the API handles it correctly (HTTP 500, no corrupted data)."""
        mock_analyze.return_value = self.mock_analysis

        # Mock repo to raise an error during save_meeting_analysis
        mock_repo = MagicMock(spec=MeetingRepository)
        mock_repo.save_meeting_analysis.side_effect = RuntimeError("Disk full / DB write failed")

        app.state.repository = mock_repo

        response = self.client.post(
            "/analyze-meeting",
            json={"transcript": self.valid_transcript},
        )

        self.assertEqual(response.status_code, 500)
        self.assertIn("Failed to persist meeting analysis", response.json()["detail"])

        # Reset real repo and verify database remains clean / uncorrupted
        app.state.repository = self.repo
        self.assertEqual(len(self.repo.list_meetings()), 0)

    @patch("app.main.analyze_transcript")
    def test_G_evidence_in_api_response_and_null_compatibility(self, mock_analyze):
        """TEST G: Verify POST /analyze-meeting returns evidence in API response and handles null evidence."""
        custom_analysis = MeetingAnalysis(
            summary="Discussion with mixed evidence availability.",
            action_items=[
                AgenticActionItem(
                    task="Book venue",
                    owner="Taylor",
                    deadline="Friday",
                    status="pending",
                    confidence=1.0,
                    evidence="Taylor: I will book the venue by Friday.",
                ),
                AgenticActionItem(
                    task="Send follow up email",
                    owner=None,
                    deadline=None,
                    status="pending",
                    confidence=0.8,
                    evidence=None,
                ),
            ],
            decisions=[],
            unresolved_issues=[],
        )
        mock_analyze.return_value = custom_analysis

        response = self.client.post(
            "/analyze-meeting",
            json={"transcript": self.valid_transcript},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()

        items = data["action_items"]
        self.assertEqual(len(items), 2)
        # First item has evidence
        self.assertEqual(items[0]["task"], "Book venue")
        self.assertEqual(items[0]["evidence"], "Taylor: I will book the venue by Friday.")

        # Second item has null evidence (backward compatible)
        self.assertEqual(items[1]["task"], "Send follow up email")
        self.assertIsNone(items[1]["evidence"])

        # Verify persisted state matches
        meetings = self.repo.list_meetings()
        self.assertEqual(len(meetings), 1)
        persisted_items = self.repo.get_action_items(meetings[0]["id"])
        self.assertEqual(persisted_items[0]["evidence"], "Taylor: I will book the venue by Friday.")
        self.assertIsNone(persisted_items[1]["evidence"])


if __name__ == "__main__":
    unittest.main()
