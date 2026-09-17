"""
Comprehensive end-to-end API test for the FastAPI Meeting Minutes backend.

Tests:
  1. Health check
  2. POST /meetings  (full AI pipeline → SQLite)
  3. GET /meetings   (list)
  4. GET /meetings/{id} (full detail)
  5. PATCH /meetings/{id}/action-items/{item_id}/status
  6. GET /meetings/{id} (verify update)
  7. GET /meetings/99999  → 404
  8. PATCH with invalid status → 400
  9. POST with empty transcript → 422
 10. POST with whitespace-only transcript → 422
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import json
import time
from pathlib import Path

import requests

BASE = "http://127.0.0.1:8000"
TRANSCRIPT_PATH = (
    Path(__file__).resolve().parent
    / "datasets" / "01_PRIMARY" / "student_club" / "transcripts" / "SC001.txt"
)

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"

errors: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"  [{PASS}] {label}")
    else:
        msg = f"  [{FAIL}] {label}" + (f"  ← {detail}" if detail else "")
        print(msg)
        errors.append(f"{label}: {detail}")


def section(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


# ---------------------------------------------------------------------------
# 1. Health check
# ---------------------------------------------------------------------------
section("1. Health check")
r = requests.get(f"{BASE}/health")
check("GET /health → 200", r.status_code == 200, str(r.status_code))
check("status=ok", r.json().get("status") == "ok", str(r.json()))

# ---------------------------------------------------------------------------
# 2. POST /meetings  (real AI pipeline)
# ---------------------------------------------------------------------------
section("2. POST /meetings — full AI pipeline")
transcript = TRANSCRIPT_PATH.read_text(encoding="utf-8")
print(f"  Transcript: SC001.txt ({len(transcript)} chars)")
print("  Calling Qwen2.5:3b via Ollama (may take 10-30 s) ...")

t0 = time.perf_counter()
r = requests.post(f"{BASE}/meetings", json={"transcript": transcript}, timeout=120)
elapsed = time.perf_counter() - t0

check("POST /meetings → 201", r.status_code == 201, f"HTTP {r.status_code} body={r.text[:200]}")
created = r.json()
print(f"  Inference + persist time: {elapsed:.1f}s")
print(f"  meeting_id        = {created.get('meeting_id')}")
print(f"  summary (preview) = {str(created.get('summary', ''))[:80]}...")
print(f"  action_items      = {len(created.get('action_items', []))}")
print(f"  decisions         = {len(created.get('decisions', []))}")
print(f"  unresolved_issues = {len(created.get('unresolved_issues', []))}")

check("Response has meeting_id", "meeting_id" in created, str(created.keys()))
check("summary non-empty", bool(created.get("summary", "").strip()))
check("action_items is list", isinstance(created.get("action_items"), list))
check("decisions is list", isinstance(created.get("decisions"), list))
check("unresolved_issues is list", isinstance(created.get("unresolved_issues"), list))
check("created_at present", "created_at" in created)

meeting_id: int = created["meeting_id"]

# ---------------------------------------------------------------------------
# 3. GET /meetings
# ---------------------------------------------------------------------------
section("3. GET /meetings — list")
r = requests.get(f"{BASE}/meetings")
check("GET /meetings → 200", r.status_code == 200, str(r.status_code))
meetings = r.json()
check("List is non-empty", len(meetings) >= 1, f"len={len(meetings)}")
first = meetings[0]
check("Each item has 'id'", "id" in first)
check("Each item has 'summary'", "summary" in first)
check("Each item has counts", all(k in first for k in ("action_items_count", "decisions_count", "unresolved_issues_count")))
print(f"  Total stored meetings: {len(meetings)}")

# ---------------------------------------------------------------------------
# 4. GET /meetings/{id}
# ---------------------------------------------------------------------------
section(f"4. GET /meetings/{meeting_id} — full detail")
r = requests.get(f"{BASE}/meetings/{meeting_id}")
check(f"GET /meetings/{meeting_id} → 200", r.status_code == 200, str(r.status_code))
detail = r.json()
check("detail has 'transcript'", "transcript" in detail)
check("transcript matches posted", detail.get("transcript") == transcript)
check("detail has 'summary'", "summary" in detail)
check("detail has 'action_items'", isinstance(detail.get("action_items"), list))
check("detail has 'decisions'", isinstance(detail.get("decisions"), list))
check("detail has 'unresolved_issues'", isinstance(detail.get("unresolved_issues"), list))

# Check nullable owner/deadline in retrieved action items
for ai in detail.get("action_items", []):
    # owner and deadline can legitimately be None (NULL) — just verify the keys exist
    check(f"  action item {ai['id']} has 'owner' key", "owner" in ai)
    check(f"  action item {ai['id']} has 'deadline' key", "deadline" in ai)

# ---------------------------------------------------------------------------
# 5. PATCH status — update first action item
# ---------------------------------------------------------------------------
action_items = detail.get("action_items", [])
if action_items:
    item_id = action_items[0]["id"]
    original_status = action_items[0]["status"]
    new_status = "completed" if original_status != "completed" else "in_progress"

    section(f"5. PATCH /meetings/{meeting_id}/action-items/{item_id}/status")
    r = requests.patch(
        f"{BASE}/meetings/{meeting_id}/action-items/{item_id}/status",
        json={"status": new_status},
    )
    check(f"PATCH → 200", r.status_code == 200, f"HTTP {r.status_code} body={r.text[:200]}")
    patch_resp = r.json()
    check("updated=true", patch_resp.get("updated") is True)
    check(f"status in response = '{new_status}'", patch_resp.get("status") == new_status)
    print(f"  Transitioned: '{original_status}' → '{new_status}'")

    # ---------------------------------------------------------------------------
    # 6. GET /meetings/{id} — verify status persisted
    # ---------------------------------------------------------------------------
    section(f"6. GET /meetings/{meeting_id} — verify updated status")
    r = requests.get(f"{BASE}/meetings/{meeting_id}")
    detail2 = r.json()
    updated_item = next((x for x in detail2["action_items"] if x["id"] == item_id), None)
    check("Updated item found in detail", updated_item is not None)
    if updated_item:
        check(
            f"Persisted status = '{new_status}'",
            updated_item["status"] == new_status,
            f"Got: {updated_item['status']}",
        )
else:
    print("\n  [SKIP] No action items to PATCH.")

# ---------------------------------------------------------------------------
# 7. 404 — nonexistent meeting
# ---------------------------------------------------------------------------
section("7. GET /meetings/99999 — expect 404")
r = requests.get(f"{BASE}/meetings/99999")
check("GET /meetings/99999 → 404", r.status_code == 404, str(r.status_code))
check("detail field present", "detail" in r.json())
print(f"  Response: {r.json()}")

# ---------------------------------------------------------------------------
# 8. 400 — invalid status in PATCH
# ---------------------------------------------------------------------------
section("8. PATCH with invalid status → expect 422")
if action_items:
    r = requests.patch(
        f"{BASE}/meetings/{meeting_id}/action-items/{action_items[0]['id']}/status",
        json={"status": "flying"},
    )
    check("Invalid status → 422", r.status_code == 422, f"HTTP {r.status_code} body={r.text[:200]}")
    print(f"  Response: {r.json()}")

# 404 — action item not in this meeting
section("8b. PATCH action-item not in meeting → expect 404")
r = requests.patch(
    f"{BASE}/meetings/{meeting_id}/action-items/999999/status",
    json={"status": "completed"},
)
check("Unknown action item → 404", r.status_code == 404, f"HTTP {r.status_code}")
print(f"  Response: {r.json()}")

# 404 — PATCH on nonexistent meeting
section("8c. PATCH on nonexistent meeting → expect 404")
r = requests.patch(
    f"{BASE}/meetings/99999/action-items/1/status",
    json={"status": "completed"},
)
check("Unknown meeting for PATCH → 404", r.status_code == 404, f"HTTP {r.status_code}")
print(f"  Response: {r.json()}")

# ---------------------------------------------------------------------------
# 9. Empty transcript → 422 (Pydantic min_length)
# ---------------------------------------------------------------------------
section("9. POST with empty transcript → 422")
r = requests.post(f"{BASE}/meetings", json={"transcript": ""}, timeout=10)
check("Empty transcript → 422", r.status_code == 422, f"HTTP {r.status_code} body={r.text[:300]}")
print(f"  Response: {r.json()['detail'][0]['msg'] if isinstance(r.json().get('detail'), list) else r.json()}")

# ---------------------------------------------------------------------------
# 10. Whitespace-only transcript → 422
# ---------------------------------------------------------------------------
section("10. POST with whitespace-only transcript → 422")
r = requests.post(f"{BASE}/meetings", json={"transcript": "   \n\t  "}, timeout=10)
check("Whitespace transcript → 422", r.status_code == 422, f"HTTP {r.status_code} body={r.text[:300]}")
print(f"  Response: {r.json()['detail'][0]['msg'] if isinstance(r.json().get('detail'), list) else r.json()}")

# ---------------------------------------------------------------------------
# 11. Missing body field → 422
# ---------------------------------------------------------------------------
section("11. POST with missing 'transcript' field → 422")
r = requests.post(f"{BASE}/meetings", json={}, timeout=10)
check("Missing field → 422", r.status_code == 422, f"HTTP {r.status_code}")

# ---------------------------------------------------------------------------
# 12. DELETE /meetings/{meeting_id} — delete meeting and verify cascade
# ---------------------------------------------------------------------------
section(f"12. DELETE /meetings/{meeting_id} — delete and verify cascade")
r = requests.delete(f"{BASE}/meetings/{meeting_id}")
check("DELETE /meetings/{id} → 204", r.status_code == 204, f"HTTP {r.status_code}")

# Confirm it can no longer be retrieved
r = requests.get(f"{BASE}/meetings/{meeting_id}")
check("GET after DELETE → 404", r.status_code == 404, f"HTTP {r.status_code}")

# Confirm repeated DELETE returns 404
r = requests.delete(f"{BASE}/meetings/{meeting_id}")
check("Repeated DELETE → 404", r.status_code == 404, f"HTTP {r.status_code}")

# DELETE nonexistent meeting → 404
r = requests.delete(f"{BASE}/meetings/99999")
check("DELETE /meetings/99999 → 404", r.status_code == 404, f"HTTP {r.status_code}")

# ---------------------------------------------------------------------------
# Final summary
# ---------------------------------------------------------------------------
print(f"\n{'=' * 60}")
if errors:
    print(f"  RESULT: {len(errors)} FAILURE(S)")
    for e in errors:
        print(f"    • {e}")
    sys.exit(1)
else:
    print("  ALL API TESTS PASSED WITH ZERO ERRORS!")
print(f"{'=' * 60}\n")
