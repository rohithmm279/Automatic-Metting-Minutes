"""Deterministic unit tests for Gemini Key Manager and Key Switching System."""

import json
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, call, patch

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.services.gemini_analyzer import GeminiAnalyzer, GeminiAnalysisError
from app.services.gemini_key_manager import GeminiKeyManager, DEFAULT_GEMINI_MODEL


class TestGeminiKeyManager(unittest.TestCase):
    """Test GeminiKeyManager initialization, key selection, mode handling, and leakage prevention."""

    def test_01_explicit_key_loading(self):
        """Test 1: Explicit keys and configuration are loaded properly."""
        km = GeminiKeyManager(
            primary_key="PRIMARY_SECRET_KEY_12345",
            backup_key="BACKUP_SECRET_KEY_67890",
            mode="auto",
            model="gemini-3.5-flash-lite",
        )
        self.assertTrue(km.has_primary)
        self.assertTrue(km.has_backup)
        self.assertTrue(km.is_configured)
        self.assertEqual(km.mode, "auto")
        self.assertEqual(km.model, "gemini-3.5-flash-lite")

    def test_02_primary_mode_selection(self):
        """Test 2: Mode 'primary' yields only the primary key candidate."""
        km = GeminiKeyManager(
            primary_key="PRIMARY_SECRET_KEY_12345",
            backup_key="BACKUP_SECRET_KEY_67890",
            mode="primary",
        )
        self.assertEqual(km.mode, "primary")
        candidates = km.get_key_candidates()
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0][0], "primary")
        self.assertEqual(candidates[0][1], "PRIMARY_SECRET_KEY_12345")

    def test_03_backup_mode_selection(self):
        """Test 3: Mode 'backup' yields only the backup key candidate."""
        km = GeminiKeyManager(
            primary_key="PRIMARY_SECRET_KEY_12345",
            backup_key="BACKUP_SECRET_KEY_67890",
            mode="backup",
        )
        self.assertEqual(km.mode, "backup")
        candidates = km.get_key_candidates()
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0][0], "backup")
        self.assertEqual(candidates[0][1], "BACKUP_SECRET_KEY_67890")

    def test_04_auto_mode_selection_ordering(self):
        """Test 4: Mode 'auto' orders primary first, then backup."""
        km = GeminiKeyManager(
            primary_key="PRIMARY_SECRET_KEY_12345",
            backup_key="BACKUP_SECRET_KEY_67890",
            mode="auto",
        )
        self.assertEqual(km.mode, "auto")
        candidates = km.get_key_candidates()
        self.assertEqual(len(candidates), 2)
        self.assertEqual(candidates[0][0], "primary")
        self.assertEqual(candidates[0][1], "PRIMARY_SECRET_KEY_12345")
        self.assertEqual(candidates[1][0], "backup")
        self.assertEqual(candidates[1][1], "BACKUP_SECRET_KEY_67890")

    def test_05_mode_normalization_and_invalid_fallback(self):
        """Test 5: Mode is case-insensitive, and invalid mode defaults to 'auto'."""
        km_upper = GeminiKeyManager(
            primary_key="KEY_1",
            backup_key="KEY_2",
            mode="PRIMARY",
        )
        self.assertEqual(km_upper.mode, "primary")

        km_invalid = GeminiKeyManager(
            primary_key="KEY_1",
            backup_key="KEY_2",
            mode="UNKNOWN_INVALID_MODE",
        )
        self.assertEqual(km_invalid.mode, "auto")

    def test_06_model_configuration_and_default(self):
        """Test 6: Model defaults to gemini-3.5-flash-lite and respects custom config."""
        km_default = GeminiKeyManager(primary_key="KEY_1")
        self.assertEqual(km_default.model, "gemini-3.5-flash-lite")

        km_custom = GeminiKeyManager(primary_key="KEY_1", model="custom-model-pro")
        self.assertEqual(km_custom.model, "custom-model-pro")

    def test_07_prevention_of_key_leakage(self):
        """Test 7: repr, str, and status summary never expose the raw API key."""
        raw_primary = "AIzaSyD_SECRET_PRIMARY_KEY_99999"
        raw_backup = "AIzaSyD_SECRET_BACKUP_KEY_88888"
        km = GeminiKeyManager(primary_key=raw_primary, backup_key=raw_backup, mode="auto")

        rep = repr(km)
        str_rep = str(km)
        status = km.get_status_summary()

        self.assertNotIn(raw_primary, rep)
        self.assertNotIn(raw_backup, rep)
        self.assertNotIn(raw_primary, str_rep)
        self.assertNotIn(raw_backup, str_rep)
        self.assertNotIn(raw_primary, status["primary_masked"])
        self.assertNotIn(raw_backup, status["backup_masked"])
        self.assertTrue(status["primary_configured"])
        self.assertTrue(status["backup_configured"])

    def test_08_unconfigured_state(self):
        """Test 8: Unconfigured key manager reports is_configured=False and empty candidates."""
        km = GeminiKeyManager(primary_key=None, backup_key=None, mode="auto", env_path=Path("/non/existent/.env"))
        # Force None keys regardless of local .env
        km._primary_key = None
        km._backup_key = None
        self.assertFalse(km.is_configured)
        self.assertEqual(km.get_key_candidates(), [])

    def test_09_gemini_api_key_legacy_fallback(self):
        """Test 9: Falls back to GEMINI_API_KEY when GEMINI_API_KEY_PRIMARY is absent."""
        with patch.dict("os.environ", {"GEMINI_API_KEY": "LEGACY_KEY_VAL", "GEMINI_API_KEY_PRIMARY": ""}, clear=False):
            km = GeminiKeyManager(env_path=Path("/non/existent/.env"))
            # If primary was not given, it resolves from GEMINI_API_KEY
            self.assertEqual(km._primary_key, "LEGACY_KEY_VAL")


class TestGeminiAnalyzerKeySwitching(unittest.TestCase):
    """Test GeminiAnalyzer failover, backoff, and model propagation with mocked GenAI Client."""

    def setUp(self):
        self.primary_key = "AIzaSyD_PRIMARY_KEY_001"
        self.backup_key = "AIzaSyD_BACKUP_KEY_002"
        self.km = GeminiKeyManager(
            primary_key=self.primary_key,
            backup_key=self.backup_key,
            mode="auto",
            model="gemini-3.5-flash-lite",
        )

    def test_01_analyzer_model_name_and_configuration(self):
        """Test 1: Analyzer reflects key manager model name and configuration status."""
        analyzer = GeminiAnalyzer(key_manager=self.km)
        self.assertTrue(analyzer.is_configured)
        self.assertEqual(analyzer.model_name, "gemini-3.5-flash-lite")

    def test_02_successful_request_uses_primary_key_only(self):
        """Test 2: When primary key succeeds, backup key is never invoked."""
        analyzer = GeminiAnalyzer(key_manager=self.km)

        mock_response = MagicMock()
        mock_response.text = '{"summary": "All good", "action_items": [], "decisions": [], "unresolved_issues": []}'

        created_clients = []

        def fake_genai_client(api_key):
            client = MagicMock()
            client._api_key = api_key
            client.models.generate_content.return_value = mock_response
            created_clients.append(client)
            return client

        with patch("app.services.gemini_analyzer.time.sleep"), \
             patch("google.genai.Client", side_effect=fake_genai_client):
            result = analyzer.generate_json("Test prompt")

        self.assertEqual(result["summary"], "All good")
        self.assertEqual(len(created_clients), 1)
        self.assertEqual(created_clients[0]._api_key, self.primary_key)

    def test_03_429_failover_to_backup_key_same_request(self):
        """Test 3: In auto mode, 429 on primary triggers immediate failover to backup key for same request."""
        analyzer = GeminiAnalyzer(key_manager=self.km)

        mock_success_response = MagicMock()
        mock_success_response.text = '{"summary": "From backup key", "action_items": [], "decisions": [], "unresolved_issues": []}'

        client_calls = []

        def fake_genai_client(api_key):
            client = MagicMock()
            client._api_key = api_key

            def generate_content(model, contents, config):
                client_calls.append(api_key)
                if api_key == self.primary_key:
                    raise Exception("429 RESOURCE_EXHAUSTED: Quota exceeded for project")
                return mock_success_response

            client.models.generate_content.side_effect = generate_content
            return client

        with patch("app.services.gemini_analyzer.time.sleep"), \
             patch("google.genai.Client", side_effect=fake_genai_client):
            result = analyzer.generate_json("Test prompt")

        self.assertEqual(result["summary"], "From backup key")
        # Check that primary was attempted first, then backup was called
        self.assertEqual(client_calls, [self.primary_key, self.backup_key])

    def test_04_no_persistent_switch_after_failover(self):
        """Test 4: Subsequent request still tries primary key first even if previous failed over."""
        analyzer = GeminiAnalyzer(key_manager=self.km)

        mock_backup_resp = MagicMock()
        mock_backup_resp.text = '{"summary": "Call 1 backup", "action_items": [], "decisions": [], "unresolved_issues": []}'

        mock_primary_resp2 = MagicMock()
        mock_primary_resp2.text = '{"summary": "Call 2 primary", "action_items": [], "decisions": [], "unresolved_issues": []}'

        call_count = {"primary": 0, "backup": 0}

        def fake_genai_client(api_key):
            client = MagicMock()
            client._api_key = api_key

            def generate_content(model, contents, config):
                if api_key == self.primary_key:
                    call_count["primary"] += 1
                    if call_count["primary"] == 1:
                        raise Exception("429 RESOURCE_EXHAUSTED: Quota limit")
                    return mock_primary_resp2
                else:
                    call_count["backup"] += 1
                    return mock_backup_resp

            client.models.generate_content.side_effect = generate_content
            return client

        with patch("app.services.gemini_analyzer.time.sleep"), \
             patch("google.genai.Client", side_effect=fake_genai_client):
            res1 = analyzer.generate_json("Prompt 1")
            res2 = analyzer.generate_json("Prompt 2")

        self.assertEqual(res1["summary"], "Call 1 backup")
        self.assertEqual(res2["summary"], "Call 2 primary")
        # Primary was called twice (once failed, once succeeded), backup called once
        self.assertEqual(call_count["primary"], 2)
        self.assertEqual(call_count["backup"], 1)

    def test_05_primary_mode_does_not_failover_on_429(self):
        """Test 5: In primary mode, 429 retries on primary only and does not switch to backup."""
        km_primary_only = GeminiKeyManager(
            primary_key=self.primary_key,
            backup_key=self.backup_key,
            mode="primary",
        )
        analyzer = GeminiAnalyzer(key_manager=km_primary_only)

        client_calls = []

        def fake_genai_client(api_key):
            client = MagicMock()
            client._api_key = api_key

            def generate_content(model, contents, config):
                client_calls.append(api_key)
                raise Exception("429 RESOURCE_EXHAUSTED: Quota limit")

            client.models.generate_content.side_effect = generate_content
            return client

        with patch("app.services.gemini_analyzer.time.sleep"), \
             patch("google.genai.Client", side_effect=fake_genai_client):
            with self.assertRaises(GeminiAnalysisError) as ctx:
                analyzer.generate_json("Test prompt", max_retries=3)

        self.assertTrue(ctx.exception.is_rate_limit)
        # All 3 attempts used primary key, backup was never used
        self.assertEqual(client_calls, [self.primary_key, self.primary_key, self.primary_key])

    def test_06_503_transient_retry_preservation(self):
        """Test 6: Transient 503 UNAVAILABLE errors trigger exponential backoff retry on same key."""
        analyzer = GeminiAnalyzer(key_manager=self.km)

        mock_success_response = MagicMock()
        mock_success_response.text = '{"summary": "Recovered from 503", "action_items": [], "decisions": [], "unresolved_issues": []}'

        attempts = []

        def fake_genai_client(api_key):
            client = MagicMock()
            client._api_key = api_key

            def generate_content(model, contents, config):
                attempts.append(api_key)
                if len(attempts) < 3:
                    raise Exception("503 Service Unavailable")
                return mock_success_response

            client.models.generate_content.side_effect = generate_content
            return client

        with patch("app.services.gemini_analyzer.time.sleep") as mock_sleep, \
             patch("google.genai.Client", side_effect=fake_genai_client):
            result = analyzer.generate_json("Test prompt", max_retries=4)

        self.assertEqual(result["summary"], "Recovered from 503")
        # Succeeded on 3rd attempt using primary key
        self.assertEqual(attempts, [self.primary_key, self.primary_key, self.primary_key])
        self.assertTrue(mock_sleep.called)

    def test_07_both_keys_exhausted_raises_redacted_error(self):
        """Test 7: When both primary and backup keys encounter 429, error is raised with is_rate_limit=True."""
        analyzer = GeminiAnalyzer(key_manager=self.km)

        def fake_genai_client(api_key):
            client = MagicMock()

            def generate_content(model, contents, config):
                raise Exception(f"429 RESOURCE_EXHAUSTED with key={api_key}")

            client.models.generate_content.side_effect = generate_content
            return client

        with patch("app.services.gemini_analyzer.time.sleep"), \
             patch("google.genai.Client", side_effect=fake_genai_client):
            with self.assertRaises(GeminiAnalysisError) as ctx:
                analyzer.generate_json("Test prompt", max_retries=2)

        self.assertTrue(ctx.exception.is_rate_limit)
        # Ensure raw key was redacted from safe message
        self.assertNotIn(self.primary_key, ctx.exception.safe_message)
        self.assertNotIn(self.backup_key, ctx.exception.safe_message)

    def test_08_redact_message_masks_all_key_patterns(self):
        """Test 8: GeminiAnalysisError.redact_message sanitizes secret tokens."""
        raw_msg = (
            "Error calling API: https://generativelanguage.googleapis.com/v1beta/models?key=AIzaSyD_SECRET_KEY_123 "
            "Authorization: Bearer my_secret_token_abc123 "
            "api_key: AIzaSyD_ANOTHER_SECRET"
        )
        safe = GeminiAnalysisError.redact_message(raw_msg)
        self.assertNotIn("AIzaSyD_SECRET_KEY_123", safe)
        self.assertNotIn("my_secret_token_abc123", safe)
        self.assertNotIn("AIzaSyD_ANOTHER_SECRET", safe)
        self.assertIn("[REDACTED]", safe)


if __name__ == "__main__":
    unittest.main()
