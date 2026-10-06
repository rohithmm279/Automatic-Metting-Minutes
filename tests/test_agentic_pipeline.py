"""Deterministic unit tests for Agentic AI Pipeline (Summary, Action, Decision, Validation, Orchestrator, Fallback)."""

import json
import datetime
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
from backend.ai.prompts import build_meeting_analysis_prompt


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

    def test_action_prompt_prioritizes_explicit_wrap_up_assignments(self):
        """The production prompt must preserve named wrap-up tasks and deadlines."""
        prompt = build_meeting_analysis_prompt("Priya: Action Items: Draft the design by Wednesday, September 23rd.")

        self.assertIn("Treat a transcript wrap-up", prompt)
        self.assertIn("preserving its named owner and explicit deadline", prompt)
        self.assertIn("Do not replace a wrap-up task with the broader decision", prompt)

    def test_prompt_separates_tentative_dates_from_confirmed_format(self):
        """The production prompt must distinguish pending approval from decisions."""
        prompt = build_meeting_analysis_prompt("Date: September 21, 2026\nArun: October 7th is tentative and needs faculty approval.")

        self.assertIn("PENDING APPROVAL RULE", prompt)
        self.assertIn("FORMAT DECISIONS", prompt)
        self.assertIn('"tomorrow" = 2026-09-22', prompt)
        self.assertIn("deadline 2026-09-23", prompt)

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

    def test_01b_unrelated_input_is_rejected_before_gemini(self):
        """Plain unrelated content must not enter the agentic extraction path."""
        mock_analyzer = MagicMock(spec=GeminiAnalyzer)
        mock_analyzer.is_configured = True
        orchestrator = AgentOrchestrator(gemini_analyzer=mock_analyzer)

        with self.assertRaisesRegex(ValueError, "does not look like a meeting transcript"):
            orchestrator.process_transcript("A recipe for pancakes with blueberries and honey.")

        mock_analyzer.generate_json.assert_not_called()

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

    def test_14_single_gemini_call_workflow(self):
        """Test 14: Default AgentOrchestrator invokes GeminiAnalyzer.generate_json exactly ONCE per meeting."""
        mock_analyzer = MagicMock(spec=GeminiAnalyzer)
        mock_analyzer.is_configured = True
        mock_analyzer.model_name = "gemini-3.5-flash-lite"
        mock_analyzer._build_prompt = GeminiAnalyzer._build_prompt
        mock_analyzer.generate_json.return_value = {
            "summary": "The Robotics Club met to plan the hackathon for November 15th. Jordan is tasked with finalizing the sponsorship proposal.",
            "action_items": [
                {
                    "task": "Finalize sponsorship proposal",
                    "owner": "Jordan",
                    "deadline": "Friday",
                    "status": "pending",
                    "confidence": 1.0,
                    "evidence": "Jordan: I will finalize the sponsorship proposal by Friday.",
                }
            ],
            "decisions": ["Host the hackathon on November 15th"],
            "unresolved_issues": ["Guest speaker confirmation"],
        }

        # Use default agent instances connected to mock_analyzer
        orchestrator = AgentOrchestrator(gemini_analyzer=mock_analyzer)

        analysis, source, is_rl = orchestrator.process_transcript(self.sample_transcript)

        # Verify exactly ONE Gemini API call
        self.assertEqual(mock_analyzer.generate_json.call_count, 1)
        self.assertEqual(source, "AGENTIC_GEMINI")
        self.assertFalse(is_rl)
        self.assertEqual(analysis.summary, "The Robotics Club met to plan the hackathon for November 15th. Jordan is tasked with finalizing the sponsorship proposal.")
        self.assertEqual(len(analysis.action_items), 1)
        self.assertEqual(analysis.action_items[0].owner, "Jordan")
        self.assertEqual(analysis.action_items[0].deadline, "Friday")
        self.assertEqual(analysis.action_items[0].evidence, "Jordan: I will finalize the sponsorship proposal by Friday.")
        self.assertEqual(len(analysis.decisions), 1)
        self.assertEqual(len(analysis.unresolved_issues), 1)
        self.assertIsNotNone(analysis.validation)
        self.assertTrue(analysis.validation.all_grounded)

    def test_15_structured_wrapup_list_entity_resolution(self):
        """Test 15: Entity resolution recovers owners from list format even if unassigned in LLM output."""
        transcript = (
            "Alex: Let's quickly review action items before we wrap up:\n"
            "1. Marcus: Update the pricing calculator specs in Figma to clarify frontend-only JS logic by EOD tomorrow.\n"
            "2. Elena: Finalize staging build and prepare for QA sign-off by October 1st.\n"
            "3. Sarah: Finalize social media schedule and press outreach for October 6th launch date.\n"
            "4. Alex: Draft launch release notes and send them out for executive review by Friday."
        )
        mock_analyzer = MagicMock(spec=GeminiAnalyzer)
        mock_analyzer.is_configured = True
        mock_analyzer.model_name = "gemini-3.6-flash"
        mock_analyzer._build_prompt = GeminiAnalyzer._build_prompt
        # Simulate LLM returning unassigned owners
        mock_analyzer.generate_json.return_value = {
            "summary": "Alex reviewed the upcoming tasks for Marcus, Elena, Sarah, and himself.",
            "action_items": [
                {
                    "task": "Update the pricing calculator specs in Figma",
                    "owner": None,
                    "deadline": None,
                    "evidence": "1. Marcus: Update the pricing calculator specs in Figma to clarify frontend-only JS logic by EOD tomorrow.",
                },
                {
                    "task": "Finalize staging build and prepare for QA sign-off",
                    "owner": "Not specified",
                    "deadline": "October 1st",
                    "evidence": "2. Elena: Finalize staging build and prepare for QA sign-off by October 1st.",
                },
                {
                    "task": "Finalize social media schedule and press outreach",
                    "owner": None,
                    "deadline": "October 6th",
                    "evidence": "3. Sarah: Finalize social media schedule and press outreach for October 6th launch date.",
                },
                {
                    "task": "Draft launch release notes",
                    "owner": None,
                    "deadline": "Friday",
                    "evidence": "4. Alex: Draft launch release notes and send them out for executive review by Friday.",
                },
            ],
            "decisions": ["Official public release scheduled for October 6th"],
            "unresolved_issues": [],
        }

        orchestrator = AgentOrchestrator(gemini_analyzer=mock_analyzer)
        analysis, source, _ = orchestrator.process_transcript(transcript)

        self.assertEqual(len(analysis.action_items), 4)
        self.assertEqual(analysis.action_items[0].owner, "Marcus")
        self.assertEqual(analysis.action_items[1].owner, "Elena")
        self.assertEqual(analysis.action_items[2].owner, "Sarah")
        self.assertEqual(analysis.action_items[3].owner, "Alex")

    def test_16_rule_based_fallback_on_structured_transcript(self):
        """Test 16: Fallback analyzer extracts owners, deadlines, and consensus decisions."""
        transcript = (
            "Marcus: Frontend JS calculations are completely fine for v1.\n"
            "Alex: Great. Let's make October 6th official.\n"
            "Alex: Action items:\n"
            "1. Marcus: Update pricing calculator specs in Figma by EOD tomorrow.\n"
            "2. Elena: Finalize staging build by October 1st."
        )
        analyzer = MeetingAnalyzer()
        res = analyzer.analyze(transcript)

        self.assertEqual(len(res.action_items), 2)
        self.assertEqual(res.action_items[0].owner, "Marcus")
        self.assertEqual(res.action_items[1].owner, "Elena")
        self.assertTrue(any("October 6th" in d for d in res.decisions))

    def test_18_decision_prefix_is_cleaned_and_conditional_risk_commitment_is_action(self):
        transcript = (
            "Aarav: Decision – we go ahead with TechVista 2026 on October 18, 2026, only if both pending sponsorships are confirmed.\n"
            "Kabir: One more risk – the college admin portal has been down since morning. "
            "I’ll escalate to the student affairs office by Wednesday if it stays down."
        )

        result = MeetingAnalyzer().analyze(transcript)

        self.assertEqual(
            result.decisions,
            ["We go ahead with TechVista 2026 on October 18, 2026, only if both pending sponsorships are confirmed"],
        )
        self.assertTrue(any("Escalate to the student affairs office" in item.task for item in result.action_items))
        self.assertEqual(result.action_items[0].owner, "Kabir")

    def test_20_sc002_deferrals_are_issues_and_tonight_is_meeting_date(self):
        from app.agents.orchestrator import AgentOrchestrator
        from app.schemas.meeting_schema import DecisionItem

        deferred, detailed, issues = AgentOrchestrator._move_deferred_decisions_to_issues(
            ["The event date will be decided after the availability poll"],
            [DecisionItem(decision="The event date will be decided after the availability poll")],
            [],
        )

        self.assertEqual(deferred, [])
        self.assertEqual(detailed, [])
        self.assertEqual(issues, ["The event date will be decided after the availability poll"])
        self.assertEqual(
            AgentOrchestrator._format_iso_deadline("tonight", datetime.date(2026, 9, 21)),
            "2026-09-21",
        )

    def test_21_header_date_is_not_an_implicit_action_deadline(self):
        self.assertFalse(
            AgentOrchestrator._deadline_is_explicit_for_action(
                "2026-09-22", "Create the GitHub repository", "Arun: I'll create the GitHub repository."
            )
        )
        self.assertTrue(
            AgentOrchestrator._deadline_is_explicit_for_action(
                "2026-09-23", "Join the complete test", "Rohith: We'll test together tomorrow at 7 PM."
            )
        )

    def test_22_followup_attendance_is_not_an_action_item(self):
        self.assertTrue(
            AgentOrchestrator._is_unassigned_meeting_attendance(
                "Everyone joins tomorrow at 7 PM on Discord", "Not specified"
            )
        )
        self.assertFalse(
            AgentOrchestrator._is_unassigned_meeting_attendance(
                "Create the Discord meeting", "Not specified"
            )
        )

    def test_23_action_is_not_repeated_as_unresolved_issue(self):
        action = ActionItem(task="Check the event guidelines", owner="Priya")
        issues = AgentOrchestrator._remove_action_issue_duplicates(
            ["Check the event guidelines", "API free usage limit remains unknown"], [action]
        )
        self.assertEqual(issues, ["API free usage limit remains unknown"])

    def test_17_incident_retro_guardrails(self):
        """Test 17: Validates anti-contamination, meta-task filtering, timestamp safety, and self-commitments."""
        transcript = (
            "Rachel: Welcome to the INC-8821 outage retrospective.\n"
            "Dev: At 11:02 AM automated alerts triggered due to Redis lock contention.\n"
            "Maya: We need a hard circuit breaker for CI/CD jobs older than 24h. I'll build it.\n"
            "Dev: I can update status page auto-trigger logic for >5% error rate.\n"
            "Carlos: I will handle customer support communication latency.\n"
            "Rachel: Let's log these action items and assign them in Jira."
        )

        mock_analyzer = MagicMock(spec=GeminiAnalyzer)
        mock_analyzer.is_configured = True
        mock_analyzer.model_name = "gemini-3.6-flash"
        mock_analyzer.generate_json.return_value = {
            "summary": "Team conducted INC-8821 retrospective. Maya committed to building the CI/CD pipeline circuit breaker, Dev will update status page logic, and Carlos will address communication latency.",
            "action_items": [
                {
                    "task": "Build the CI/CD pipeline circuit breaker",
                    "owner": None,
                    "deadline": None,
                    "evidence": "Maya: We need a hard circuit breaker for CI/CD jobs older than 24h. I'll build it.",
                },
                {
                    "task": "Update status page auto-trigger logic",
                    "owner": "Dev",
                    "deadline": "11:02 AM",  # Erroneous incident timestamp from LLM
                    "evidence": "Dev: At 11:02 AM automated alerts triggered",
                },
                {
                    "task": "Address status page communication latency for customer support",
                    "owner": "Carlos",
                    "deadline": None,
                    "evidence": "Carlos: I will handle customer support communication latency.",
                },
                {
                    "task": "Log the action items and assign them in Jira",  # Meta-task
                    "owner": "Rachel",
                    "deadline": None,
                    "evidence": "Rachel: Let's log these action items and assign them in Jira.",
                },
            ],
            "decisions": ["Deploy circuit breaker for jobs older than 24h"],
            "unresolved_issues": [
                "Latency spikes on the search endpoint",  # Contamination from other meeting
                "Waiting on brand team approval for updated UI tokens",  # Contamination from other meeting
            ],
        }

        orchestrator = AgentOrchestrator(gemini_analyzer=mock_analyzer)
        analysis, _, _ = orchestrator.process_transcript(transcript)

        # 1. Verify ungrounded hallucinated issues from other meetings were completely pruned
        self.assertEqual(analysis.unresolved_issues, [])

        # 2. Verify meta-task was filtered out (leaving 3 real engineering tasks)
        tasks = [a.task for a in analysis.action_items]
        self.assertFalse(any(t.lower().startswith("log ") or "assign them" in t.lower() for t in tasks))
        self.assertEqual(len(analysis.action_items), 3)

        # 3. Verify self-commitment correctly assigned Maya (not Dev)
        maya_task = next(a for a in analysis.action_items if "circuit breaker" in a.task.lower())
        self.assertEqual(maya_task.owner, "Maya")

        # 4. Verify incident timestamp 11:02 AM was neutralized
        dev_task = next(a for a in analysis.action_items if "status page" in a.task.lower())
        self.assertEqual(dev_task.deadline, "Not specified")

    def test_18_relative_date_and_decision_filtering(self):
        """Test 18: Verify relative date resolution to ISO YYYY-MM-DD and decision task filtering."""
        transcript = (
            "Meeting Date: September 20, 2026\n"
            "Maya: Proceed with Beta release on October 5, 2026.\n"
            "Dev: Retain progressive disclosure onboarding design for Beta.\n"
            "Priya: I will circulate the final feature freeze list today, September 20, 2026 EOD.\n"
            "Arjun: I will escalate the third-party payment gateway issue tomorrow."
        )

        mock_analyzer = MagicMock(spec=GeminiAnalyzer)
        mock_analyzer.is_configured = True
        mock_analyzer.model_name = "gemini-3.6-flash"
        mock_analyzer.generate_json.return_value = {
            "summary": "Team aligned on Beta release on October 5, 2026 and retaining onboarding design.",
            "action_items": [
                {
                    "task": "Circulate final feature freeze list",
                    "owner": "Priya",
                    "deadline": "today, September 20, 2026 EOD",
                    "evidence": "Priya: I will circulate the final feature freeze list today, September 20, 2026 EOD.",
                },
                {
                    "task": "Escalate third-party payment gateway issue",
                    "owner": "Arjun",
                    "deadline": "tomorrow",
                    "evidence": "Arjun: I will escalate the third-party payment gateway issue tomorrow.",
                },
            ],
            "decisions": [
                "Proceed with Beta release on October 5, 2026",
                "Retain progressive disclosure onboarding design for Beta",
                "Circulate final feature freeze list to stakeholders",  # Should be filtered out (action item)
                "Arjun Mehta to escalate payment gateway issue",  # Should be filtered out (action item)
            ],
            "unresolved_issues": [
                "No issues identified",  # Dummy risk item, should be filtered out
            ],
        }

        orchestrator = AgentOrchestrator(gemini_analyzer=mock_analyzer)
        analysis, _, _ = orchestrator.process_transcript(transcript)

        # 1. Action items relative dates converted to ISO YYYY-MM-DD
        priya_task = next(a for a in analysis.action_items if "freeze list" in a.task.lower())
        self.assertEqual(priya_task.deadline, "2026-09-20")

        arjun_task = next(a for a in analysis.action_items if "payment gateway" in a.task.lower())
        self.assertEqual(arjun_task.deadline, "2026-09-21")

        # 2. Key Decisions contain only structural decisions, NOT individual action items
        self.assertEqual(len(analysis.decisions), 2)
        self.assertIn("Proceed with Beta release on October 5, 2026", analysis.decisions)
        self.assertIn("Retain progressive disclosure onboarding design for Beta", analysis.decisions)
        self.assertFalse(any("freeze list" in d.lower() or "arjun" in d.lower() for d in analysis.decisions))

        # 3. Unresolved issues pruned of dummy "No issues identified" -> empty list
        self.assertEqual(analysis.unresolved_issues, [])

    def test_19_forward_date_computation_and_decision_discriminator(self):
        """Test 19: Forward weekday date computation and decision discriminator for recipient handoffs."""
        transcript = (
            "Meeting Date: Sunday, September 20, 2026\n"
            "Maya: Proceed with Beta release on October 5, 2026.\n"
            "Priya: I will circulate the final feature freeze list to stakeholders.\n"
            "Arjun: I'll escalate to their account manager by Tuesday if it continues."
        )

        mock_analyzer = MagicMock(spec=GeminiAnalyzer)
        mock_analyzer.is_configured = True
        mock_analyzer.model_name = "gemini-3.6-flash"
        mock_analyzer.generate_json.return_value = {
            "summary": "Team agreed to proceed with Beta release on October 5, 2026.",
            "action_items": [
                {
                    "task": "Circulate final feature freeze list to stakeholders",
                    "owner": "Priya",
                    "deadline": "today",
                    "evidence": "Priya: I will circulate the final feature freeze list to stakeholders.",
                },
                {
                    "task": "Escalate to account manager if gateway issues continue",
                    "owner": "Arjun",
                    "deadline": "by Tuesday",
                    "evidence": "Arjun: I'll escalate to their account manager by Tuesday if it continues.",
                },
            ],
            "decisions": [
                "Proceed with Beta release on October 5, 2026",
                "Marketing will receive the final feature list and known limitations",  # Action item handoff, should be filtered out
            ],
            "unresolved_issues": [],
        }

        orchestrator = AgentOrchestrator(gemini_analyzer=mock_analyzer)
        analysis, _, _ = orchestrator.process_transcript(transcript)

        # 1. Tuesday after Sunday Sept 20, 2026 MUST be Tuesday Sept 22, 2026 (2026-09-22), NOT in the past (2026-09-14)
        arjun_task = next(a for a in analysis.action_items if "account manager" in a.task.lower())
        self.assertEqual(arjun_task.deadline, "2026-09-22")

        # 2. Decision discriminator rejects "Marketing will receive the final feature list..."
        self.assertEqual(len(analysis.decisions), 1)
        self.assertEqual(analysis.decisions[0], "Proceed with Beta release on October 5, 2026")


if __name__ == "__main__":
    unittest.main()





