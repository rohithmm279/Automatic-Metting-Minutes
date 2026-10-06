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
from backend.ai.evidence_repair import repair_output
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

    def test_01g_evidence_repair_adds_missing_explicit_commitment(self):
        output = MeetingOutput(
            summary="The team discussed the project.",
            action_items=[],
            decisions=[],
            unresolved_issues=[],
        )
        repaired = repair_output(
            output,
            "Karthik: I will arrange laptops for the coding session by Thursday.\n"
            "Kavya: The printing order is still not confirmed.",
        )

        self.assertEqual(repaired.action_items[0].task, "Arrange laptops for the coding session")
        self.assertEqual(repaired.action_items[0].owner, "Karthik")
        self.assertEqual(len(repaired.unresolved_issues), 1)

    def test_01e_unrelated_input_is_rejected_before_model_call(self):
        """Plain unrelated content must not be sent to the extraction model."""
        with self.assertRaisesRegex(ValueError, "does not look like a meeting transcript"):
            self.orchestrator.analyze("The latest football score was 4 to 1.")

        self.mock_client.generate.assert_not_called()

    def test_01c_two_pass_tags_intent_before_extraction(self):
        """Two-pass mode sends intent evidence to the structural extraction pass."""
        tags = {
            "meeting_archetype": "corporate_sync",
            "utterance_tags": [
                {
                    "speaker": "Jordan",
                    "text": "I will finalize the sponsorship deck by Friday.",
                    "intent": "assigned_task",
                },
                {
                    "speaker": "Alex",
                    "text": "We decided to allocate $500 for catering.",
                    "intent": "final_decision",
                },
            ],
        }
        payload = {
            "summary": "The committee reviewed the annual budget and event planning.",
            "action_items": [{"task": "Finalize the sponsorship deck", "owner": "Jordan", "deadline": "Friday"}],
            "decisions": ["Allocate $500 for catering"],
            "unresolved_issues": [],
        }
        self.mock_client.generate.side_effect = [json.dumps(tags), json.dumps(payload)]
        orchestrator = MeetingOrchestrator(client=self.mock_client, temperature=0.0, two_pass=True)

        result = orchestrator.analyze(self.sample_transcript)

        self.assertEqual(result.pipeline_name, "qwen_application")
        self.assertEqual(result.prompt_version, "backend.ai.prompts.v3-two-pass")
        self.assertEqual(self.mock_client.generate.call_count, 2)
        self.assertIn("assigned_task", self.mock_client.generate.call_args_list[1].kwargs["prompt"])
        self.assertIn("corporate_sync", self.mock_client.generate.call_args_list[1].kwargs["prompt"])

    def test_01d_two_pass_falls_back_to_one_pass_on_bad_tags(self):
        """Malformed pass-one output does not prevent normal extraction."""
        payload = {
            "summary": "The committee reviewed the annual budget.",
            "action_items": [],
            "decisions": [],
            "unresolved_issues": [],
        }
        self.mock_client.generate.side_effect = ["not json", json.dumps(payload)]
        orchestrator = MeetingOrchestrator(client=self.mock_client, temperature=0.0, two_pass=True)

        result = orchestrator.analyze(self.sample_transcript)

        self.assertEqual(result.summary, payload["summary"])
        self.assertEqual(self.mock_client.generate.call_count, 2)
        self.assertNotIn("PASS 1 INTENT GUIDANCE", self.mock_client.generate.call_args_list[1].kwargs["prompt"])

    @patch("backend.ai.ollama_client.requests.post")
    def test_01b_ollama_limits_are_configurable(self, mock_post):
        """Ollama requests expose configurable timeout and output limits."""
        response = MagicMock()
        response.json.return_value = {"response": "{}"}
        mock_post.return_value = response

        client = OllamaClient(timeout_seconds=45, max_output_tokens=512)
        client.generate("test prompt")

        request = mock_post.call_args
        self.assertEqual(request.kwargs["timeout"], (10, 45))
        self.assertEqual(request.kwargs["json"]["options"]["num_predict"], 512)
        self.assertEqual(request.kwargs["json"]["keep_alive"], "10m")

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

    def test_04b_known_status_alias_is_normalized(self):
        """Common model status aliases are converted to the public status enum."""
        payload = {
            "summary": "The team reviewed the annual budget.",
            "action_items": [{"task": "Finalize the sponsorship deck", "owner": "Jordan", "status": "settled"}],
            "decisions": [],
            "unresolved_issues": [],
        }
        self.mock_client.generate.return_value = json.dumps(payload)

        result = self.orchestrator.analyze(self.sample_transcript)

        self.assertEqual(result.action_items[0].status, "completed")

    def test_04c_confirmed_action_status_is_pending(self):
        """Model status 'confirmed' means accepted assignment, not completed work."""
        payload = {
            "summary": "The team confirmed the prototype test assignment.",
            "action_items": [{
                "task": "Test the prototype",
                "owner": "Jordan",
                "status": "confirmed",
            }],
            "decisions": [],
            "unresolved_issues": [],
        }
        self.mock_client.generate.return_value = json.dumps(payload)

        result = self.orchestrator.analyze(self.sample_transcript)

        self.assertEqual(result.action_items[0].status, "pending")

    def test_04d_resolved_action_status_is_completed(self):
        """Model status 'resolved' maps to the public completed state."""
        payload = {
            "summary": "The assigned issue was resolved.",
            "action_items": [{
                "task": "Fix the issue",
                "owner": "Jordan",
                "status": "resolved",
            }],
            "decisions": [],
            "unresolved_issues": [],
        }
        self.mock_client.generate.return_value = json.dumps(payload)

        result = self.orchestrator.analyze(self.sample_transcript)

        self.assertEqual(result.action_items[0].status, "completed")

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

    def test_06b_iso_date_deadline_grounding(self):
        """Test 6b: ISO formatted date (e.g. 2026-09-23) grounds against transcript containing month/day."""
        transcript_with_date = (
            "Alex: Welcome everyone.\n"
            "Jordan: I will finalize the sponsorship deck by September 23rd.\n"
            "Alex: Sounds good."
        )
        payload = {
            "summary": "Meeting discussion on sponsorship.",
            "action_items": [
                {
                    "task": "Finalize the sponsorship deck",
                    "owner": "Jordan",
                    "deadline": "2026-09-23",
                    "status": "pending",
                }
            ],
            "decisions": [],
            "unresolved_issues": [],
        }
        self.mock_client.generate.return_value = json.dumps(payload)
        result = self.orchestrator.analyze(transcript_with_date)
        self.assertEqual(result.action_items[0].deadline, "2026-09-23")

    def test_06b1_iso_date_is_not_grounded_by_generic_deadline_words(self):
        """Generic temporal words must not support an invented ISO deadline."""
        transcript_without_date = (
            "Jordan: I will send the draft before the deadline.\n"
            "Alex: We still need to confirm the external reviewer."
        )
        output = MeetingOutput(
            summary="The team discussed the report.",
            action_items=[
                ActionItem(
                    task="Send the draft",
                    owner="Jordan",
                    deadline="2026-11-01",
                    status="pending",
                )
            ],
            decisions=[],
            unresolved_issues=[],
        )

        with self.assertRaises(MeetingValidationError):
            self.orchestrator.validator.validate(output, transcript_without_date)

    def test_06c_relative_resolved_iso_deadline_grounding(self):
        """Test 6c: ISO date (e.g. 2026-09-14) resolved from relative words (e.g. next Monday) is validated successfully."""
        transcript_relative = (
            "Alex: Welcome to the team sync.\n"
            "Jordan: I will deploy the hotfix by next Monday.\n"
            "Alex: Sounds good."
        )
        payload = {
            "summary": "Meeting discussion on hotfix deployment.",
            "action_items": [
                {
                    "task": "Deploy the hotfix",
                    "owner": "Jordan",
                    "deadline": "2026-09-14",
                    "status": "pending",
                }
            ],
            "decisions": [],
            "unresolved_issues": [],
        }
        self.mock_client.generate.return_value = json.dumps(payload)
        result = self.orchestrator.analyze(transcript_relative)
        self.assertEqual(result.action_items[0].deadline, "2026-09-14")

    def test_06d_header_relative_iso_deadline_grounding(self):
        """Header-relative dates are grounded after normalization to ISO format."""
        transcript_relative = (
            "Date: 22 September 2026\n"
            "Rohith: Tomorrow we'll do a complete test together."
        )
        payload = {
            "summary": "The team scheduled a complete test for tomorrow.",
            "action_items": [
                {
                    "task": "Complete the test",
                    "owner": "Rohith",
                    "deadline": "2026-09-23",
                    "status": "pending",
                }
            ],
            "decisions": [],
            "unresolved_issues": [],
        }
        self.mock_client.generate.return_value = json.dumps(payload)

        result = self.orchestrator.analyze(transcript_relative)

        self.assertEqual(result.action_items[0].deadline, "2026-09-23")

    def test_06e_month_first_header_relative_iso_deadline_grounding(self):
        """Month-first headers must ground normalized relative deadlines."""
        transcript = (
            "Date: October 1, 2026\n"
            "Rohith: Tomorrow we'll complete the test together.\n"
            "Alex: I will review the results after that."
        )
        payload = {
            "summary": "The team scheduled a complete test for tomorrow.",
            "action_items": [{
                "task": "Complete the test",
                "owner": "Rohith",
                "deadline": "2026-10-02",
                "status": "pending",
            }],
            "decisions": [],
            "unresolved_issues": [],
        }
        self.mock_client.generate.return_value = json.dumps(payload)

        result = self.orchestrator.analyze(transcript)
        self.assertEqual(result.action_items[0].deadline, "2026-10-02")

    def test_06g_relative_iso_deadline_without_meeting_header_is_grounded(self):
        """Relative timing can ground a normalized ISO date without a date header."""
        transcript = (
            "Karthik: I will arrange laptops for the coding session by Thursday evening.\n"
            "Kavya: I will fix the club website bug by end of this week."
        )
        output = MeetingOutput(
            summary="The team assigned laptop and website work.",
            action_items=[
                ActionItem(task="Arrange laptops for the coding session", owner="Karthik", deadline="2026-10-02", status="pending"),
            ],
            decisions=[],
            unresolved_issues=[],
        )

        self.assertIs(self.orchestrator.validator.validate(output, transcript), output)

    def test_06e_header_relative_iso_hallucinated_deadline_rejected(self):
        """An ISO date not resolved by the meeting header or transcript is rejected."""
        transcript_relative = (
            "Date: 22 September 2026\n"
            "Rohith: Tomorrow we'll do a complete test together."
        )
        output = MeetingOutput(
            summary="The team scheduled a complete test for tomorrow.",
            action_items=[
                ActionItem(
                    task="Complete the test",
                    owner="Rohith",
                    deadline="2026-09-24",
                    status="pending",
                )
            ],
            decisions=[],
            unresolved_issues=[],
        )

        with self.assertRaises(MeetingValidationError) as ctx:
            self.orchestrator.validator.validate(output, transcript_relative)

        self.assertIn("references deadline", str(ctx.exception).lower())

    def test_06f_datetime_deadline_recovers_from_transcript_turn(self):
        """A model datetime with the wrong date is corrected from the matched relative commitment."""
        transcript_relative = (
            "Date: 22 September 2026\n"
            "Rohith: Tomorrow we'll do a complete test together.\n"
            "Arun: I'll create the GitHub repo."
        )
        payload = {
            "summary": "The team scheduled a complete test for tomorrow.",
            "action_items": [
                {
                    "task": "Complete the test",
                    "owner": "Rohith",
                    "deadline": "2026-09-24T19:00:00",
                    "status": "pending",
                }
            ],
            "decisions": [],
            "unresolved_issues": [],
        }
        self.mock_client.generate.return_value = json.dumps(payload)

        result = self.orchestrator.analyze(transcript_relative)

        self.assertEqual(result.action_items[0].deadline, "2026-09-23")

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

    def test_09b_wrapped_llm_json_is_recovered(self):
        """Test 9b: Common model wrappers do not prevent structured parsing."""
        payload = {
            "summary": "The club planned its showcase materials and staffing.",
            "action_items": [],
            "decisions": [],
            "unresolved_issues": [],
        }
        self.mock_client.generate.return_value = (
            "Here is the requested JSON:\n```json\n"
            + json.dumps(payload)
            + "\n```"
        )

        result = self.orchestrator.analyze(self.sample_transcript)

        self.assertEqual(result.summary, payload["summary"])

    def test_10_hallucinated_owner_grounding(self):
        """Test 10: Unsupported owners are safely cleared, not allowed to poison output."""
        payload = {
            "summary": "Meeting with hallucinated owner.",
            "action_items": [
                {"task": "Fix website", "owner": "GhostSpeakerNotInTranscript", "deadline": None}
            ],
            "decisions": [],
            "unresolved_issues": [],
        }
        self.mock_client.generate.return_value = json.dumps(payload)

        result = self.orchestrator.analyze(self.sample_transcript)
        self.assertIsNone(result.action_items[0].owner)

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

    def test_12_unsupported_prompt_examples_are_removed(self):
        """Prompt examples must not become unsupported decisions or issues."""
        payload = {
            "summary": "The team reviewed the event plan.",
            "action_items": [],
            "decisions": ["Finalize the event date"],
            "unresolved_issues": ["Guest's travel plans", "Budget approval"],
        }
        self.mock_client.generate.return_value = json.dumps(payload)

        result = self.orchestrator.analyze(self.sample_transcript)

        self.assertEqual(result.decisions, [])
        self.assertEqual(result.unresolved_issues, [])

    def test_13_prompt_example_is_kept_when_transcript_supports_it(self):
        """A prompt example remains valid when it is actually discussed."""
        transcript = self.sample_transcript + "\nTaylor: Guest's travel plans remain unresolved."
        payload = {
            "summary": "The team reviewed the event plan.",
            "action_items": [],
            "decisions": [],
            "unresolved_issues": ["Guest's travel plans"],
        }
        self.mock_client.generate.return_value = json.dumps(payload)

        result = self.orchestrator.analyze(transcript)

        self.assertEqual(len(result.unresolved_issues), 1)
        self.assertEqual(result.unresolved_issues[0].issue, "Guest's travel plans")



if __name__ == "__main__":
    unittest.main()
