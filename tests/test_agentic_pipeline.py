"""Deterministic unit tests for Agentic AI Pipeline (Summary, Action, Decision, Validation, Orchestrator, Fallback)."""

import json
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.agents.summary_agent import SummaryAgent
from app.agents.action_agent import ActionAgent
from app.agents.decision_agent import DecisionAgent
from app.agents.validation_agent import ValidationAgent
from app.agents.orchestrator import AgentOrchestrator
from app.schemas.meeting_schema import ActionItem, DecisionItem, MeetingAnalysis
from app.services.gemini_analyzer import GeminiAnalyzer, GeminiAnalysisError
from app.services.meeting_analyzer import MeetingAnalyzer


class TestAgenticPipeline(unittest.TestCase):
    """Test individual agents, validation logic, failure fallback, and complete orchestrator."""

    def setUp(self):
        self.sample_transcript = (
            "Alex: Welcome everyone to the Robotics Club planning meeting.\n"
            "Jordan: I will finalize the sponsorship proposal by Friday.\n"
            "Taylor: We also need someone to order the motor parts, but no one is assigned yet.\n"
            "Alex: Great. We all agreed to host the hackathon on November 15th.\n"
            "Sam: What about the guest speaker? That's still pending confirmation."
        )

    # -----------------------------------------------------------------------
    # 1. Summary Agent Tests
    # -----------------------------------------------------------------------
    def test_01_summary_agent_extraction(self):
        """Test 1: Summary Agent produces a concise 3-5 sentence summary from mocked Gemini."""
        mock_analyzer = MagicMock(spec=GeminiAnalyzer)
        mock_analyzer.is_configured = True
        mock_analyzer.model_name = "gemini-3.6-flash"
        mock_analyzer.generate_json.return_value = {
            "summary": "The Robotics Club met to organize the upcoming hackathon. Jordan committed to finalizing the sponsorship proposal by Friday. The committee decided to host the event on November 15th while speaker confirmation remains pending."
        }

        agent = SummaryAgent(gemini_analyzer=mock_analyzer)
        summary = agent.generate_summary(self.sample_transcript)

        self.assertIn("Robotics Club", summary)
        self.assertIn("November 15th", summary)

    # -----------------------------------------------------------------------
    # 2. Action Agent Tests
    # -----------------------------------------------------------------------
    def test_02_action_agent_extraction(self):
        """Test 2: Action Agent extracts assigned tasks, explicit owner, deadline, and unassigned tasks."""
        mock_analyzer = MagicMock(spec=GeminiAnalyzer)
        mock_analyzer.is_configured = True
        mock_analyzer.model_name = "gemini-3.6-flash"
        mock_analyzer.generate_json.return_value = {
            "action_items": [
                {
                    "task": "Finalize the sponsorship proposal",
                    "owner": "Jordan",
                    "deadline": "Friday",
                    "status": "pending",
                    "confidence": 1.0,
                    "evidence": "I will finalize the sponsorship proposal by Friday."
                },
                {
                    "task": "Order the motor parts",
                    "owner": None,
                    "deadline": None,
                    "status": "pending",
                    "confidence": 0.9,
                    "evidence": "We also need someone to order the motor parts"
                }
            ]
        }

        agent = ActionAgent(gemini_analyzer=mock_analyzer)
        items = agent.extract_action_items(self.sample_transcript)

        self.assertEqual(len(items), 2)
        self.assertEqual(items[0].task, "Finalize the sponsorship proposal")
        self.assertEqual(items[0].owner, "Jordan")
        self.assertEqual(items[0].deadline, "Friday")
        # Missing owner and deadline should default to "Not specified"
        self.assertEqual(items[1].owner, "Not specified")
        self.assertEqual(items[1].deadline, "Not specified")

    # -----------------------------------------------------------------------
    # 3. Decision Agent Tests
    # -----------------------------------------------------------------------
    def test_03_decision_agent_extraction(self):
        """Test 3: Decision Agent extracts confirmed decisions and distinguishes unresolved issues."""
        mock_analyzer = MagicMock(spec=GeminiAnalyzer)
        mock_analyzer.is_configured = True
        mock_analyzer.model_name = "gemini-3.6-flash"
        mock_analyzer.generate_json.return_value = {
            "decisions": [
                {
                    "decision": "Host the hackathon on November 15th",
                    "confidence": 1.0,
                    "evidence": "We all agreed to host the hackathon on November 15th."
                }
            ],
            "unresolved_issues": [
                "Guest speaker confirmation"
            ]
        }

        agent = DecisionAgent(gemini_analyzer=mock_analyzer)
        flat_decs, detailed_decs, issues = agent.extract_decisions(self.sample_transcript)

        self.assertEqual(len(flat_decs), 1)
        self.assertIn("Host the hackathon on November 15th", flat_decs[0])
        self.assertEqual(len(detailed_decs), 1)
        self.assertEqual(detailed_decs[0].evidence, "We all agreed to host the hackathon on November 15th.")
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0], "Guest speaker confirmation")

    # -----------------------------------------------------------------------
    # 4. Validation Agent Tests
    # -----------------------------------------------------------------------
    def test_04_validation_agent_valid_inputs(self):
        """Test 4: Validation Agent passes grounded outputs."""
        validator = ValidationAgent()
        summary = "The Robotics Club met to organize the hackathon on November 15th."
        actions = [
            ActionItem(task="Finalize the sponsorship proposal", owner="Jordan", deadline="Friday", status="pending")
        ]
        decisions = ["Host the hackathon on November 15th"]

        v_sum, v_acts, v_decs, v_det_decs, overall = validator.validate_all(
            transcript=self.sample_transcript,
            summary=summary,
            action_items=actions,
            decisions=decisions,
        )

        self.assertTrue(overall.all_grounded)
        self.assertTrue(overall.summary_grounded)
        self.assertTrue(overall.action_items_valid)
        self.assertTrue(overall.decisions_valid)
        self.assertTrue(v_acts[0].validation.is_valid)

    def test_05_validation_agent_detects_hallucinated_owner(self):
        """Test 5: Validation Agent flags an owner that does not exist in the transcript."""
        validator = ValidationAgent()
        actions = [
            ActionItem(task="Finalize proposal", owner="Elon Musk", deadline="Friday", status="pending")
        ]
        _, v_acts, _, _, overall = validator.validate_all(
            transcript=self.sample_transcript,
            summary="Robotics meeting summary.",
            action_items=actions,
            decisions=["Host the hackathon on November 15th"],
        )

        self.assertFalse(v_acts[0].validation.grounded)
        self.assertIn("Elon Musk", v_acts[0].validation.notes)
        self.assertFalse(overall.action_items_valid)

    def test_06_validation_agent_detects_hallucinated_deadline(self):
        """Test 6: Validation Agent flags a deadline not mentioned in the transcript."""
        validator = ValidationAgent()
        actions = [
            ActionItem(task="Finalize sponsorship proposal", owner="Jordan", deadline="next year in December", status="pending")
        ]
        _, v_acts, _, _, overall = validator.validate_all(
            transcript=self.sample_transcript,
            summary="Robotics meeting summary.",
            action_items=actions,
            decisions=["Host the hackathon on November 15th"],
        )

        self.assertFalse(v_acts[0].validation.grounded)
        self.assertIn("Deadline", v_acts[0].validation.notes)

    def test_07_validation_agent_detects_unsupported_decision(self):
        """Test 7: Validation Agent flags speculative proposals treated as decisions."""
        validator = ValidationAgent()
        decisions = ["We might thinking about buying a submarine"]

        _, _, _, _, overall = validator.validate_all(
            transcript=self.sample_transcript,
            summary="Robotics meeting summary.",
            action_items=[],
            decisions=decisions,
        )

        self.assertFalse(overall.decisions_valid)

    def test_08_missing_owner_and_deadline_normalization(self):
        """Test 8: Missing owner and missing deadline are normalized to 'Not specified' without error."""
        validator = ValidationAgent()
        actions = [
            ActionItem(task="Order motor parts", owner="Not specified", deadline="Not specified", status="pending")
        ]
        _, v_acts, _, _, overall = validator.validate_all(
            transcript=self.sample_transcript,
            summary="Robotics meeting summary.",
            action_items=actions,
            decisions=["Host hackathon on November 15th"],
        )

        self.assertTrue(v_acts[0].validation.is_valid)
        self.assertEqual(v_acts[0].owner, "Not specified")
        self.assertEqual(v_acts[0].deadline, "Not specified")

    # -----------------------------------------------------------------------
    # 5. Gemini Failure & Fallback Tests
    # -----------------------------------------------------------------------
    def test_09_gemini_failure_triggers_fallback(self):
        """Test 9: When Gemini fails, the orchestrator seamlessly falls back to rule-based MeetingAnalyzer."""
        mock_summary_agent = MagicMock()
        mock_summary_agent.generate_summary.side_effect = GeminiAnalysisError("API connection timeout")

        mock_analyzer = MagicMock(spec=GeminiAnalyzer)
        mock_analyzer.is_configured = True
        mock_analyzer.model_name = "gemini-3.6-flash"

        orchestrator = AgentOrchestrator(
            gemini_analyzer=mock_analyzer,
            summary_agent=mock_summary_agent,
        )

        analysis, source, is_rl = orchestrator.process_transcript(self.sample_transcript)

        self.assertEqual(source, "RULE-BASED FALLBACK")
        self.assertIsInstance(analysis, MeetingAnalysis)
        self.assertTrue(len(analysis.summary) > 0)
        self.assertIsNotNone(analysis.validation)

    # -----------------------------------------------------------------------
    # 6. Complete Orchestrator Workflow
    # -----------------------------------------------------------------------
    def test_10_complete_orchestrator_mocked_workflow(self):
        """Test 10: Complete orchestrator coordinates preprocessor -> agents -> validation -> output."""
        mock_summary_agent = MagicMock()
        mock_summary_agent.generate_summary.return_value = "The Robotics Club met to plan the hackathon for November 15th."

        mock_action_agent = MagicMock()
        mock_action_agent.extract_action_items.return_value = [
            ActionItem(task="Finalize sponsorship proposal", owner="Jordan", deadline="Friday", status="pending")
        ]

        mock_decision_agent = MagicMock()
        mock_decision_agent.extract_decisions.return_value = (
            ["Host the hackathon on November 15th"],
            [DecisionItem(decision="Host the hackathon on November 15th", confidence=1.0, evidence="We all agreed")],
            ["Guest speaker confirmation"]
        )

        mock_analyzer = MagicMock(spec=GeminiAnalyzer)
        mock_analyzer.is_configured = True
        mock_analyzer.model_name = "gemini-3.6-flash"

        orchestrator = AgentOrchestrator(
            gemini_analyzer=mock_analyzer,
            summary_agent=mock_summary_agent,
            action_agent=mock_action_agent,
            decision_agent=mock_decision_agent,
        )

        analysis, source, is_rl = orchestrator.process_transcript(self.sample_transcript)

        self.assertEqual(source, "AGENTIC_GEMINI")
        self.assertFalse(is_rl)
        self.assertEqual(analysis.summary, "The Robotics Club met to plan the hackathon for November 15th.")
        self.assertEqual(len(analysis.action_items), 1)
        self.assertEqual(analysis.action_items[0].owner, "Jordan")
        self.assertEqual(len(analysis.decisions), 1)
        self.assertEqual(len(analysis.unresolved_issues), 1)
        self.assertIsNotNone(analysis.validation)
        self.assertTrue(analysis.validation.all_grounded)


    # -----------------------------------------------------------------------
    # 7. Rate-limit and Retry-After handling
    # -----------------------------------------------------------------------
    def test_11_retry_after_extraction_from_error_message(self):
        """Test 11: GeminiAnalyzer._extract_retry_after parses Retry-After seconds from error strings."""
        from app.services.gemini_analyzer import GeminiAnalyzer

        # Pattern: 'retry_delay { seconds: 30 }'
        assert GeminiAnalyzer._extract_retry_after("retry_delay { seconds: 30 }") == 30.0
        # Pattern: 'Retry-After: 45'
        assert GeminiAnalyzer._extract_retry_after("Retry-After: 45") == 45.0
        # Pattern: 'retryDelay: 60'
        assert GeminiAnalyzer._extract_retry_after("retryDelay: 60") == 60.0
        # No match → None
        assert GeminiAnalyzer._extract_retry_after("some other error text") is None

    def test_12_rate_limit_error_detected_in_fallback(self):
        """Test 12: A 429/RESOURCE_EXHAUSTED error sets is_rate_limited=True via orchestrator fallback."""
        err_msg = "429 RESOURCE_EXHAUSTED: quota exceeded"
        rate_limited_error = GeminiAnalysisError(err_msg)
        rate_limited_error.is_rate_limit = True

        mock_summary_agent = MagicMock()
        mock_summary_agent.generate_summary.side_effect = rate_limited_error

        mock_analyzer = MagicMock(spec=GeminiAnalyzer)
        mock_analyzer.is_configured = True
        mock_analyzer.model_name = "gemini-3.6-flash"

        orchestrator = AgentOrchestrator(
            gemini_analyzer=mock_analyzer,
            summary_agent=mock_summary_agent,
        )

        analysis, source, is_rl = orchestrator.process_transcript(self.sample_transcript)

        self.assertEqual(source, "RULE-BASED FALLBACK")
        self.assertTrue(is_rl, "is_rate_limited must be True when a 429 error triggers fallback")
        self.assertIsInstance(analysis, MeetingAnalysis)

    def test_13_orchestrator_inter_agent_delay_configured(self):
        """Test 13: AgentOrchestrator has _INTER_AGENT_DELAY_S > 0 (pacing constant present)."""
        self.assertGreater(
            AgentOrchestrator._INTER_AGENT_DELAY_S,
            0,
            "Inter-agent delay must be positive to pace Gemini calls.",
        )


if __name__ == "__main__":
    unittest.main()

