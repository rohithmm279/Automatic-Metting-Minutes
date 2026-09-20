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

2. ACTION ITEMS & OWNER BINDING
Extract EVERY concrete task, deliverable, assignment, or agreed prerequisite step that is explicitly assigned or committed to by a speaker.

An action item requires:
- a concrete engineering/operational task or deliverable
- an explicit person responsible OR an explicit speaker commitment (e.g.:
  * Assign tasks to the person who explicitly self-commits ("I will do X", "I'll handle this", "My action item is X", "I can take that") -> Owner is strictly that committing speaker;
  * When a speaker addresses someone with an instruction or request that is accepted/acknowledged (e.g., "Dev, please update the status page logic") -> Owner is that person;
  * When tasks are listed with names in a structured list or wrap-up (e.g., "1. Maya: Build pipeline circuit breaker"), the named person is the Owner)
- an expectation that the task will be performed

STRICT ACTION ITEM GUARDRAILS:
- OWNER BINDING: If Maya says "I'll build it", Maya is the owner, NOT someone else who raised the issue. NEVER assign tasks to the meeting host, facilitator, or Incident Commander simply because they summarized or requested the task at the end.
- NO META-TASKS: Do NOT extract meta-instructions or meeting administrative commands (e.g., "log the action items", "assign tasks to log", "note down the meeting minutes", "record these in Jira") as action items. Do NOT assign fake tasks to facilitators simply because they asked the team to record or log items.
- NO INCIDENT / TIMELINE TIMESTAMPS AS DEADLINES: Incident event timestamps, alert firing times (e.g. "11:02 AM", "14:30 UTC"), log timestamps, and dialogue timestamps indicate when past events occurred, NOT task deadlines. NEVER treat past incident times as deadlines. If no explicit future calendar date is mentioned for a task, deadline MUST be null.

Do NOT extract general guidance or ongoing responsibilities unless they contain a concrete deliverable.
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
- Include ONLY the core task (e.g., "Build the CI/CD pipeline circuit breaker", "Update status page auto-trigger logic").
- Do NOT include deadline/time expressions in the task. Strip out time phrases like "today", "by tomorrow", "on Thursday", "by next Monday", "by EOD today".

owner:
- Extract the person explicitly responsible or committing (e.g. "Maya", "Dev", "Carlos").
- If the speaker says "I will..." or "I'll...", that speaker is the owner.
- If responsibility is genuinely unassigned, use null.
- Never infer ownership merely because someone discussed the topic or facilitated the meeting.

deadline:
- ALL action item deadlines MUST be formatted strictly as ISO standard dates: YYYY-MM-DD (e.g., "2026-09-20", "2026-09-22", "2026-09-23", "2026-10-05").
- FORWARD RELATIVE DATE MATH RULE:
  * When calculating relative weekdays ("by Wednesday", "by Tuesday", "this Friday", "tomorrow", "by EOD"), ALWAYS compute strictly forward from the Meeting Header Date.
  * For example, if the meeting took place on Sunday, September 20, 2026:
    - "today" or "today EOD" -> "2026-09-20"
    - "tomorrow" -> "2026-09-21"
    - "by Tuesday" -> "2026-09-22" (September 20 + 2 days = September 22)
    - "by Wednesday" -> "2026-09-23" (September 20 + 3 days = September 23)
    - "this Friday" -> "2026-09-25" (September 20 + 5 days = September 25)
  * NEVER output a deadline date that occurs BEFORE the meeting header date (e.g., NEVER output 2026-09-03 or 2026-09-14 for a meeting held on September 20, 2026).
- If no explicit future calendar deadline exists, use null.
- Never invent "ASAP", "Ongoing", "Soon", etc.

status:
- Always "pending" unless the transcript explicitly states the task has already been completed.

3. DECISIONS (STRICT TAXONOMY & DECISION DISCRIMINATOR)
A Decision is an organizational agreement, policy, schedule target, vendor choice, scope cutoff, or architectural design choice confirmed by the group or meeting lead (e.g., "Launch pricing experiment on September 29, 2026 (pending bugs/QA)", "Keep current paywall layout for the experiment", "Monitor conversion daily and decide on changes after seven days of data").
Format: A flat array of strings.
Include ALL confirmed strategic choices, launch date policies, milestone/freeze agreements, technical scope alignments, and spending policies explicitly agreed, approved, confirmed, finalized, or decided by the group or meeting lead.
Verbal agreements and consensus choices count as confirmed decisions even if the word "decide" is not used.
REJECT PROPOSALS: If a proposal was contested, modified, or postponed, do NOT classify it as a confirmed decision.

4. ACTIONS ARE NOT DECISIONS (DECISION DISCRIMINATOR & ZERO TASK/RISK OVERLAP)
DECISION DISCRIMINATOR:
- Ask: "Is this a structural policy/agreement, or is it an action item, conditional task, or risk mitigation?"
- NEVER classify individual tasks, operational actions, conditional action items, or risk mitigations as Key Decisions:
  * "Escalate billing provider's sandbox stability issue..." is an Action Item (#5), NOT a Key Decision.
  * "Hard freeze campaign creatives today..." is an operational risk mitigation strategy, NOT an independent Key Decision.
- If a person or team is assigned to execute or deliver it (e.g., "Priya Sharma will circulate...", "Dev will escalate..."), it belongs ONLY under Action Items.
- NEVER list an Action Item, conditional task, or deliverable handoff under Decisions. Key Decisions describe structural policies, milestone dates, vendors, or designs.

5. UNRESOLVED ISSUES, RISKS & CONSTRAINTS (ZERO-RISK HANDLING)
Include matters that remain pending, undecided, awaiting external sign-off, or active technical/operational risks discussed in this meeting transcript.
Format: A flat array of strings.
ZERO DATA CONTAMINATION & ZERO-RISK HANDLING: NEVER copy example text or invent risks/issues from other meetings. If no unresolved issues or active risks are present in this transcript, return an empty array []. NEVER generate a dummy risk item containing text like "No issues identified" or "No issues found".
Do NOT output nested objects or dictionaries inside unresolved_issues. Output ONLY a flat list of strings.
Do NOT classify action items as unresolved issues.
Do NOT classify confirmed decisions as unresolved issues.

6. STRICT MUTUAL EXCLUSIVITY
Each extracted item must belong to ONE category only:
- ACTION ITEM: Something someone must do.
- DECISION: Something the group has settled or agreed.
- UNRESOLVED ISSUE: Something that remains unresolved, blocked, or a pending risk.
Never put the same semantic item into multiple categories.

7. CONDITIONAL DATES
A date used as a condition or threshold is NOT automatically the deadline of an action item unless the transcript explicitly states the task must be completed by that date.

8. MULTIPLE COMMITMENTS
Extract every independent commitment from a speaker's turn.

9. FOLLOW-UP MEETINGS
A scheduled future meeting is normally a FOLLOW-UP EVENT, not a strategic decision and not an action item, unless someone is tasked to organize/schedule it.

10. EVIDENCE & OWNER RESOLUTION
Base every extracted item directly on transcript evidence. Resolve first-person commitments using the speaker identity.

11. DEADLINE SEPARATION & ISO DATES
Always keep deadline information separate from task text and formatted in ISO YYYY-MM-DD.
Example:
Transcript Header: Date: September 20, 2026
Transcript: "Rahul will send the beta summary by September 23."
Correct:
task = "Send the beta summary"
owner = "Rahul Mehta"
deadline = "2026-09-23"
Incorrect:
task = "Send the beta summary by September 23"

12. FINAL SELF-CHECK
Before returning JSON, verify:
- Every action is a real concrete commitment with deadline formatted as YYYY-MM-DD or null computed forward from meeting header date.
- No confirmed decision appears as an action.
- No action or deliverable handoff appears as a decision.
- Every owner is supported by the transcript and bound to the actual committing speaker.
- If no risks exist, unresolved_issues is [].
- No invented facts are present.
- Each semantic item appears in only one category.

### OUTPUT FORMAT

Return ONLY valid JSON in exactly this structure:

{{
  "summary": "Concise 3-5 sentence meeting summary.",
  "action_items": [
    {{
      "task": "Clean task description without deadline words",
      "owner": "Owner name or null",
      "deadline": "YYYY-MM-DD or null",
      "status": "pending"
    }}
  ],
  "decisions": [
    "Settled decision text"
  ],
  "unresolved_issues": [
    "Unresolved issue text"
  ]
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