"""Unit tests for the GroqClient and its integration with MeetingOrchestrator."""

import json
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch

import requests

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.ai.groq_client import GroqClient
from backend.ai.orchestrator import MeetingOrchestrator
from backend.models.meeting import MeetingOutput


class TestGroqClient(unittest.TestCase):
    """Test GroqClient initialization, API requests, and error handling."""

    def test_missing_api_key_raises_value_error(self):
        """Generating without an API key raises ValueError."""
        client = GroqClient(api_key="")
        with self.assertRaises(ValueError) as ctx:
            client.generate("Test prompt")
        self.assertIn("GROQ_API_KEY is not configured", str(ctx.exception))

    @patch("requests.post")
    def test_successful_generate(self, mock_post):
        """Successful API response extracts content from choices."""
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps({"summary": "A successful meeting."})
                    }
                }
            ]
        }
        mock_post.return_value = mock_response

        client = GroqClient(api_key="gsk_mock_test_key_12345", model="llama-3.3-70b-versatile")
        output = client.generate("Analyze this transcript")

        self.assertIn("A successful meeting.", output)
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args[1]
        self.assertEqual(call_kwargs["headers"]["Authorization"], "Bearer gsk_mock_test_key_12345")
        self.assertEqual(call_kwargs["json"]["model"], "llama-3.3-70b-versatile")
        self.assertEqual(call_kwargs["json"]["response_format"], {"type": "json_object"})

    @patch("requests.post")
    def test_401_unauthorized_raises_permission_error(self, mock_post):
        """HTTP 401 raises PermissionError with clear message."""
        mock_response = MagicMock()
        mock_response.ok = False
        mock_response.status_code = 401
        mock_post.return_value = mock_response

        client = GroqClient(api_key="invalid_key")
        with self.assertRaises(PermissionError) as ctx:
            client.generate("Prompt")
        self.assertIn("Invalid API key", str(ctx.exception))

    @patch("requests.post")
    def test_429_rate_limit_raises_runtime_error(self, mock_post):
        """HTTP 429 raises RuntimeError indicating rate limit."""
        mock_response = MagicMock()
        mock_response.ok = False
        mock_response.status_code = 429
        mock_post.return_value = mock_response

        client = GroqClient(api_key="valid_key")
        with self.assertRaises(RuntimeError) as ctx:
            client.generate("Prompt")
        self.assertIn("rate limit exceeded", str(ctx.exception).lower())

    @patch("requests.post")
    def test_timeout_raises_timeout_error(self, mock_post):
        """Timeout during request raises TimeoutError."""
        mock_post.side_effect = requests.exceptions.Timeout("Connection timed out")

        client = GroqClient(api_key="valid_key", timeout_seconds=5.0)
        with self.assertRaises(TimeoutError):
            client.generate("Prompt")

    @patch("requests.post")
    def test_orchestrator_integration_with_groq(self, mock_post):
        """MeetingOrchestrator produces validated MeetingOutput using GroqClient."""
        payload = {
            "summary": "Team agreed to launch the new feature on Monday.",
            "action_items": [
                {
                    "task": "Deploy production build",
                    "owner": "Sarah",
                    "deadline": "2026-10-15",
                    "status": "pending",
                }
            ],
            "decisions": ["Launch feature on Monday"],
            "unresolved_issues": [],
        }
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": json.dumps(payload)}}]
        }
        mock_post.return_value = mock_response

        client = GroqClient(api_key="gsk_mock_test_key_12345", model="llama-3.3-70b-versatile")
        orchestrator = MeetingOrchestrator(client=client, temperature=0.0)

        sample_transcript = (
            "Alice: Let's discuss our launch timeline.\n"
            "Bob: We confirmed we will launch the feature on Monday.\n"
            "Sarah: I will deploy the production build by October 15th."
        )

        result = orchestrator.analyze(sample_transcript)
        self.assertIsInstance(result, MeetingOutput)
        self.assertEqual(result.pipeline_name, "groq_application")
        self.assertEqual(result.model_name, "llama-3.3-70b-versatile")
        self.assertEqual(len(result.action_items), 1)
        self.assertEqual(result.action_items[0].owner, "Sarah")


if __name__ == "__main__":
    unittest.main()
