"""End-to-end test for SQLite persistence layer with real AI pipeline execution on SC001."""

import os
from pathlib import Path
import sqlite3
import sys

# Set up paths
ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BACKEND))

from backend.ai.orchestrator import MeetingOrchestrator
from backend.database.repository import MeetingRepository
from backend.database.connection import get_connection
from backend.models.meeting import MeetingOutput, ActionItem, Decision, UnresolvedIssue


def run_e2e_persistence_test():
    print("=" * 70)
    print("REAL END-TO-END PERSISTENCE TEST (SC001)")
    print("=" * 70)

    # 1. Read transcript
    transcript_path = ROOT / "datasets" / "01_PRIMARY" / "student_club" / "transcripts" / "SC001.txt"
    if not transcript_path.exists():
        raise FileNotFoundError(f"Transcript not found at {transcript_path}")
    
    transcript = transcript_path.read_text(encoding="utf-8")
    print(f"[1] Loaded transcript SC001 ({len(transcript)} chars, {len(transcript.splitlines())} lines).")

    # 2. Run the existing MeetingOrchestrator
    print("[2] Running MeetingOrchestrator with local Qwen2.5:3b via Ollama...")
    orchestrator = MeetingOrchestrator(temperature=0.0)
    validated_output = orchestrator.analyze(transcript)
    print("    Inference & validation succeeded!")
    print(f"    Summary preview: {validated_output.summary[:90]}...")
    print(f"    Action items count: {len(validated_output.action_items)}")
    print(f"    Decisions count: {len(validated_output.decisions)}")
    print(f"    Unresolved issues count: {len(validated_output.unresolved_issues)}")

    # 3. Save the validated result to SQLite
    test_db_path = ROOT / "backend" / "test_meetings.db"
    if test_db_path.exists():
        test_db_path.unlink()  # Clean start for pristine test run

    repo = MeetingRepository(db_path=test_db_path)
    print(f"[3] Saving validated MeetingOutput to SQLite at {test_db_path}...")
    meeting_id = repo.save_meeting(transcript=transcript, meeting_output=validated_output)
    print(f"    Saved meeting successfully with meeting_id = {meeting_id}")
    assert meeting_id > 0, f"Expected positive integer meeting_id, got {meeting_id}"

    # 4. Retrieve from SQLite
    print(f"[4] Retrieving meeting {meeting_id} from SQLite...")
    retrieved = repo.get_meeting(meeting_id)
    assert retrieved is not None, f"Failed to retrieve meeting with ID {meeting_id}"

    # 5. Verify summary, action items, decisions, and unresolved issues
    print("[5] Verifying retrieved components against original validated output...")
    assert retrieved["summary"] == validated_output.summary, "Summary does not match!"
    assert retrieved["transcript"] == transcript, "Transcript does not match!"
    assert len(retrieved["action_items"]) == len(validated_output.action_items), "Action item count mismatch!"
    assert len(retrieved["decisions"]) == len(validated_output.decisions), "Decisions count mismatch!"
    assert len(retrieved["unresolved_issues"]) == len(validated_output.unresolved_issues), "Unresolved issues count mismatch!"
    print("    All counts and text contents match the AI output perfectly.")

    # 6. Verify nullable owner/deadline values remain NULL where appropriate
    print("[6] Checking nullable owner and deadline integrity...")
    null_owner_or_deadline_found = False
    for ai_item, db_item in zip(validated_output.action_items, retrieved["action_items"]):
        assert db_item["task"] == ai_item.task
        assert db_item["status"] == ai_item.status
        if ai_item.owner is None:
            assert db_item["owner"] is None, f"Expected NULL owner, got {db_item['owner']}"
            null_owner_or_deadline_found = True
        else:
            assert db_item["owner"] == ai_item.owner
        if ai_item.deadline is None:
            assert db_item["deadline"] is None, f"Expected NULL deadline, got {db_item['deadline']}"
            null_owner_or_deadline_found = True
        else:
            assert db_item["deadline"] == ai_item.deadline
    
    # Also explicitly test saving a record that deliberately has NULL owner and NULL deadline
    test_null_output = MeetingOutput(
        summary="Test meeting with null owner and deadline.",
        action_items=[
            ActionItem(task="Unassigned task without deadline", owner=None, deadline=None, status="pending", confidence=1.0)
        ],
        decisions=[Decision(decision="Agreed to verify nullability", confidence=1.0)],
        unresolved_issues=[UnresolvedIssue(issue="TBD whether to assign", confidence=1.0)],
    )
    null_test_id = repo.save_meeting(transcript="Short test transcript", meeting_output=test_null_output)
    retrieved_null = repo.get_meeting(null_test_id)
    assert retrieved_null is not None
    assert retrieved_null["action_items"][0]["owner"] is None
    assert retrieved_null["action_items"][0]["deadline"] is None
    print("    Explicit nullability test verified: owner=None -> SQL NULL, deadline=None -> SQL NULL.")

    # 7. Verify action-item status can be updated
    print("[7] Testing action-item status update...")
    first_item = retrieved["action_items"][0]
    action_item_id = first_item["id"]
    original_status = first_item["status"]
    new_status = "completed" if original_status != "completed" else "in_progress"

    update_success = repo.update_action_item_status(action_item_id, new_status)
    assert update_success is True, f"Failed to update status for action item {action_item_id}"

    # Verify status changed in database
    action_items_updated = repo.get_action_items(meeting_id)
    updated_item = next(item for item in action_items_updated if item["id"] == action_item_id)
    assert updated_item["status"] == new_status, f"Status was not updated! Got {updated_item['status']}"
    print(f"    Action item {action_item_id} status successfully transitioned: '{original_status}' -> '{new_status}'.")

    # 8. Verify foreign-key relationships work
    print("[8] Verifying foreign-key constraint enforcement...")
    # Test FK violation in its own short-lived connection
    conn = get_connection(test_db_path)
    fk_enforced = False
    try:
        conn.execute(
            """
            INSERT INTO action_items (meeting_id, task, owner, deadline, status, confidence)
            VALUES (999999, 'Invalid orphan task', NULL, NULL, 'pending', 1.0);
            """
        )
        raise AssertionError("Foreign key violation was NOT triggered when inserting orphan child!")
    except sqlite3.IntegrityError as err:
        fk_enforced = True
        print(f"    Foreign key constraint properly enforced on INSERT: {err}")
    finally:
        conn.close()  # Always close BEFORE any repo operation to prevent lock

    assert fk_enforced, "FK constraint was not raised!"

    # Verify cascading deletion — connection above is now closed
    print("    Testing CASCADE deletion on meeting removal...")
    repo.delete_meeting(null_test_id)
    # Check that child records for null_test_id were cascade-deleted
    items_after_delete = repo.get_action_items(null_test_id)
    decisions_after_delete = repo.get_decisions(null_test_id)
    issues_after_delete = repo.get_unresolved_issues(null_test_id)
    assert len(items_after_delete) == 0, "Action items were not deleted on CASCADE!"
    assert len(decisions_after_delete) == 0, "Decisions were not deleted on CASCADE!"
    assert len(issues_after_delete) == 0, "Unresolved issues were not deleted on CASCADE!"
    print("    CASCADE deletion verified: child records were automatically purged.")

    # 9. Verify listing meetings
    print("[9] Testing list_meetings...")
    meetings_list = repo.list_meetings()
    assert len(meetings_list) >= 1
    print(f"    Listed {len(meetings_list)} meetings successfully.")
    for m in meetings_list:
        print(f"    - ID {m['id']}: {m['action_items_count']} actions, {m['decisions_count']} decisions, {m['unresolved_issues_count']} issues. Summary: {m['summary'][:50]}...")

    # 10. Also verify MeetingOrchestrator.analyze_and_save integration
    print("[10] Testing MeetingOrchestrator.analyze_and_save minimal integration...")
    orch_with_repo = MeetingOrchestrator(repository=repo)
    out2, m_id2 = orch_with_repo.analyze_and_save(transcript)
    assert m_id2 > 0
    assert len(out2.action_items) == len(validated_output.action_items)
    print(f"    analyze_and_save succeeded seamlessly! Saved meeting ID = {m_id2}.")

    print("=" * 70)
    print("ALL TESTS PASSED WITH ZERO ERRORS!")
    print("=" * 70)


if __name__ == "__main__":
    run_e2e_persistence_test()
