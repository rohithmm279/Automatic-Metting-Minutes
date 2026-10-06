"""Comprehensive tests for meeting metadata extraction (title, date, time), edge cases, and export formatting."""

from datetime import date
import json
import pytest
from unittest.mock import MagicMock

from backend.ai.orchestrator import (
    MeetingOrchestrator,
    _extract_title_from_transcript,
    _extract_human_date_from_transcript,
    _extract_time_from_transcript,
    _extract_date_from_transcript,
)
from backend.models.meeting import MeetingOutput, ActionItem, Decision, UnresolvedIssue
from backend.database.repository import MeetingRepository
from backend.database.schema import init_db


def test_01_transcript_with_explicit_bracket_title():
    transcript = "[Meeting: Robotics Autonomous Nav Sprint | Date: 18 September 2026 | Time: 10:00 AM - 11:30 AM]\nAlice: Let's test the lidar sensors.\nBob: I will test lidar by Friday."
    title = _extract_title_from_transcript(transcript)
    date_str = _extract_human_date_from_transcript(transcript)
    time_str, st, et = _extract_time_from_transcript(transcript)

    assert title == "Robotics Autonomous Nav Sprint"
    assert "18 September 2026" in date_str
    assert time_str == "10:00 AM - 11:30 AM"
    assert st == "10:00 AM"
    assert et == "11:30 AM"


def test_02_transcript_with_header_colon_title():
    transcript = "Meeting: Cultural Fest Budget Sync\nDate: 2026-10-15\nTime: 3:00 PM\nPriya: Let us review the decorator quote."
    title = _extract_title_from_transcript(transcript)
    date_str = _extract_human_date_from_transcript(transcript)
    time_str, st, et = _extract_time_from_transcript(transcript)

    assert title == "Cultural Fest Budget Sync"
    assert date_str == "2026-10-15"
    assert time_str == "3:00 PM"
    assert st == "3:00 PM"
    assert et is None


def test_03_transcript_without_title():
    transcript = "Alice: Hey team, let's look at the open tickets.\nBob: I will take ticket 402."
    title = _extract_title_from_transcript(transcript)
    assert title is None


def test_04_transcript_with_date_and_time_ranges():
    transcript = "Date/Time: Tuesday, Oct 14, 2025, 2:00 PM - 3:30 PM\nSpeaker A: Hello everyone."
    date_str = _extract_human_date_from_transcript(transcript)
    time_str, st, et = _extract_time_from_transcript(transcript)

    assert "Oct 14, 2025" in date_str
    assert time_str == "2:00 PM - 3:30 PM"
    assert st == "2:00 PM"
    assert et == "3:30 PM"


def test_05_transcript_with_date_but_no_time():
    transcript = "Date: November 25, 2026\nPriya: We have all hands next week."
    date_str = _extract_human_date_from_transcript(transcript)
    time_str, st, et = _extract_time_from_transcript(transcript)

    assert "November 25, 2026" in date_str
    assert time_str is None
    assert st is None
    assert et is None


def test_06_ambiguous_datetime_in_body():
    transcript = "Priya: Let's meet next Friday at 4 PM.\nVikram: Agreed."
    # Header should not produce a false meeting date if no header exists
    date_obj = _extract_date_from_transcript(transcript)
    assert date_obj is None


def test_07_long_meeting_title():
    long_title = "Joint Inter-Club Annual Technical & Cultural Symposium Core Executive Steering Committee Sync"
    transcript = f"[Meeting: {long_title}]\nPriya: Starting the discussion."
    title = _extract_title_from_transcript(transcript)
    assert title == long_title


def test_08_empty_decisions_and_issues_persistence(tmp_path):
    db_file = tmp_path / "test_empty_sections.db"
    repo = MeetingRepository(db_path=db_file)

    output = MeetingOutput(
        summary="Brief sync with only action items.",
        action_items=[ActionItem(task="Deploy hotfix", owner="Dev", deadline="Today", status="pending", confidence=1.0)],
        decisions=[],
        unresolved_issues=[],
        title="Hotfix Quick Sync",
        meeting_date="2026-09-20",
        meeting_time="5:00 PM",
        start_time="5:00 PM",
        end_time=None,
    )

    meeting_id = repo.save_meeting("Dev: I will deploy hotfix today.", output)
    retrieved = repo.get_meeting(meeting_id)

    assert retrieved is not None
    assert retrieved["title"] == "Hotfix Quick Sync"
    assert retrieved["meeting_date"] == "2026-09-20"
    assert retrieved["meeting_time"] == "5:00 PM"
    assert len(retrieved["action_items"]) == 1
    assert len(retrieved["decisions"]) == 0
    assert len(retrieved["unresolved_issues"]) == 0


def test_09_long_transcript_metadata_extraction():
    long_dialogue = "\n".join([f"Speaker {i%4}: Discussing agenda item {i} in detail." for i in range(150)])
    full_transcript = "[Meeting: Marathon Hackathon Planning | Date: 12 December 2026 | Time: 9:00 AM - 6:00 PM]\n" + long_dialogue
    title = _extract_title_from_transcript(full_transcript)
    date_str = _extract_human_date_from_transcript(full_transcript)
    time_str, st, et = _extract_time_from_transcript(full_transcript)

    assert title == "Marathon Hackathon Planning"
    assert "12 December 2026" in date_str
    assert time_str == "9:00 AM - 6:00 PM"


def test_10_orchestrator_attaches_all_metadata():
    mock_client = MagicMock()
    mock_client.generate.return_value = json.dumps({
        "summary": "Team aligned on festival preparation.",
        "action_items": [{"task": "Book auditorium", "owner": "Aditya", "deadline": "Friday", "status": "pending"}],
        "decisions": ["Proceed with stage design A"],
        "unresolved_issues": ["Security clearance pending"]
    })

    orchestrator = MeetingOrchestrator(client=mock_client)
    transcript = "[Meeting: Annual Fest Core Sync | Date: 18 September 2026 | Time: 10:00 AM - 11:30 AM]\nPriya: Let us begin.\nAditya: I will book the auditorium by Friday."
    res = orchestrator.analyze(transcript)

    assert res.title == "Annual Fest Core Sync"
    assert res.meeting_date == "18 September 2026"
    assert res.meeting_time == "10:00 AM - 11:30 AM"
    assert res.start_time == "10:00 AM"
    assert res.end_time == "11:30 AM"
    assert len(res.action_items) == 1
    assert len(res.decisions) == 1
    assert len(res.unresolved_issues) == 1


def test_11_markdown_formatted_title_and_metadata():
    transcript = (
        "**Weekly Product Sync – Atlas Platform**  \n"
        "**Date:** September 20, 2026  \n"
        "**Time:** 2:00 PM IST  \n\n"
        "Maya: Let’s begin. We need to finalize the pricing experiment and the mobile release window today."
    )
    title = _extract_title_from_transcript(transcript)
    date_str = _extract_human_date_from_transcript(transcript)
    time_str, st, et = _extract_time_from_transcript(transcript)

    assert title == "Weekly Product Sync – Atlas Platform"
    assert "September 20, 2026" in date_str
    assert "2:00 PM" in time_str


def test_12_runtime_timestamp_distinct_from_meeting_time(tmp_path):
    db_file = tmp_path / "test_header_ts.db"
    repo = MeetingRepository(db_path=db_file)

    transcript = (
        "**Weekly Product Sync – Atlas Platform**\n"
        "**Date:** September 20, 2026\n"
        "**Time:** 2:00 PM IST\n\n"
        "Maya: Meeting started."
    )
    output = MeetingOutput(
        summary="Weekly product sync meeting.",
        action_items=[],
        decisions=[],
        unresolved_issues=[],
        title="Weekly Product Sync – Atlas Platform",
        meeting_date="September 20, 2026",
        meeting_time="2:00 PM IST",
        start_time="2:00 PM IST",
    )
    meeting_id = repo.save_meeting(transcript, output)
    row = repo.get_meeting(meeting_id)

    assert row is not None
    assert row["meeting_date"] == "September 20, 2026"
    assert row["meeting_time"] == "2:00 PM IST"
    assert row["created_at"] is not None


def test_13_forward_relative_date_math():
    from app.agents.orchestrator import AgentOrchestrator
    import datetime

    meeting_date = datetime.date(2026, 9, 20)  # Sunday

    # "by Wednesday" forward from Sunday Sep 20 -> Wednesday Sep 23
    dl_wed = AgentOrchestrator._format_iso_deadline("by Wednesday", meeting_date)
    assert dl_wed == "2026-09-23"

    # "today" -> 2026-09-20
    dl_today = AgentOrchestrator._format_iso_deadline("today", meeting_date)
    assert dl_today == "2026-09-20"

    # Erroneous past date (2026-09-03) resolved with evidence "by Wednesday"
    task, owner, dl_resolved = AgentOrchestrator._resolve_owner_and_deadline(
        task="Escalate billing provider sandbox stability issue",
        owner="Dev",
        deadline="2026-09-03",
        evidence="I’ll escalate to their support lead by Wednesday if it doesn’t stabilize.",
        transcript_clean="Dev: I’ll escalate to their support lead by Wednesday if it doesn’t stabilize.",
        meeting_date=meeting_date,
    )
    assert dl_resolved == "2026-09-23"


def test_14_decision_filtering_rejects_tasks_and_risk_mitigations():
    from app.agents.orchestrator import AgentOrchestrator
    from app.schemas.meeting_schema import ActionItem, DecisionItem

    action_items = [
        ActionItem(task="Escalate billing provider's sandbox stability issue to support lead", owner="Dev Kapoor", deadline="2026-09-23")
    ]
    raw_decisions = [
        "Launch pricing experiment on September 29, 2026 (pending bugs/QA)",
        "Keep current paywall layout for the experiment",
        "Monitor conversion daily and decide on changes after seven days of data",
        "Hard freeze campaign creatives today if sandbox latency persists",
        "Escalate billing provider's sandbox stability issue by Wednesday if it doesn't stabilize",
    ]
    raw_detailed = [DecisionItem(decision=d) for d in raw_decisions]

    filtered_flat, filtered_detailed = AgentOrchestrator._filter_action_items_from_decisions(
        raw_decisions, raw_detailed, action_items
    )

    assert len(filtered_flat) == 3
    assert "Launch pricing experiment on September 29, 2026 (pending bugs/QA)" in filtered_flat
    assert "Keep current paywall layout for the experiment" in filtered_flat
    assert "Monitor conversion daily and decide on changes after seven days of data" in filtered_flat
    assert not any("Hard freeze" in d for d in filtered_flat)
    assert not any("Escalate billing provider" in d for d in filtered_flat)


def test_15_timestamp_speaker_attribution_and_deduplication():
    import datetime
    from app.agents.orchestrator import AgentOrchestrator
    from app.schemas.meeting_schema import ActionItem

    meeting_date = datetime.date(2026, 9, 20)  # Sunday
    transcript = "[00:03:51] Karthik: Okay, I'll send the meeting link in the group."

    task, owner, deadline = AgentOrchestrator._resolve_owner_and_deadline(
        task="Send the meeting link in the group",
        owner="Not specified",
        deadline="Not specified",
        evidence="[00:03:51] Karthik: Okay, I'll send the meeting link in the group.",
        transcript_clean=transcript,
        meeting_date=meeting_date,
    )
    assert owner == "Karthik"

    # Test deduplication merging
    items = [
        ActionItem(task="Send the meeting link in the group", owner="Karthik", deadline="Not specified"),
        ActionItem(task="Send meeting link in group", owner="Not specified", deadline="2026-09-24"),
    ]
    deduped = AgentOrchestrator._deduplicate_action_items(items)
    assert len(deduped) == 1
    assert deduped[0].owner == "Karthik"
    assert deduped[0].deadline == "2026-09-24"


def test_16_role_assignment_decision_migration():
    from app.agents.orchestrator import AgentOrchestrator
    from app.schemas.meeting_schema import ActionItem, DecisionItem

    action_items = []
    raw_decisions = [
        "Use FAISS for vector search and Streamlit for UI",
        "Adopt 'StudyGen' as project name",
        "Arun will handle the RAG feature and backend development",
        "Karthik will handle UI development",
    ]
    raw_detailed = [DecisionItem(decision=d) for d in raw_decisions]

    filtered_flat, filtered_detailed = AgentOrchestrator._filter_action_items_from_decisions(
        raw_decisions, raw_detailed, action_items
    )

    # Decisions should only contain the 2 architectural/naming decisions
    assert len(filtered_flat) == 2
    assert "Use FAISS for vector search and Streamlit for UI" in filtered_flat
    assert "Adopt 'StudyGen' as project name" in filtered_flat
    assert not any("will handle" in d for d in filtered_flat)

    # Action items should now have the 2 migrated tasks
    assert len(action_items) == 2
    arun_item = next(ai for ai in action_items if ai.owner == "Arun")
    assert "RAG feature" in arun_item.task
    karthik_item = next(ai for ai in action_items if ai.owner == "Karthik")
    assert "UI development" in karthik_item.task



