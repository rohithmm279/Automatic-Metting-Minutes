"""Unit tests for the AI pipeline and orchestrator with mocked LLM."""

import json
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.ai.ollama_client import OllamaClient
from backend.ai.orchestrator import MeetingOrchestrator, MeetingParseError
from backend.ai.validator import MeetingValidator, MeetingValidationError
from backend.models.meeting import ActionItem, Decision, UnresolvedIssue, MeetingOutput


class TestAIPipelineMocked(unittest.TestCase):
    """Test AI orchestrator, parser, and validator behaviors using mocked Ollama responses."""

    def setUp(self):
        self.mock_client = MagicMock(spec=OllamaClient)
        self.orchestrator = MeetingOrchestrator(client=self.mock_client, temperature=0.0)
        self.sample_transcript = (
            "Alex: Welcome everyone. Let's discuss the annual budget.\n"
            "Jordan: I will finalize the sponsorship deck by Friday.\n"
            "Alex: Great, we decided to allocate $500 for catering.\n"
            "Taylor: We still need to figure out the venue permit."
        )

    def test_01_valid_json_response(self):
        """Test 1: Valid JSON response produces a valid MeetingOutput."""
        payload = {
            "summary": "The committee met to discuss the annual budget and event planning.",
            "action_items": [
                {
                    "task": "Finalize the sponsorship deck",
                    "owner": "Jordan",
                    "deadline": "Friday",
                    "status": "pending",
                }
            ],
            "decisions": ["Allocate $500 for catering"],
            "unresolved_issues": ["Venue permit still needed"],
        }
        self.mock_client.generate.return_value = json.dumps(payload)

        result = self.orchestrator.analyze(self.sample_transcript)

        self.assertIsInstance(result, MeetingOutput)
        self.assertEqual(result.summary, payload["summary"])
        self.assertEqual(len(result.action_items), 1)
        self.assertEqual(result.action_items[0].task, "Finalize the sponsorship deck")
        self.assertEqual(result.action_items[0].owner, "Jordan")
        self.assertEqual(result.action_items[0].deadline, "Friday")
        self.assertEqual(len(result.decisions), 1)
        self.assertEqual(result.decisions[0].decision, "Allocate $500 for catering")
        self.assertEqual(len(result.unresolved_issues), 1)
        self.assertEqual(result.unresolved_issues[0].issue, "Venue permit still needed")

    def test_02_json_inside_markdown_fences(self):
        """Test 2: Strips markdown code fences (```json ... ```) correctly."""
        payload = {
            "summary": "Meeting minutes inside code fences.",
            "action_items": [{"task": "Review budget", "owner": "Alex", "deadline": None}],
            "decisions": ["Approved $500"],
            "unresolved_issues": [],
        }
        raw_output = f"```json\n{json.dumps(payload)}\n```"
        self.mock_client.generate.return_value = raw_output

        result = self.orchestrator.analyze(self.sample_transcript)
        self.assertEqual(result.summary, "Meeting minutes inside code fences.")
        self.assertEqual(len(result.action_items), 1)
        self.assertEqual(result.action_items[0].owner, "Alex")

    def test_03_missing_summary(self):
        """Test 3: Missing or empty summary raises MeetingValidationError."""
        payload = {
            "summary": "",
            "action_items": [],
            "decisions": [],
            "unresolved_issues": [],
        }
        self.mock_client.generate.return_value = json.dumps(payload)

        with self.assertRaises(MeetingValidationError) as ctx:
            self.orchestrator.analyze(self.sample_transcript)
        self.assertIn("summary must be a non-empty string", str(ctx.exception).lower())

    def test_04_invalid_action_item_fields(self):
        """Test 4: Empty task or invalid status in action items raises validation error."""
        # Case A: Empty task
        payload_empty_task = {
            "summary": "Valid meeting summary here.",
            "action_items": [{"task": "", "owner": "Alex", "deadline": None}],
            "decisions": [],
            "unresolved_issues": [],
        }
        self.mock_client.generate.return_value = json.dumps(payload_empty_task)
        with self.assertRaises(MeetingValidationError) as ctx:
            self.orchestrator.analyze(self.sample_transcript)
        self.assertIn("empty task", str(ctx.exception).lower())

        # Case B: Invalid status
        payload_invalid_status = {
            "summary": "Valid meeting summary here.",
            "action_items": [{"task": "Valid task", "owner": "Alex", "status": "non_existent_status"}],
            "decisions": [],
            "unresolved_issues": [],
        }
        self.mock_client.generate.return_value = json.dumps(payload_invalid_status)
        with self.assertRaises(MeetingValidationError) as ctx:
            self.orchestrator.analyze(self.sample_transcript)
        self.assertIn("invalid status", str(ctx.exception).lower())

    def test_05_unassigned_action_item(self):
        """Test 5: Unassigned action item (owner=None or missing) is allowed and parsed."""
        payload = {
            "summary": "Meeting with an unassigned community task.",
            "action_items": [{"task": "Set up chairs", "owner": None, "deadline": None}],
            "decisions": [],
            "unresolved_issues": [],
        }
        self.mock_client.generate.return_value = json.dumps(payload)

        result = self.orchestrator.analyze(self.sample_transcript)
        self.assertEqual(len(result.action_items), 1)
        self.assertIsNone(result.action_items[0].owner)
        self.assertIsNone(result.action_items[0].deadline)
        self.assertEqual(result.action_items[0].status, "pending")

    def test_06_invalid_deadline_hallucination(self):
        """Test 6: Deadline not mentioned in transcript triggers grounding validation error."""
        payload = {
            "summary": "Meeting summary.",
            "action_items": [
                {
                    "task": "Finalize deck",
                    "owner": "Jordan",
                    "deadline": "Next Christmas 2030",  # Not in transcript
                }
            ],
            "decisions": [],
            "unresolved_issues": [],
        }
        self.mock_client.generate.return_value = json.dumps(payload)

        with self.assertRaises(MeetingValidationError) as ctx:
            self.orchestrator.analyze(self.sample_transcript)
        self.assertIn("references deadline", str(ctx.exception).lower())

    def test_07_duplicate_action_items(self):
        """Test 7: Handles multiple action items including duplicates without crashing."""
        payload = {
            "summary": "Meeting with duplicate tasks.",
            "action_items": [
                {"task": "Prepare slides", "owner": "Alex", "deadline": None},
                {"task": "Prepare slides", "owner": "Alex", "deadline": None},
            ],
            "decisions": [],
            "unresolved_issues": [],
        }
        self.mock_client.generate.return_value = json.dumps(payload)

        result = self.orchestrator.analyze(self.sample_transcript)
        self.assertEqual(len(result.action_items), 2)
        self.assertEqual(result.action_items[0].task, "Prepare slides")

    def test_08_duplicate_decisions(self):
        """Test 8: Handles duplicate decisions cleanly without crashing."""
        payload = {
            "summary": "Meeting with duplicate decisions.",
            "action_items": [],
            "decisions": ["Approved budget", "Approved budget"],
            "unresolved_issues": [],
        }
        self.mock_client.generate.return_value = json.dumps(payload)

        result = self.orchestrator.analyze(self.sample_transcript)
        self.assertEqual(len(result.decisions), 2)
        self.assertEqual(result.decisions[0].decision, "Approved budget")

    def test_09_malformed_llm_json(self):
        """Test 9: Malformed/non-JSON response raises MeetingParseError."""
        self.mock_client.generate.return_value = "Sorry, as an AI model I cannot assist with this."

        with self.assertRaises(MeetingParseError) as ctx:
            self.orchestrator.analyze(self.sample_transcript)
        self.assertIn("not valid json", str(ctx.exception).lower())

    def test_10_hallucinated_owner_grounding(self):
        """Test 10: Owner not present in transcript triggers MeetingValidationError."""
        payload = {
            "summary": "Meeting with hallucinated owner.",
            "action_items": [
                {"task": "Fix website", "owner": "GhostSpeakerNotInTranscript", "deadline": None}
            ],
            "decisions": [],
            "unresolved_issues": [],
        }
        self.mock_client.generate.return_value = json.dumps(payload)

        with self.assertRaises(MeetingValidationError) as ctx:
            self.orchestrator.analyze(self.sample_transcript)
        self.assertIn("references owner", str(ctx.exception).lower())

    def test_11_preprocessing_integration(self):
        """Test 11: Verifies raw transcript is preprocessed via TranscriptProcessor."""
        # Unclean transcript with extra spaces, tabs, and blank lines
        unclean_transcript = (
            "   Alex:   Welcome   everyone.   \n\n\n"
            "Jordan:    I will finalize the sponsorship deck by Friday.   \n\n"
            "Alex: We decided to allocate $500 for catering.   \n"
        )
        payload = {
            "summary": "Discussion of budget and sponsorship.",
            "action_items": [{"task": "Finalize deck", "owner": "Jordan", "deadline": "Friday"}],
            "decisions": ["Allocate $500 for catering"],
            "unresolved_issues": [],
        }
        self.mock_client.generate.return_value = json.dumps(payload)

        result = self.orchestrator.analyze(unclean_transcript)
        self.assertIsInstance(result, MeetingOutput)
        # Check that generate was called with prompt built from cleaned transcript (no redundant blank lines)
        called_prompt = self.mock_client.generate.call_args[1]["prompt"]
        self.assertNotIn("   Alex:   Welcome", called_prompt)
        self.assertIn("Alex: Welcome everyone.", called_prompt)


if __name__ == "__main__":
    unittest.main()
