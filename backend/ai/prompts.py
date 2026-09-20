"""Prompt definitions for meeting analysis matching the proven benchmark rules."""


def build_meeting_analysis_prompt(transcript: str) -> str:
    """Build the meeting-analysis prompt optimized for Qwen 2.5 3B."""

    return f"""Analyze the meeting transcript below strictly according to the following rules.

### RULES:

1. SUMMARY
- Produce a concise 3–5 sentence meeting summary synthesizing the concluded state and final consensus.
- Preserve original meaning and tense.
- Action items are planned/pending tasks, NOT completed actions.
- Do not use past-tense verbs to describe pending tasks.
- Accurately mention the meeting purpose, important upcoming commitments, confirmed decisions, and open issues/risks.
- Ground all approvals and statements strictly to the actual speakers. Never state that an external or absent team (e.g. Finance, Legal) approved something when the speaker merely mentioned needing or seeking their sign-off.
- Do not invent facts, people, dates, deadlines, or outcomes.

2. ACTION ITEMS
Extract every concrete task, deliverable, assignment, or agreed prerequisite step that is explicitly assigned or committed to by a speaker.

An action item requires:
- a concrete task or deliverable
- an explicit person responsible OR an explicit speaker commitment (e.g. "I will assign two PMs..." -> Owner is the speaker; "If Alex provides release notes by Sept 24..." -> Task: "Provide feature release notes", Owner: "Alex", Deadline: "Sept 24")
- an expectation that the task will be performed

Examples:
- "I will send the report."
- "I'll check with HR."
- "Please own the messaging pillars."
- "Can you finalize the budget?"

A speaker may make multiple commitments in one turn.
Extract EACH independent commitment separately.

A host/facilitator can also be an action-item owner.

Do NOT extract general guidance or ongoing responsibilities unless they
contain a concrete deliverable.

Normally exclude:
- "Keep us posted."
- "Flag risks early."
- "Stay aligned."
- "Monitor this."
- "Keep an eye on this."
- "Be aware of the risk."

Every action item MUST contain exactly these 4 keys:
"task", "owner", "deadline", "status".

task:
- Include ONLY the core task.
- Do NOT include deadline/time expressions in the task.
- Example:
  "Draft the messaging pillars by September 25"
  becomes:
  "Draft the messaging pillars"

owner:
- Use the explicitly assigned person.
- If the speaker says "I will..." or "I'll...", that speaker is the owner.
- If responsibility is genuinely unassigned, use null.
- Never infer ownership merely because someone discussed the topic.

deadline:
- Use ONLY an explicit deadline or relative timeframe for that specific task (e.g. "Sept 23", "first 3 days post-launch", "by Friday").
- If no explicit deadline exists, use null.
- Never invent "ASAP", "Ongoing", "Soon", etc.

status:
- Always "pending" unless the transcript explicitly says the task
  has already been completed.

3. DECISIONS
A decision is a settled choice, agreement, approval, confirmation,
policy, direction, selected option, or contingent release plan.

Examples:
- "Let's lock the campaign theme."
- "Everyone agreed to use October 15 as the central moment."
- "Keep target launch date as October 1, 2026, with fallback to October 15 if load tests fail."
- "Pause paid ad spend until engineering confirms readiness."
- "Approved the 20% discount code for early adopters from product side."

Include ALL decisions, strategic choices, spending freezes, and policies explicitly agreed, approved, confirmed, finalized, or decided by the group or meeting lead.
Look for markers: "Let's make a decision", "Approved", "Agreed", "We keep...", "Smart move / hold off".

REJECT PROPOSALS: If a proposal was contested, modified, or postponed, do NOT classify it as a confirmed decision.

4. ACTIONS ARE NOT DECISIONS
If a person is assigned or commits to performing work, classify it as
an ACTION ITEM, not a DECISION.

5. UNRESOLVED ISSUES, RISKS & CONSTRAINTS
Include matters that remain:
- pending or undecided
- awaiting approval or external sign-off (e.g. "20% discount requires sign-off from Finance")
- active technical or operational risks being monitored/mitigated (e.g. "Database latency spikes during peak hours (3-5s delays for ~5% of users)", "Anticipated 30% increase in support ticket volume")
- unresolved, unconfirmed, or blocked

Do NOT classify action items as unresolved issues.
Do NOT classify confirmed decisions as unresolved issues.
- unconfirmed
- blocked
- dependent on another event

Do NOT classify action items as unresolved issues.
Do NOT classify confirmed decisions as unresolved issues.

6. STRICT MUTUAL EXCLUSIVITY
Each extracted item must belong to ONE category only:

ACTION ITEM:
Something someone must do.

DECISION:
Something the group has settled or agreed.

UNRESOLVED ISSUE:
Something that remains unresolved or pending.

Never put the same semantic item into multiple categories.

7. CONDITIONAL DATES
A date used as a condition or threshold is NOT automatically the
deadline of an action item.

Example:
"If CRM attribution is not ready by September 30, we'll use UTM tracking."

Correct interpretation:
- Risk/threshold date = September 30.
- Fallback = UTM-only tracking.
- The date is NOT automatically the deadline for:
  "Follow up with CRM."

Do not convert conditional dates into task deadlines unless the
transcript explicitly states that the task itself must be completed
by that date.

8. MULTIPLE COMMITMENTS
Extract every independent commitment from a speaker's turn.

Example:
"I'll finalize the media plan. I'll also chase the CRM team."

Correct:
Action 1:
  task = "Finalize the media plan"

Action 2:
  task = "Chase the CRM team"

Do NOT stop after extracting the first commitment.

9. FOLLOW-UP MEETINGS
A scheduled future meeting is normally a FOLLOW-UP EVENT, not a
strategic decision and not an action item.

Example:
"Let's reconvene next Thursday to review the draft."

Do NOT create:
action = "Review the draft"

Do NOT create:
decision = "Review the draft"

The meeting itself may be mentioned in the summary, but there is no
separate event field in the required JSON schema.

10. EVIDENCE
Base every extracted item directly on transcript evidence.

Do not infer:
- missing owners
- missing deadlines
- implied approvals
- implied task completion
- causal relationships between risks and actions

If the transcript does not explicitly support an attribute, use null.

11. DEADLINE SEPARATION
Always keep deadline information separate from task text.

Example:
Transcript:
"Rahul will send the beta summary by September 23."

Correct:
task = "Send the beta summary"
owner = "Rahul Mehta"
deadline = "September 23"

Incorrect:
task = "Send the beta summary by September 23"

12. OWNER RESOLUTION
Resolve first-person commitments using the speaker identity.

Example:
Rahul Mehta:
"I'll send the beta summary by September 23."

Correct:
owner = "Rahul Mehta"

Do not use null when the speaker's identity is clearly known.

13. NO HALLUCINATED ACTIONS
Do not create an action merely because:
- something was discussed
- something was recommended
- something was agreed
- a risk exists
- a future meeting was scheduled
- a person was mentioned

There must be an actual commitment or assignment.

14. RISK/MITIGATION RELATIONSHIPS
Do not automatically treat a nearby action as the mitigation for a risk.

Example:
Risk:
"Beta feedback may change positioning."

Action:
"Rahul will send beta insights."

Do NOT automatically state that Rahul's action eliminates or mitigates
the risk unless the transcript explicitly establishes that relationship.

15. FINAL SELF-CHECK
Before returning JSON, verify:

- Every action is a real concrete commitment.
- No confirmed decision appears as an action.
- No action appears as a decision.
- No follow-up meeting is incorrectly converted into an action.
- Every owner is supported by the transcript.
- Every deadline is explicitly supported.
- Conditional/threshold dates are not incorrectly used as task deadlines.
- Multiple commitments from one speaker are all extracted.
- No invented facts are present.
- Task text contains no deadline words.
- Each semantic item appears in only one category.

### OUTPUT

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

No markdown formatting.
Do NOT use ``` or ```json.
No explanations outside the JSON.
No extra fields.

### TRANSCRIPT:
{transcript}

### JSON OUTPUT:"""


# Alias for backward compatibility
build_prompt = build_meeting_analysis_prompt