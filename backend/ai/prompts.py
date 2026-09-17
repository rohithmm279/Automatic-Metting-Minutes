"""Prompt definitions for meeting analysis matching the proven benchmark rules."""


def build_meeting_analysis_prompt(transcript: str) -> str:
    """Build the 10-rule meeting-analysis prompt optimized for Qwen 2.5 3B."""
    return f"""Analyze the meeting transcript below strictly according to the following 10 rules.

### 10 RULES:

1. SUMMARY
- Produce a concise 3–5 sentence meeting summary.
- Preserve original meaning and tense: Action items are planned/pending tasks, NOT completed actions. Do not use past-tense verbs (never say "booked", "set up", or "coordinated") to describe pending tasks. Use planned/future phrasing (e.g. "Key upcoming tasks include...", "is tasked with", "will coordinate").
- Accurately mention the meeting purpose, upcoming action commitments, the agreed decision, and open issues.
- Do not invent facts, people, dates, deadlines, or outcomes.

2. ACTION ITEMS
Extract only tasks that are actually assigned or explicitly committed to.
Every action item object must contain exactly these 4 keys: "task", "owner", "deadline", "status".
- task: ONLY the core task action. Time and deadline words (e.g., "before the weekend", "sometime next week", "by Friday") are STRICTLY FORBIDDEN inside the task field.
  * Correct: "Book the auditorium"
  * Correct: "Set up the registration desk"
  * Correct: "Coordinate with campus security"
- owner: The person explicitly assigned or committing to the task. If a speaker agrees with "I'll..." or "I will..." (e.g. Meera: "I'll set up...", owner is "Meera"), use that speaker's name. If unassigned, use null.
- deadline: The explicit timeframe or date stated for the task (e.g., "before the weekend", "sometime next week", "Friday"). If none stated, use null.
- status: Always "pending" unless the transcript clearly says it is completed.
- Never invent an owner or deadline.
- Do not convert general discussion into an action item.
- FORBIDDEN: Do NOT include group decisions (such as finalizing or choosing the event date) in action items.

3. DECISIONS
Include only things that were explicitly:
- agreed
- approved
- confirmed
- finalized
- decided
Format: A flat array of strings (e.g., ["Finalize the event date"]).
Do NOT classify individual action items (like coordinating security or booking a room) as decisions.
Do NOT classify unresolved matters as decisions.

4. UNRESOLVED ISSUES
Include matters that remain:
- pending
- undecided
- awaiting approval
- unresolved
- unconfirmed
Format: A flat array of strings (e.g., ["Guest's travel plans", "Budget approval"]).
Do NOT classify action items as unresolved issues.
Do NOT classify confirmed decisions as unresolved issues.

5. DISTINGUISH THE THREE (STRICT MUTUAL EXCLUSIVITY)
Use this rule:
ACTION = something someone must do (e.g., "Book the auditorium", "Set up the registration desk", "Coordinate with campus security").
DECISION = something the group agreed/approved/confirmed/settled (e.g., "Finalize the event date").
UNRESOLVED ISSUE = something that is still pending/not settled (e.g., "Guest's travel plans", "Budget approval").
Never list an item under more than one category.

6. EVIDENCE
When possible, base each extracted item directly on transcript wording.
Do not infer missing information.

7. DEADLINES
Keep deadlines separate from task text.
Example 1:
"Bob will prepare the deployment scripts by Friday."
Correct:
task: "Prepare the deployment scripts"
owner: "Bob"
deadline: "Friday"
status: "pending"

Example 2:
"Meera: I'll set up the registration desk sometime next week."
Correct:
task: "Set up the registration desk"
owner: "Meera"
deadline: "sometime next week"
status: "pending"

8. OWNERS
Never assign ownership merely because a person discussed a topic.
Only assign an owner when the transcript explicitly indicates responsibility (speaker commitment or direct assignment).

9. TENSE
Preserve whether something is planned, pending, or completed.
Do not change "will prepare" into "prepared".

10. OUTPUT
Return ONLY valid JSON in exactly this structure:

{{
  "summary": "...",
  "action_items": [
    {{
      "task": "...",
      "owner": null,
      "deadline": null,
      "status": "pending"
    }}
  ],
  "decisions": [],
  "unresolved_issues": []
}}

No markdown formatting (do NOT use ``` or ```json).
No explanations outside the JSON.
No extra fields.

### TRANSCRIPT:
{transcript}

### JSON OUTPUT:"""


# Alias for backward compatibility
build_prompt = build_meeting_analysis_prompt
